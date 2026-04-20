"""自動送信エンジン - Playwrightでフォーム入力・送信を実行する

フォーム解析結果をもとにフィールドへ入力し送信する。
CAPTCHA・robots.txt・タイムアウトは安全にスキップする。
リトライ・同一ドメイン制限・拡張スキップ検出に対応。
"""

import logging
import random
import time
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

from config import PAGE_TIMEOUT, POST_SUBMIT_WAIT, WAIT_MAX, WAIT_MIN
from utils.ai_fallback import analyze_form_with_ai, merge_mappings
from utils.cms_detector import try_cms_mapping
from utils.db_cache import (
    get_form_cache, is_cache_reliable, save_form_cache,
    compute_html_signature, get_cache_by_signature,
)
from utils.form_analyzer import (
    analyze_form_bs4,
    build_virtual_form,
    check_robots_txt,
    detect_captcha,
    extract_contact_emails,
    find_contact_url,
    guess_contact_url,
    select_best_form,
)

logger = logging.getLogger(__name__)

# リトライ設定
MAX_RETRY = 3
RETRY_INTERVAL = 10  # 秒

# オプトアウト文言
OPT_OUT_TEXT = "\n\n※本メールが不要な場合はご連絡ください。以後の送信を停止いたします。"

# タイピング速度（ミリ秒）
TYPE_DELAY_MIN = 20
TYPE_DELAY_MAX = 80

# フィールド間移動待機（秒）
FIELD_MOVE_MIN = 0.1
FIELD_MOVE_MAX = 0.3

# 送信ボタンクリック前待機（秒）
PRE_SUBMIT_MIN = 0.5
PRE_SUBMIT_MAX = 1.5

# User-Agentリスト（主要ブラウザ最新版）
USER_AGENTS = [
    # Chrome最新版（Windows）
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome最新版（Mac）
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge最新版（Windows）
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Firefox最新版（Windows）
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def send_to_company(
    url: str,
    company_name: str,
    message: str,
    sender: Optional[dict] = None,
    headless: bool = False,
    dry_run: bool = False,
) -> dict:
    """1企業へフォーム送信を実行する（リトライ付き）

    Args:
        url: 企業WebサイトURL
        company_name: 企業名
        message: 送信メッセージ（置換済み）
        sender: 差出人情報辞書
        headless: ヘッドレスモードか
        dry_run: Trueなら送信ボタンを押さない

    Returns:
        {"status": str, "detail": str, "ai_used": bool,
         "cache_used": bool, "retry_count": int}
    """
    sender = sender or {}

    # robots.txtチェック
    if not check_robots_txt(url):
        return {
            "status": "robots_blocked",
            "detail": "robots.txtによりアクセス拒否",
            "ai_used": False,
            "cache_used": False,
            "retry_count": 0,
        }

    # オプトアウト文言付与
    full_message = message + OPT_OUT_TEXT

    # リトライループ
    last_result = None
    for attempt in range(MAX_RETRY):
        if attempt > 0:
            logger.info("リトライ %d/%d: %s", attempt, MAX_RETRY - 1, company_name)
            time.sleep(RETRY_INTERVAL)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            # ランダムUser-Agentを設定
            ua = random.choice(USER_AGENTS)
            context = browser.new_context(user_agent=ua)
            page = context.new_page()
            page.set_default_timeout(PAGE_TIMEOUT)
            logger.info("User-Agent: %s", ua[:60])

            try:
                result = _process(
                    page, url, company_name, full_message, sender, dry_run
                )
                result["retry_count"] = attempt
            except Exception as e:
                result = {
                    "status": "error",
                    "detail": str(e),
                    "ai_used": False,
                    "cache_used": False,
                    "retry_count": attempt,
                }
                logger.error("送信エラー [%s] (試行%d): %s", company_name, attempt + 1, e)
            finally:
                context.close()
                browser.close()

        last_result = result

        # 成功 or リトライ不要なステータスなら終了
        if result["status"] in ("success", "dry_run", "captcha",
                                 "no_form", "robots_blocked", "skip_spa",
                                 "skip_iframe", "skip_file_upload"):
            break

    return last_result


def _try_cached_mapping(domain: str) -> Optional[dict]:
    """キャッシュから信頼性の高いマッピングを取得する

    成功回数が十分かつ失敗率が低いキャッシュのみ返す。
    信頼性が低い場合はNoneを返し、再解析を促す。

    Args:
        domain: ドメイン名

    Returns:
        信頼できるマッピング辞書、なければNone
    """
    cache = get_form_cache(domain)
    if cache and is_cache_reliable(cache):
        logger.info(
            "キャッシュ使用: %s (成功%d/失敗%d)",
            domain, cache["success_count"], cache["fail_count"],
        )
        return cache["field_mapping"]
    return None


def _navigate_and_wait(page: Page, url: str) -> str:
    """ページにアクセスしてフォーム描画を待つ

    networkidleで読込し、タイムアウト時はdomcontentloadedにフォールバック。
    その後、form要素＋入力欄の描画を段階的に待機する。
    フォーム内入力要素が見つからない場合は追加待機でリトライ。

    Args:
        page: Playwrightのページ
        url: アクセス先URL

    Returns:
        ページのHTML文字列
    """
    try:
        page.goto(url, wait_until="networkidle", timeout=15000)
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded")
        except Exception:
            raise

    # 段階的にフォーム描画を待機
    _wait_for_form_render(page)

    return page.content()


def _wait_for_form_render(page: Page) -> None:
    """フォーム要素＋入力欄の描画を段階的に待つ

    1. form要素の出現を最大5秒待機
    2. form内のinput/textareaの出現を最大3秒待機
    3. 入力欄が見つからなければ追加で2秒待ってリトライ

    フォームなしサイトでタイムアウトしても例外は投げない。
    """
    # 1. form要素の出現を待つ
    try:
        page.wait_for_selector("form", timeout=5000)
    except Exception:
        return  # フォームなし → 終了

    # 2. form内の入力欄を待つ
    try:
        page.wait_for_selector(
            "form input:not([type='hidden']), form textarea",
            timeout=3000,
        )
        return  # 入力欄検出 → 完了
    except Exception:
        pass

    # 3. 追加待機リトライ（JS遅延描画への対応）
    try:
        page.wait_for_timeout(2000)
        page.wait_for_selector(
            "form input:not([type='hidden']), form textarea",
            timeout=3000,
        )
    except Exception:
        pass  # 最終的に見つからなくても続行


def _analyze_form_pipeline(
    html: str, target_form, domain: str
) -> tuple[dict, bool, bool]:
    """フォーム解析パイプライン（キャッシュ→CMS→BS4→AI）

    5段階の解析を順に試行し、最初に成功した結果を返す。

    Args:
        html: ページのHTMLテキスト
        target_form: 解析対象のform要素
        domain: ドメイン名

    Returns:
        (mapping, ai_used, cache_used) のタプル
    """
    # 1. 同一ドメインキャッシュ
    cached = _try_cached_mapping(domain)
    if cached:
        return cached, False, True

    # 2. クロスサイトキャッシュ（HTML署名一致）
    signature = compute_html_signature(target_form)
    if signature:
        cross_cache = get_cache_by_signature(signature)
        if cross_cache:
            logger.info("クロスサイトキャッシュ: 署名=%s", signature)
            return cross_cache["field_mapping"], False, True

    # 3. CMS検出マッピング
    cms_mapping = try_cms_mapping(html, target_form)

    # 4. BS4パターンマッチ
    bs4_mapping = analyze_form_bs4(target_form)

    # CMS + BS4をマージ（CMS優先）
    mapping = {**bs4_mapping, **cms_mapping} if cms_mapping else bs4_mapping

    # 5. AI補完（必須フィールド不足時）
    ai_used = False
    required = {"email", "message"}
    if not required.issubset(mapping.keys()):
        ai_result = analyze_form_with_ai(str(target_form))
        if ai_result:
            mapping = merge_mappings(mapping, ai_result)
            ai_used = True

    return mapping, ai_used, False


def _process(
    page: Page, url: str, company: str, message: str,
    sender: dict, dry_run: bool = False,
) -> dict:
    """送信処理の本体"""
    logger.info("=== 送信開始: %s ===", company)

    # ページアクセス（networkidle + フォーム待ち）
    html = _navigate_and_wait(page, url)

    # SPA検出
    if _detect_spa(html):
        return _skip_result("skip_spa", "SPA検出のためスキップ")

    # お問い合わせページへ遷移
    contact_url = find_contact_url(html, url)
    if not contact_url:
        # リンクが見つからない場合は直接URL推測
        contact_url = guess_contact_url(url)
    if contact_url and contact_url != url:
        html = _navigate_and_wait(page, contact_url)

    # CAPTCHA検出
    if detect_captcha(html):
        return _skip_result("captcha", "CAPTCHA検出のためスキップ")

    # フォーム抽出（検索フォーム除外 + スコアリング）
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    target_form = select_best_form(forms) if forms else None

    # <form>タグなしの場合、仮想フォーム構築を試行
    if not target_form:
        target_form = build_virtual_form(soup)

    if not target_form:
        emails = extract_contact_emails(html)
        return _skip_result("no_form", "コンタクトフォーム要素なし", emails)

    # iframe内フォーム検出
    if _detect_iframe_form(html):
        return _skip_result("skip_iframe", "iframe内フォームのためスキップ")

    # ファイルアップロード検出
    if _detect_file_upload(target_form):
        return _skip_result("skip_file_upload", "ファイルアップロード必須のためスキップ")

    # ドメイン抽出（遷移後のURLを使用）
    domain = urlparse(page.url).netloc

    # 解析パイプライン（キャッシュ→CMS→BS4→AI）
    mapping, ai_used, cache_used = _analyze_form_pipeline(
        html, target_form, domain
    )

    # マッピングが空（メタ情報除く）→ コンタクトフォームではない
    valid_fields = [k for k in mapping if not k.startswith("_")]
    if not valid_fields:
        emails = extract_contact_emails(html)
        return _skip_result("no_form", "コンタクトフォーム項目なし", emails)

    # フォーム入力
    if not _fill_form(page, mapping, message, sender):
        save_form_cache(domain, page.url, mapping, success=False)
        return _error_result("フォーム入力失敗", ai_used, cache_used)

    # 送信ボタン検索
    submit_sel = _find_submit(page, mapping)
    if not submit_sel:
        save_form_cache(domain, page.url, mapping, success=False)
        return _error_result("送信ボタンなし", ai_used, cache_used)

    # ドライラン: 送信ボタンを押さずに終了
    if dry_run:
        save_form_cache(domain, page.url, mapping, success=True)
        fields = [k for k in mapping if not k.startswith("_")]
        detail = f"ドライラン完了（解析:{','.join(fields)}）"
        logger.info("ドライラン: %s - %s", company, detail)
        return {
            "status": "dry_run", "detail": detail,
            "ai_used": ai_used, "cache_used": cache_used,
        }

    # 送信実行
    return _execute_submit(
        page, submit_sel, mapping, domain, company, ai_used, cache_used
    )


def _execute_submit(
    page: Page, submit_sel: str, mapping: dict,
    domain: str, company: str, ai_used: bool, cache_used: bool,
) -> dict:
    """送信ボタンクリック・確認画面対応・キャッシュ保存"""
    pre_wait = random.uniform(PRE_SUBMIT_MIN, PRE_SUBMIT_MAX)
    logger.info("送信前待機: %.1f秒", pre_wait)
    time.sleep(pre_wait)

    page.click(submit_sel)
    time.sleep(POST_SUBMIT_WAIT)

    # 確認画面対応
    if mapping.get("_confirm"):
        confirm_sel = _find_submit(page, {})
        if confirm_sel:
            page.click(confirm_sel)
            time.sleep(POST_SUBMIT_WAIT)

    # 送信成功 → キャッシュ保存
    save_form_cache(domain, page.url, mapping, success=True)

    logger.info("送信成功: %s", company)
    return {
        "status": "success", "detail": "送信完了",
        "ai_used": ai_used, "cache_used": cache_used,
    }


def _skip_result(status: str, detail: str, emails: Optional[list] = None) -> dict:
    """スキップ系の結果辞書を生成する（キャッシュ保存なし）

    Args:
        status: ステータス名
        detail: 詳細メッセージ
        emails: 手動対応用のメールアドレスリスト（no_form時等）
    """
    result = {
        "status": status, "detail": detail,
        "ai_used": False, "cache_used": False,
    }
    if emails:
        result["detail"] = f"{detail} / 連絡先: {', '.join(emails[:3])}"
        result["contact_emails"] = emails
    return result


def _error_result(detail: str, ai_used: bool, cache_used: bool) -> dict:
    """エラー系の結果辞書を生成する"""
    return {
        "status": "error", "detail": detail,
        "ai_used": ai_used, "cache_used": cache_used,
    }


def _fill_form(
    page: Page, mapping: dict, message: str, sender: dict
) -> bool:
    """マッピングに基づいてフォームに値を入力する"""
    values = {
        "company": sender.get("company", ""),
        "last_name": sender.get("last_name", ""),
        "first_name": sender.get("first_name", ""),
        "name": sender.get("name", ""),
        "last_kana": sender.get("last_kana", ""),
        "first_kana": sender.get("first_kana", ""),
        "kana": sender.get("kana", ""),
        "email": sender.get("email", ""),
        "phone": sender.get("phone", ""),
        "postal": sender.get("postal", ""),
        "address": sender.get("address", ""),
        "subject": sender.get("subject", "ご提案のご連絡"),
        "message": message,
    }

    filled = 0
    for ftype, finfo in mapping.items():
        if ftype.startswith("_"):
            continue
        value = values.get(ftype, "")
        if not value or not finfo.get("name"):
            continue

        sel = f'[name="{finfo["name"]}"]'
        if _fill_field(page, sel, ftype, value, filled):
            filled += 1

    return filled > 0


def _fill_field(
    page: Page, sel: str, ftype: str, value: str, filled_count: int
) -> bool:
    """単一フィールドに値を入力する（可視化・フォールバック・検証付き）

    優先順位:
    1. scroll_into_view → click → page.type（通常入力）
    2. elem.fill()（force入力・非表示要素用フォールバック）
    3. 入力後の値検証（input_value確認）

    Args:
        page: Playwrightのページ
        sel: フィールドのCSSセレクタ
        ftype: フィールドタイプ名（ログ用）
        value: 入力値
        filled_count: すでに入力済みのフィールド数

    Returns:
        入力成功（値検証OK）ならTrue
    """
    elem = page.query_selector(sel)
    if not elem:
        return False

    # フィールド間移動の待機
    if filled_count > 0:
        time.sleep(random.uniform(FIELD_MOVE_MIN, FIELD_MOVE_MAX))

    # 1. 通常入力（scroll+click+type）
    typed_ok = _try_type_input(page, elem, sel, value)

    # 2. フォールバック: fill（非表示要素でも値をセット）
    if not typed_ok:
        try:
            elem.fill(value, timeout=3000)
            typed_ok = True
        except Exception as e:
            logger.debug("fill失敗 [%s]: %s", ftype, str(e)[:80])

    # 3. 最終フォールバック: JavaScript直接セット + イベント発火
    if not typed_ok:
        typed_ok = _try_js_set_value(page, elem, value)

    if not typed_ok:
        logger.warning("入力失敗 [%s]: 全手法失敗", ftype)
        return False

    # 4. 入力後検証（値が実際にセットされたか確認）
    if not _verify_field_value(elem, value):
        logger.warning("入力検証失敗 [%s]: 値がセットされていない", ftype)
        return False

    logger.info("入力: %s", ftype)
    return True


def _try_js_set_value(page: Page, elem, value: str) -> bool:
    """JavaScriptで値を直接セットし、input/changeイベントを発火する

    React/Vue等のフレームワークはnative setterを使わないと検知しないため、
    prototype setterを明示的に呼び出してイベント発火する。

    Args:
        page: Playwrightのページ
        elem: 対象要素のElementHandle
        value: セットする値

    Returns:
        成功ならTrue
    """
    try:
        elem.evaluate(
            """(el, val) => {
                const setter = Object.getOwnPropertyDescriptor(
                    el.tagName === 'TEXTAREA'
                        ? HTMLTextAreaElement.prototype
                        : HTMLInputElement.prototype,
                    'value'
                ).set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""",
            value,
        )
        return True
    except Exception as e:
        logger.debug("JS直接セット失敗: %s", str(e)[:80])
        return False


def _try_type_input(page: Page, elem, sel: str, value: str) -> bool:
    """通常入力（scroll+click+type）を試行する"""
    try:
        elem.scroll_into_view_if_needed(timeout=2000)
        elem.click(timeout=3000)
        delay = random.uniform(TYPE_DELAY_MIN, TYPE_DELAY_MAX)
        page.type(sel, value, delay=delay, timeout=5000)
        return True
    except Exception as e:
        logger.debug("通常入力失敗: %s", str(e)[:80])
        return False


def _verify_field_value(elem, expected: str) -> bool:
    """フィールドに値が実際にセットされたか検証する

    textareaとinputで値取得方法が異なる場合があるため両方試行。
    完全一致でなく、先頭10文字で判定（長文テキストの切り詰め対応）。
    """
    try:
        actual = elem.input_value()
        if not actual:
            return False
        # 先頭10文字（または全長）で一致確認
        check_len = min(10, len(expected))
        return actual[:check_len] == expected[:check_len]
    except Exception:
        # input_value()が使えない要素は検証スキップ（成功扱い）
        return True


def _find_submit(page: Page, mapping: dict) -> Optional[str]:
    """送信ボタンのセレクタを探す（拡張版）

    検索順序:
    1. AIが指定したセレクタ（_submit）
    2. 標準的なtype="submit"のinput/button
    3. 日本語テキストの各種ボタン（送信・確認・問い合わせる等）
    4. value属性マッチ
    5. aタグ・画像ボタン・class属性マッチ（フォールバック）
    """
    if "_submit" in mapping:
        return mapping["_submit"]

    # 優先度の高い候補から順にチェック
    for sel in _SUBMIT_SELECTORS:
        if page.query_selector(sel):
            return sel
    return None


# 送信ボタン検出セレクタ（優先度順）
_SUBMIT_SELECTORS = [
    # 標準的なsubmit要素
    'input[type="submit"]',
    'button[type="submit"]',
    'input[type="image"]',
    # 日本語テキストボタン
    'button:has-text("送信")',
    'button:has-text("確認")',
    'button:has-text("確認する")',
    'button:has-text("確認画面")',
    'button:has-text("問い合わせる")',
    'button:has-text("お問い合わせ")',
    'button:has-text("相談する")',
    'button:has-text("申し込む")',
    'button:has-text("お申込")',
    'button:has-text("申込")',
    'button:has-text("次へ")',
    'button:has-text("進む")',
    'button:has-text("Send")',
    'button:has-text("Submit")',
    # value属性
    'input[value="送信"]',
    'input[value="確認"]',
    'input[value="確認する"]',
    'input[value="問い合わせる"]',
    'input[value="お申し込み"]',
    'input[value="申し込む"]',
    'input[value*="送信"]',
    'input[value*="確認"]',
    # class属性フォールバック
    'button[class*="submit"]',
    'button[class*="send"]',
    'button[class*="form-submit"]',
    # aタグボタン
    'a[role="button"]:has-text("送信")',
    'a[role="button"]:has-text("確認")',
    'a[role="button"]:has-text("問い合わせ")',
    'a[class*="btn"]:has-text("送信")',
    'a[class*="btn"]:has-text("確認")',
    'a[class*="btn"]:has-text("問い合わせ")',
]


def _detect_spa(html: str) -> bool:
    """SPA（Single Page Application）を検出する

    JSフレームワークのルートのみでコンテンツが少ないケース。
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    if not body:
        return False

    # テキストが極端に少ない＋script多数 → SPAの可能性
    text_len = len(body.get_text(strip=True))
    scripts = body.find_all("script")
    if text_len < 100 and len(scripts) > 5:
        logger.info("SPA検出: テキスト%d文字, script%d個", text_len, len(scripts))
        return True
    return False


def _detect_iframe_form(html: str) -> bool:
    """iframe内にフォームが埋め込まれているか検出する"""
    soup = BeautifulSoup(html, "html.parser")
    iframes = soup.find_all("iframe")
    for iframe in iframes:
        src = iframe.get("src", "")
        # Google Forms, Typeform, HubSpot等の外部フォーム
        if any(k in src for k in [
            "forms.google", "typeform.com", "hubspot",
            "formrun.com", "form.run", "docs.google",
        ]):
            logger.info("iframe内フォーム検出: %s", src[:80])
            return True
    return False


def _detect_file_upload(form) -> bool:
    """フォームにファイルアップロード必須フィールドがあるか検出する"""
    file_inputs = form.find_all("input", {"type": "file"})
    for fi in file_inputs:
        # BS4はrequired属性を空文字として返すのでhas_attrで判定
        if fi.has_attr("required"):
            logger.info("ファイルアップロード必須検出")
            return True
    return False


def random_wait(base_interval: Optional[float] = None) -> float:
    """設定値を中心にランダム幅を持たせたウェイト時間を返す（秒）

    base_intervalが指定された場合、その値を基準に0.8〜1.5倍のランダム値を返す。
    未指定の場合はWAIT_MIN〜WAIT_MAXのレガシー動作。

    Args:
        base_interval: 基準となる送信間隔（秒）。Noneの場合はWAIT_MIN/MAX使用。

    Returns:
        ランダム化されたウェイト時間（秒）
    """
    if base_interval is not None:
        wait_min = base_interval * 0.8
        wait_max = base_interval * 1.5
        wait = random.uniform(wait_min, wait_max)
    else:
        wait = random.uniform(WAIT_MIN, WAIT_MAX)
    logger.info("ウェイト: %.1f秒", wait)
    return wait
