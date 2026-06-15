"""2Captcha連携によるCAPTCHA解決 - 人間ワーカーに解読を依頼

2Captcha APIに解読タスクを送信し、トークンを受け取ってページに注入する。
reCAPTCHA v2/v3、hCaptcha、Turnstileに対応。
"""

import logging
import os
import time
from typing import Optional

import requests
import streamlit as st
from playwright.sync_api import Page

from utils.db_logs import get_setting, save_setting

logger = logging.getLogger(__name__)

# 2Captcha APIエンドポイント
IN_URL = "http://2captcha.com/in.php"
RES_URL = "http://2captcha.com/res.php"

# ポーリング設定
POLL_INTERVAL = 5  # 秒
SOLVE_TIMEOUT = 120  # 秒
SUBMIT_RETRY = 3  # キュー満杯時のリトライ回数

# 費用計算（$0.003/解決 × 150円/USD = 約0.45円）
COST_JPY_PER_SOLVE = 0.45


def solve_captcha(page: Page, page_url: str, captcha_info: dict) -> dict:
    """CAPTCHA解決〜トークン注入を一気通貫で実行する

    Args:
        page: Playwright Page（トークン注入先）
        page_url: CAPTCHA設置ページURL
        captcha_info: detect_captcha_info()の戻り値

    Returns:
        {"solved": bool, "token": str|None, "error": str|None,
         "elapsed_sec": float, "cost_jpy": float, "captcha_id": str|None}
    """
    start = time.time()
    result = {
        "solved": False, "token": None, "error": None,
        "elapsed_sec": 0.0, "cost_jpy": 0.0, "captcha_id": None,
    }

    # sitekey必須チェック
    sitekey = captcha_info.get("sitekey")
    if not sitekey:
        result["error"] = "no_sitekey"
        return result

    # APIキー取得
    api_key = _get_api_key()
    if not api_key:
        result["error"] = "no_api_key"
        logger.info("2Captcha APIキー未設定のためスキップ")
        return result

    # タスク登録
    try:
        captcha_id = _submit_captcha(api_key, page_url, captcha_info)
        result["captcha_id"] = captcha_id
    except ValueError as e:
        result["error"] = str(e)
        return result
    except requests.RequestException:
        result["error"] = "network_error"
        return result

    # ポーリング
    try:
        token = _poll_result(api_key, captcha_id)
    except TimeoutError:
        result["error"] = "solve_timeout"
        return result
    except ValueError as e:
        result["error"] = str(e)
        return result
    except requests.RequestException:
        result["error"] = "network_error"
        return result

    # トークンをページに注入
    try:
        _inject_token(page, captcha_info, token)
    except ValueError as e:
        result["error"] = str(e)
        return result
    except Exception as e:
        logger.warning("トークン注入失敗: %s", str(e)[:80])
        result["error"] = "injection_failed"
        return result

    # 成功：カウンタ更新
    elapsed = time.time() - start
    result.update({
        "solved": True, "token": token,
        "elapsed_sec": elapsed, "cost_jpy": COST_JPY_PER_SOLVE,
    })
    _increment_usage_counters(COST_JPY_PER_SOLVE)
    return result


def _get_api_key() -> str:
    """2Captcha APIキーを取得する（session_state → DB → 環境変数）"""
    try:
        key = st.session_state.get("two_captcha_api_key", "")
    except Exception:
        key = ""

    if not key:
        key = get_setting("two_captcha_api_key", "")

    if not key:
        key = os.environ.get("TWO_CAPTCHA_API_KEY", "")

    return key


def _submit_captcha(api_key: str, page_url: str, captcha_info: dict) -> str:
    """2Captchaに解決タスクを登録し、captcha_idを返す"""
    ctype = captcha_info["type"]
    sitekey = captcha_info["sitekey"]

    # CAPTCHA種別ごとのパラメータ組み立て
    params = {"key": api_key, "pageurl": page_url, "json": "1"}
    if ctype == "recaptcha_v2":
        params["method"] = "userrecaptcha"
        params["googlekey"] = sitekey
    elif ctype == "recaptcha_v3":
        params["method"] = "userrecaptcha"
        params["version"] = "v3"
        params["googlekey"] = sitekey
        params["action"] = captcha_info.get("action", "submit")
        params["min_score"] = str(captcha_info.get("min_score", 0.3))
    elif ctype == "hcaptcha":
        params["method"] = "hcaptcha"
        params["sitekey"] = sitekey
    elif ctype == "turnstile":
        params["method"] = "turnstile"
        params["sitekey"] = sitekey
    else:
        raise ValueError("unsupported_captcha_type")

    # キュー満杯時のリトライ付きで送信
    for attempt in range(SUBMIT_RETRY):
        resp = requests.post(IN_URL, data=params, timeout=30).json()
        if resp.get("status") == 1:
            return str(resp["request"])

        error_code = resp.get("request", "unknown_error")
        err = _map_error(error_code)
        if err != "queue_full":
            raise ValueError(err)
        time.sleep(POLL_INTERVAL)

    raise ValueError("queue_full")


def _poll_result(api_key: str, captcha_id: str) -> str:
    """結果をポーリングしてトークンを返す"""
    deadline = time.time() + SOLVE_TIMEOUT
    params = {
        "key": api_key, "action": "get",
        "id": captcha_id, "json": "1",
    }

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        resp = requests.get(RES_URL, params=params, timeout=30).json()
        if resp.get("status") == 1:
            return str(resp["request"])
        if resp.get("request") == "CAPCHA_NOT_READY":
            continue
        raise ValueError(_map_error(resp.get("request", "unknown_error")))

    raise TimeoutError("solve_timeout")


def _map_error(error_code: str) -> str:
    """2Captchaエラーコードを内部エラー名にマッピング"""
    mapping = {
        "ERROR_WRONG_USER_KEY": "api_key_invalid",
        "ERROR_KEY_DOES_NOT_EXIST": "api_key_invalid",
        "ERROR_ZERO_BALANCE": "insufficient_balance",
        "ERROR_NO_SLOT_AVAILABLE": "queue_full",
        "ERROR_CAPTCHA_UNSOLVABLE": "unsolvable",
    }
    return mapping.get(error_code, f"api_error:{error_code}")


def _inject_token(page: Page, captcha_info: dict, token: str) -> None:
    """CAPTCHA種別ごとに適切なDOMへトークンを注入する"""
    if not token:
        raise ValueError("empty_token")

    ctype = captcha_info["type"]
    if ctype in ("recaptcha_v2", "recaptcha_v3"):
        page.evaluate(
            """(t) => {
                document.querySelectorAll(
                    '[name="g-recaptcha-response"], #g-recaptcha-response'
                ).forEach(e => {
                    e.innerHTML = t; e.value = t;
                    e.style.display = 'block';
                });
            }""",
            token,
        )
    elif ctype == "hcaptcha":
        # hCaptchaは両方のtextareaにセットするケースがある
        page.evaluate(
            """(t) => {
                document.querySelectorAll(
                    '[name="h-captcha-response"], [name="g-recaptcha-response"]'
                ).forEach(e => {
                    e.innerHTML = t; e.value = t;
                    e.style.display = 'block';
                });
            }""",
            token,
        )
    elif ctype == "turnstile":
        page.evaluate(
            """(t) => {
                document.querySelectorAll(
                    '[name="cf-turnstile-response"]'
                ).forEach(e => {
                    e.innerHTML = t; e.value = t;
                    e.style.display = 'block';
                });
            }""",
            token,
        )
    else:
        raise ValueError(f"unknown_type:{ctype}")


def _increment_usage_counters(cost_jpy: float) -> None:
    """月次・累計の解決回数と推定費用を更新する"""
    import datetime as _dt

    try:
        month_key = (
            f"captcha_solve_count_month_"
            f"{_dt.datetime.now().strftime('%Y%m')}"
        )

        current_month = _safe_int(get_setting(month_key, "0"))
        save_setting(month_key, str(current_month + 1))

        total = _safe_int(get_setting("captcha_solve_count_total", "0"))
        save_setting("captcha_solve_count_total", str(total + 1))

        spend = _safe_float(get_setting("captcha_spend_jpy", "0"))
        save_setting("captcha_spend_jpy", f"{spend + cost_jpy:.2f}")
    except Exception as e:
        logger.warning("使用状況カウンタ更新失敗: %s", str(e)[:80])


def _safe_int(s: str) -> int:
    """文字列を安全にintに変換（失敗時は0）"""
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def _safe_float(s: str) -> float:
    """文字列を安全にfloatに変換（失敗時は0.0）"""
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
