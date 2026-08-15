"""CAPTCHA種別・sitekey検出 - HTMLからCAPTCHA情報を抽出する

ネットワークアクセスなしの純粋なパース処理。
reCAPTCHA v2/v3、hCaptcha、Cloudflare Turnstileに対応。
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# reCAPTCHA v3のJS呼び出しパターン
_V3_EXECUTE_PATTERN = re.compile(
    r"grecaptcha\.execute\s*\(\s*['\"]([0-9A-Za-z_-]{20,})['\"]"
    r"(?:\s*,\s*\{[^}]*action\s*:\s*['\"]([^'\"]+)['\"])?",
    re.IGNORECASE,
)

# JS変数内のsitekey定義パターン（{ sitekey: 'xxx' } 形式）
_JS_SITEKEY_PATTERN = re.compile(
    r"sitekey\s*[:=]\s*['\"]([0-9A-Za-z_-]{20,})['\"]",
    re.IGNORECASE,
)

# reCAPTCHA iframeのURLパターン（?k=SITEKEY）
_RECAPTCHA_IFRAME_PATTERN = re.compile(
    r"google\.com/recaptcha/api2/(?:anchor|bframe)\?[^\"']*k=([0-9A-Za-z_-]{20,})",
    re.IGNORECASE,
)

# hCaptcha iframeのURLパターン
_HCAPTCHA_IFRAME_PATTERN = re.compile(
    r"hcaptcha\.com/captcha/v1/api\.js\?[^\"']*sitekey=([0-9A-Za-z_-]{20,})",
    re.IGNORECASE,
)


def detect_captcha_info(html: str) -> dict:
    """HTMLからCAPTCHA情報を抽出する

    検出順: reCAPTCHA v2 → hCaptcha → Turnstile → reCAPTCHA v3 → 不明

    Args:
        html: ページのHTMLテキスト

    Returns:
        {"present": bool, "type": str|None, "sitekey": str|None,
         "action": str|None, "min_score": float|None}
    """
    default = {
        "present": False, "type": None, "sitekey": None,
        "action": None, "min_score": None,
    }

    if not html:
        return default

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return default

    # 各種CAPTCHAを優先順位で検出
    for detector in (
        _detect_recaptcha_v2,
        _detect_hcaptcha,
        _detect_turnstile,
    ):
        result = detector(soup)
        if result:
            result["present"] = True
            logger.info(
                "CAPTCHA検出: %s (sitekey=%s)",
                result["type"], (result.get("sitekey") or "")[:20],
            )
            return {**default, **result}

    # reCAPTCHA v3はJS内のパターンマッチ
    v3 = _detect_recaptcha_v3(html)
    if v3:
        v3["present"] = True
        logger.info("CAPTCHA検出: %s", v3["type"])
        return {**default, **v3}

    # iframeのURL/JS変数からsitekey抽出（フォールバック）
    fallback = _detect_from_iframe_or_js(html)
    if fallback:
        fallback["present"] = True
        logger.info(
            "CAPTCHA検出: %s (フォールバック・sitekey=%s)",
            fallback["type"], fallback["sitekey"][:20],
        )
        return {**default, **fallback}

    # 文字列マッチのみで種別特定できなかった場合
    html_lower = html.lower()
    for pat in ("g-recaptcha", "h-captcha", "captcha", "cf-turnstile"):
        if pat in html_lower:
            logger.warning("CAPTCHA文字列検出（種別不明・sitekey抽出不可）")
            return {**default, "present": True, "type": "unknown"}

    return default


def _detect_from_iframe_or_js(html: str) -> Optional[dict]:
    """iframeのURLまたはJS変数からsitekeyを抽出する（フォールバック）

    検出順:
    1. reCAPTCHA iframeのURL `?k=SITEKEY`
    2. hCaptcha iframeのURL `?sitekey=SITEKEY`
    3. JS変数 `sitekey: 'xxx'` 形式

    Args:
        html: ページのHTMLテキスト

    Returns:
        検出結果dict、なければNone
    """
    # reCAPTCHA iframe URL
    m = _RECAPTCHA_IFRAME_PATTERN.search(html)
    if m:
        # v3バッジ表示の有無で種別判定
        if "grecaptcha-badge" in html.lower():
            return {
                "type": "recaptcha_v3", "sitekey": m.group(1),
                "action": "submit", "min_score": 0.3,
            }
        return {"type": "recaptcha_v2", "sitekey": m.group(1)}

    # hCaptcha iframe URL
    m = _HCAPTCHA_IFRAME_PATTERN.search(html)
    if m:
        return {"type": "hcaptcha", "sitekey": m.group(1)}

    # JS変数 { sitekey: 'xxx' }
    m = _JS_SITEKEY_PATTERN.search(html)
    if m:
        sitekey = m.group(1)
        # reCAPTCHAのsitekeyは通常「6L」で始まる
        if sitekey.startswith("6L"):
            if "grecaptcha-badge" in html.lower():
                return {
                    "type": "recaptcha_v3", "sitekey": sitekey,
                    "action": "submit", "min_score": 0.3,
                }
            return {"type": "recaptcha_v2", "sitekey": sitekey}
        return {"type": "hcaptcha", "sitekey": sitekey}

    return None


def _detect_recaptcha_v2(soup: BeautifulSoup) -> Optional[dict]:
    """reCAPTCHA v2（チェックボックス型）を検出する"""
    elem = soup.find(class_="g-recaptcha")
    if not elem:
        return None

    sitekey = elem.get("data-sitekey", "")
    if not sitekey:
        return None

    return {"type": "recaptcha_v2", "sitekey": sitekey}


def _detect_hcaptcha(soup: BeautifulSoup) -> Optional[dict]:
    """hCaptchaを検出する"""
    elem = soup.find(class_="h-captcha")
    if not elem:
        return None

    sitekey = elem.get("data-sitekey", "")
    if not sitekey:
        return None

    return {"type": "hcaptcha", "sitekey": sitekey}


def _detect_turnstile(soup: BeautifulSoup) -> Optional[dict]:
    """Cloudflare Turnstileを検出する"""
    elem = soup.find(class_="cf-turnstile")
    if not elem:
        return None

    sitekey = elem.get("data-sitekey", "")
    if not sitekey:
        return None

    return {"type": "turnstile", "sitekey": sitekey}


def _detect_recaptcha_v3(html: str) -> Optional[dict]:
    """reCAPTCHA v3（invisible）を検出する

    JS中の grecaptcha.execute('SITEKEY', {action: '...'}) を正規表現で抽出。
    """
    m = _V3_EXECUTE_PATTERN.search(html)
    if not m:
        return None

    sitekey = m.group(1)
    action = m.group(2) or "submit"

    return {
        "type": "recaptcha_v3",
        "sitekey": sitekey,
        "action": action,
        "min_score": 0.3,  # デフォルト最低スコア
    }
