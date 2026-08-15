"""送信エンジン - Playwrightによるフォーム自動入力・送信"""

import logging
import random
import time
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

from config import (
    DEFAULT_SENDER,
    PAGE_TIMEOUT,
    POST_SUBMIT_WAIT,
    WAIT_MAX,
    WAIT_MIN,
)
from engine.ai_mapper import analyze_form_with_ai, merge_mappings
from engine.learner import get_form_cache, save_form_cache, save_result
from engine.scraper import (
    analyze_form,
    detect_captcha,
    extract_forms,
    find_contact_url,
)

logger = logging.getLogger(__name__)


def _get_domain(url: str) -> str:
    """URLからドメイン名を抽出する"""
    return urlparse(url).netloc


def _fill_form(
    page: Page, mapping: dict, message: str, sender: dict
) -> bool:
    """マッピングに基づいてフォームに入力する

    Args:
        page: Playwrightのページ
        mapping: フィールドマッピング
        message: 送信メッセージ本文
        sender: 送信者情報

    Returns:
        入力成功ならTrue
    """
    # フィールドタイプ → 入力値の対応
    values = {
        "company": sender.get("company", ""),
        "name": sender.get("name", ""),
        "email": sender.get("email", ""),
        "phone": sender.get("phone", ""),
        "subject": sender.get("subject", "ご提案のご連絡"),
        "message": message,
    }

    filled_count = 0
    for field_type, field_info in mapping.items():
        # メタ情報はスキップ
        if field_type.startswith("_"):
            continue
        value = values.get(field_type, "")
        if not value or not field_info.get("name"):
            continue

        try:
            selector = f'[name="{field_info["name"]}"]'
            element = page.query_selector(selector)
            if element:
                element.click()
                time.sleep(random.uniform(0.1, 0.3))
                element.fill(value)
                filled_count += 1
                logger.info("入力完了: %s", field_type)
        except Exception as e:
            logger.warning("入力失敗 [%s]: %s", field_type, e)

    return filled_count > 0


def _find_submit_button(page: Page, mapping: dict) -> Optional[str]:
    """送信ボタンのセレクタを探す

    Args:
        page: Playwrightのページ
        mapping: フィールドマッピング

    Returns:
        送信ボタンのセレクタ、見つからなければNone
    """
    # AI判定のセレクタがあればそれを使う
    if "_submit" in mapping:
        return mapping["_submit"]

    # 一般的な送信ボタンのセレクタを試行
    candidates = [
        'input[type="submit"]',
        'button[type="submit"]',
        'button:has-text("送信")',
        'button:has-text("確認")',
        'input[value="送信"]',
        'input[value="確認"]',
        'button:has-text("Send")',
    ]
    for sel in candidates:
        if page.query_selector(sel):
            return sel
    return None


def send_to_company(
    url: str,
    company_name: str,
    message: str,
    sender: Optional[dict] = None,
    headless: bool = False,
) -> dict:
    """1企業へフォーム送信を実行する

    Args:
        url: 企業のWebサイトURL
        company_name: 企業名
        message: 送信メッセージ（{{company_name}}は置換済み）
        sender: 送信者情報（Noneならデフォルト使用）
        headless: ヘッドレスモードで実行するか

    Returns:
        {"status": str, "detail": str} の結果辞書
    """
    sender = sender or DEFAULT_SENDER
    domain = _get_domain(url)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            result = _process_company(
                page, url, domain, company_name, message, sender
            )
        except Exception as e:
            result = {"status": "error", "detail": str(e)}
            logger.error("送信処理エラー [%s]: %s", company_name, e)
        finally:
            browser.close()

    # DB記録
    save_result(company_name, url, result["status"], result["detail"])
    return result


def _process_company(
    page: Page,
    url: str,
    domain: str,
    company_name: str,
    message: str,
    sender: dict,
) -> dict:
    """1企業の送信処理本体

    Returns:
        {"status": str, "detail": str}
    """
    logger.info("=== 送信開始: %s ===", company_name)

    # キャッシュ確認
    cache = get_form_cache(domain)
    if cache:
        logger.info("キャッシュヒット: %s", domain)

    # ページアクセス
    page.goto(url, wait_until="domcontentloaded")
    html = page.content()

    # お問い合わせページへ遷移
    contact_url = find_contact_url(html, url)
    if contact_url and contact_url != url:
        page.goto(contact_url, wait_until="domcontentloaded")
        html = page.content()

    # CAPTCHA検出
    if detect_captcha(html):
        return {"status": "captcha", "detail": "CAPTCHA検出のためスキップ"}

    # フォーム解析
    forms = extract_forms(html)
    if not forms:
        return {"status": "no_form", "detail": "フォーム要素なし"}

    # 第1段階：BS4解析
    mapping = analyze_form(forms[0])

    # 第2段階：AI補完（BS4で不足がある場合）
    required = {"email", "message"}
    if not required.issubset(mapping.keys()):
        ai_result = analyze_form_with_ai(str(forms[0]))
        mapping = merge_mappings(mapping, ai_result)

    # フォーム入力
    if not _fill_form(page, mapping, message, sender):
        return {"status": "error", "detail": "フォーム入力失敗"}

    # 送信ボタン押下
    submit_sel = _find_submit_button(page, mapping)
    if not submit_sel:
        return {"status": "error", "detail": "送信ボタンが見つかりません"}

    page.click(submit_sel)
    time.sleep(POST_SUBMIT_WAIT)

    # 確認ページ対応
    if mapping.get("_confirm"):
        confirm_sel = _find_submit_button(page, {})
        if confirm_sel:
            page.click(confirm_sel)
            time.sleep(POST_SUBMIT_WAIT)

    # キャッシュ保存
    save_form_cache(domain, url, mapping, success=True)

    logger.info("送信成功: %s", company_name)
    return {"status": "success", "detail": "送信完了"}


def random_wait() -> float:
    """ランダムなウェイト時間を返す（秒）"""
    wait = random.uniform(WAIT_MIN, WAIT_MAX)
    logger.info("ウェイト: %.1f秒", wait)
    return wait
