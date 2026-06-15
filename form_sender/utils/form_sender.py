"""自動送信エンジン - Playwrightでフォーム入力・送信を実行する

フォーム解析結果をもとにフィールドへ入力し送信する。
CAPTCHA・robots.txt・タイムアウトは安全にスキップする。
リトライ・同一ドメイン制限・拡張スキップ検出に対応。
Windows + Streamlit環境でPlaywrightがsubprocess起動できるように、
専用スレッドでProactorEventLoopを使う仕組みを実装。
"""

import asyncio
import logging
import random
import re
import sys
import threading
import time

# CSSのID選択子として有効な文字列パターン
_CSS_ID_RE = re.compile(r'^[a-zA-Z_\-][a-zA-Z0-9_\-]*$')
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright

# Windows環境ではProactorEventLoopを既定にする（subprocess対応のため）
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from config import GEMINI_API_KEY, PAGE_TIMEOUT, POST_SUBMIT_WAIT, WAIT_MAX, WAIT_MIN
from utils.ai_fallback import analyze_form_with_ai, merge_mappings


def _session_state_has_key() -> bool:
    """Streamlit session_stateにGemini APIキーが設定されているか確認する"""
    try:
        import streamlit as st
        return bool(st.session_state.get("gemini_api_key", ""))
    except Exception:
        return False


def _get_gemini_api_key() -> str:
    """Gemini APIキーを取得する（session_state → DB → .env の優先順で確認）

    1. Streamlit session_state（設定画面で入力・同セッション内）
    2. SQLite DB（設定画面で保存済み・永続）
    3. .env / 環境変数

    Returns:
        APIキー文字列（未設定なら空文字）
    """
    # 1. Streamlit session_state から取得
    try:
        import streamlit as st
        key = st.session_state.get("gemini_api_key", "")
        if key:
            return key
    except Exception:
        pass
    # 2. SQLite DB から取得（設定画面で「APIキーを保存」した値）
    try:
        from utils.db_logs import get_setting
        key = get_setting("gemini_api_key", "")
        if key:
            return key
    except Exception:
        pass
    # 3. 環境変数から取得（.envからload_dotenv済み、設定画面保存時に即時反映）
    import os
    return os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY)
from utils.captcha_detector import detect_captcha_info
from utils.captcha_solver import solve_captcha
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
MAX_RETRY = 1
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
    """1企業へフォーム送信を実行する（Streamlit対応・スレッド分離付き）

    Streamlit環境ではメインスレッドのevent loop制約でPlaywrightが
    subprocess起動できないため、専用スレッドで実行する。
    """
    # 別スレッドで実行（ProactorEventLoopを使うため）
    result_holder: dict = {}
    error_holder: list = []

    def _worker():
        # スレッド内で新規ProactorEventLoopをセット
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)
        try:
            result_holder["result"] = _send_to_company_impl(
                url, company_name, message, sender, headless, dry_run,
            )
        except Exception as e:
            error_holder.append(e)
            logger.error("送信スレッドエラー: %s", e)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()

    if error_holder:
        return {
            "status": "error",
            "detail": str(error_holder[0]),
            "ai_used": False,
            "cache_used": False,
            "captcha_solved": False,
            "retry_count": 0,
        }
    return result_holder.get("result", {
        "status": "error", "detail": "不明エラー",
        "ai_used": False, "cache_used": False,
        "captcha_solved": False, "retry_count": 0,
    })


def _send_to_company_impl(
    url: str,
    company_name: str,
    message: str,
    sender: Optional[dict] = None,
    headless: bool = False,
    dry_run: bool = False,
) -> dict:
    """1企業へフォーム送信を実行する（リトライ付き・実装本体）

    Args:
        url: 企業WebサイトURL
        company_name: 企業名
        message: 送信メッセージ（置換済み）
        sender: 差出人情報辞書
        headless: ヘッドレスモードか
        dry_run: Trueなら送信ボタンを押さない

    Returns:
        {"status": str, "detail": str, "ai_used": bool,
         "cache_used": bool, "captcha_solved": bool, "retry_count": int}
    """
    sender = sender or {}

    # robots.txtチェック
    if not check_robots_txt(url):
        return {
            "status": "robots_blocked",
            "detail": "robots.txtによりアクセス拒否",
            "ai_used": False,
            "cache_used": False,
            "captcha_solved": False,
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
                    "captcha_solved": False,
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

    1. スクロールでlazy-loadトリガー（Contact Form 7等の遅延描画対応）
    2. form要素の出現を最大8秒待機（旧5秒→延長）
    3. form内のinput/textareaの出現を最大5秒待機（旧3秒→延長）
    4. 入力欄が見つからなければ追加3秒待ってリトライ（旧2秒→延長）

    フォームなしサイトでタイムアウトしても例外は投げない。
    """
    # 0. スクロールでlazy-loadを発火してからトップに戻る
    try:
        page.evaluate(
            "window.scrollTo(0, Math.min(600, document.body.scrollHeight))"
        )
        page.wait_for_timeout(400)
        page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass

    # 1. form要素の出現を待つ（8秒に延長）
    try:
        page.wait_for_selector("form", timeout=8000)
    except Exception:
        return  # フォームなし → 終了

    # 2. form内の入力欄を待つ（5秒に延長）
    try:
        page.wait_for_selector(
            "form input:not([type='hidden']), form textarea",
            timeout=5000,
        )
        return  # 入力欄検出 → 完了
    except Exception:
        pass

    # 3. 追加待機リトライ（JS遅延描画への対応、3秒待機後5秒リトライ）
    try:
        page.wait_for_timeout(3000)
        page.wait_for_selector(
            "form input:not([type='hidden']), form textarea",
            timeout=5000,
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

    # 5. AI補完（強化版トリガー条件）
    # 以下のいずれかに該当する場合にGemini AIで解析・補完する:
    #   a) 必須フィールド（email/message）が不足している
    #   b) フリガナ系フィールドがある（文字種エラーが起きやすい）
    #   c) 5フィールド以上の複雑なフォーム（住所・氏名分割等）
    #   d) postal + address の両方がある（住所自動補完フォーム）
    ai_used = False
    gemini_key = _get_gemini_api_key()  # session_state → .env の順で確認
    if gemini_key:
        required = {"email", "message"}
        valid_fields = {k for k in mapping if not k.startswith("_")}
        has_kana = bool({"kana", "kana_first", "kana_last"} & valid_fields)
        has_address_set = {"postal", "address"}.issubset(valid_fields)
        is_complex = len(valid_fields) >= 5
        needs_ai = (
            not required.issubset(valid_fields)
            or has_kana
            or is_complex
            or has_address_set
        )
        if needs_ai:
            # AI呼び出し理由をログに出力（デバッグ用）
            reasons = []
            if not required.issubset(valid_fields):
                reasons.append("必須フィールド不足")
            if has_kana:
                reasons.append("フリガナあり")
            if is_complex:
                reasons.append(f"フィールド{len(valid_fields)}個")
            if has_address_set:
                reasons.append("住所セット")
            logger.info("Gemini AI解析開始（理由: %s）", ", ".join(reasons))
            ai_result = analyze_form_with_ai(str(target_form))
            if ai_result:
                mapping = merge_mappings(mapping, ai_result)
                ai_used = True
                logger.info("Gemini AI解析完了: マッピング補完")
            else:
                logger.warning("Gemini AI解析失敗（APIエラーまたはキー不正）")
        else:
            logger.info(
                "Gemini AI: シンプルなフォーム（%d フィールド）のためスキップ",
                len(valid_fields),
            )
    else:
        logger.warning(
            "Gemini APIキー未確認: AI解析をスキップします"
        )

    return mapping, ai_used, False


def _process(
    page: Page, url: str, company: str, message: str,
    sender: dict, dry_run: bool = False,
) -> dict:
    """送信処理の本体"""
    logger.info("=== 送信開始: %s ===", company)

    # Gemini API設定状況をログ出力（クライアント環境の確認用）
    gemini_key = _get_gemini_api_key()
    if gemini_key:
        src = "session_state" if (
            _session_state_has_key()
        ) else ".env"
        logger.info(
            "Gemini API: 設定済み（ソース=%s, キー末尾=...%s）",
            src, gemini_key[-4:],
        )
    else:
        logger.warning(
            "Gemini API: 未設定 → AI解析無効（BS4のみ）。"
            "設定画面またはGEMINI_API_KEY環境変数を確認してください。"
        )

    # ページアクセス（networkidle + フォーム待ち）
    html = _navigate_and_wait(page, url)

    # SPA検出
    if _detect_spa(html):
        return _skip_result("skip_spa", "SPA検出のためスキップ")

    # フォームが既存ページにあればURL探索をスキップ（Fix C）
    soup_check = BeautifulSoup(html, "html.parser")
    has_form_already = bool(soup_check.find_all("form"))

    if not has_form_already:
        # お問い合わせページへ遷移
        contact_url = find_contact_url(html, url)
        if not contact_url:
            # リンクが見つからない場合は直接URL推測
            contact_url = guess_contact_url(url)
        if contact_url and contact_url != url:
            html = _navigate_and_wait(page, contact_url)

    # CAPTCHA検出・解決（2Captcha連携）
    captcha_info = detect_captcha_info(html)
    captcha_solved = False
    if captcha_info["present"]:
        if captcha_info["type"] == "unknown" or not captcha_info.get("sitekey"):
            # type不明 = HTML中に"captcha"文字列があるだけでCAPTCHA確定できない
            # （CF7プラグインのCSSクラス名等による誤検出が多いため）スキップせず続行
            logger.info("CAPTCHA種別不明（誤検出の可能性あり） → フォーム処理続行")
        else:
            solve = solve_captcha(page, page.url, captcha_info)
            if not solve["solved"]:
                return _skip_result(
                    "captcha",
                    f"CAPTCHA解決失敗: {solve['error']}",
                )
            captcha_solved = True
            logger.info(
                "CAPTCHA解決成功: %s %.1fs %.2f円",
                captcha_info["type"], solve["elapsed_sec"], solve["cost_jpy"],
            )

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

    # 送信ボタンの有効化を待つ（wpcf7 disabled対応）
    _wait_for_submit_enabled(page, submit_sel)

    # ドライラン: 送信ボタンを押さずに終了
    if dry_run:
        save_form_cache(domain, page.url, mapping, success=True)
        fields = [k for k in mapping if not k.startswith("_")]
        detail = f"ドライラン完了（解析:{','.join(fields)}）"
        logger.info("ドライラン: %s - %s", company, detail)
        return {
            "status": "dry_run", "detail": detail,
            "ai_used": ai_used, "cache_used": cache_used,
            "captcha_solved": captcha_solved,
        }

    # 送信実行
    result = _execute_submit(
        page, submit_sel, mapping, domain, company,
        ai_used, cache_used, captcha_solved,
    )

    # バリデーションエラー後のAIリトライ
    # AI未使用で失敗した場合のみ実行（二重送信防止のため submitted_unverified は除外）
    if (
        result["status"] == "error"
        and not result.get("ai_used")
        and not captcha_solved      # CAPTCHA解決済みサイトは再試行不可
        and _get_gemini_api_key()   # session_state → .env の順で確認
    ):
        logger.info("AIリトライ開始: %s（BS4失敗 → AI再解析）", company)
        try:
            # ページをリロードしてフォームをリセット
            html_retry = _navigate_and_wait(page, page.url)
            soup_retry = BeautifulSoup(html_retry, "html.parser")
            forms_retry = soup_retry.find_all("form")
            form_retry = select_best_form(forms_retry) if forms_retry else None
            if not form_retry:
                form_retry = build_virtual_form(soup_retry)

            if form_retry:
                # AIで強制解析（BS4結果を上書き）
                ai_result = analyze_form_with_ai(str(form_retry))
                if ai_result:
                    ai_mapping = merge_mappings(mapping, ai_result)
                    if _fill_form(page, ai_mapping, message, sender):
                        submit_sel2 = _find_submit(page, ai_mapping)
                        if submit_sel2:
                            _wait_for_submit_enabled(page, submit_sel2)
                            logger.info("AIリトライ: フォーム入力完了 → 再送信")
                            result = _execute_submit(
                                page, submit_sel2, ai_mapping, domain, company,
                                True, False, captcha_solved,
                            )
        except Exception as e:
            logger.warning("AIリトライ中にエラー: %s", str(e)[:80])

    return result


def _execute_submit(
    page: Page, submit_sel: str, mapping: dict,
    domain: str, company: str, ai_used: bool, cache_used: bool,
    captcha_solved: bool = False,
) -> dict:
    """送信ボタンクリック・確認画面対応・完了検証付きキャッシュ保存

    送信フロー:
    1. 「入力 → 確認 → 完了」型に対応（最大3段階）
    2. 各クリック後にURL・タイトル・ボディの3段階で完了を判定
    3. フォーム残存検知でバリデーションエラーを正確分類
    """
    pre_wait = random.uniform(PRE_SUBMIT_MIN, PRE_SUBMIT_MAX)
    logger.info("送信前待機: %.1f秒", pre_wait)
    time.sleep(pre_wait)

    url_before = page.url
    # 確認画面を経由したかどうかのフラグ
    # 確認画面を経由した場合はフォーム残存チェックをスキップする
    passed_confirmation = False

    # ステップ1: 1回目のクリック（多くは「確認画面へ」もしくは「送信」）
    _click_submit(page, submit_sel)
    _wait_after_submit(page)

    # 最大2回まで確認画面のステップを進める
    for step in range(2):
        # URL・タイトル・ボディの3段階で完了を判定（最優先）
        if _check_page_completion(page):
            save_form_cache(domain, page.url, mapping, success=True)
            logger.info("送信成功（完了確認）: %s", company)
            return {
                "status": "success", "detail": "送信完了（完了画面確認）",
                "ai_used": ai_used, "cache_used": cache_used,
                "captcha_solved": captcha_solved,
            }

        body = _get_body_text(page)

        # 確認画面チェック（エラー検出より先にチェック）
        # ※確認画面にも「入力してください」等の文言が含まれる場合があるため
        if _is_confirmation_page(body):
            confirm_sel = _find_confirm_button(page)
            if confirm_sel:
                logger.info("確認画面検出 → 送信ボタン押下 (%s)", confirm_sel)
                _click_submit(page, confirm_sel)
                _wait_after_submit(page)
                passed_confirmation = True  # 確認画面を経由したことを記録
                continue

        # エラー画面チェック（バリデーション失敗等）
        if _is_error_page(body):
            save_form_cache(domain, page.url, mapping, success=False)
            logger.warning("送信エラー検出（キーワード）: %s", company)
            return {
                "status": "error",
                "detail": "サイト側でバリデーションエラー検出",
                "ai_used": ai_used, "cache_used": cache_used,
                "captcha_solved": captcha_solved,
            }

        # 確認画面でも完了画面でもない → 完了未確認
        break

    # 最終チェック（URL・タイトル・ボディ）
    if _check_page_completion(page):
        save_form_cache(domain, page.url, mapping, success=True)
        logger.info("送信成功（最終確認）: %s", company)
        return {
            "status": "success", "detail": "送信完了",
            "ai_used": ai_used, "cache_used": cache_used,
            "captcha_solved": captcha_solved,
        }

    # フォームがまだ表示されていればバリデーションエラーの可能性
    # ただし確認画面を経由した場合はスキップ（確認画面のフォームが残っている誤検知を防ぐ）
    # （URLが変わっていない + フォーム残存 + 確認画面未経由 = 送信が通っていない）
    url_after = page.url
    if not passed_confirmation and url_before == url_after and _is_form_still_visible(page):
        # バリデーションエラーの詳細をログに記録
        errors = _extract_validation_errors(page)
        if errors:
            for field, msg in errors:
                logger.warning("  バリデーションエラー詳細 [%s]: %s", field, msg)
        else:
            logger.warning("  バリデーションエラー詳細: 取得できず（JS動的表示の可能性）")
        save_form_cache(domain, page.url, mapping, success=False)
        logger.warning("バリデーションエラー（フォーム残存）: %s", company)
        detail = "送信後もフォームが残存（バリデーションエラーの可能性）"
        if errors:
            detail += " / " + " | ".join(f"{f}:{m}" for f, m in errors[:3])
        return {
            "status": "error",
            "detail": detail,
            "ai_used": ai_used, "cache_used": cache_used,
            "captcha_solved": captcha_solved,
        }

    # 完了確認できず（uncertain）
    save_form_cache(domain, page.url, mapping, success=False)
    logger.warning("送信完了確認できず: %s", company)
    return {
        "status": "submitted_unverified",
        "detail": "送信ボタンは押したが完了画面を確認できず（要手動確認）",
        "ai_used": ai_used, "cache_used": cache_used,
        "captcha_solved": captcha_solved,
    }


def _extract_validation_errors(page: Page) -> list[tuple[str, str]]:
    """フォームのバリデーションエラーメッセージを取得する

    以下の方法でエラーを検出する:
    1. aria-invalid="true" の入力欄とその関連エラーメッセージ
    2. エラー系クラス名を持つ要素（error/invalid/alert等）のテキスト
    3. 必須入力が空のまま残っている入力欄名

    Args:
        page: Playwrightのページ

    Returns:
        [(フィールド名またはセレクタ, エラーメッセージ)] のリスト
    """
    try:
        errors = page.evaluate(
            """() => {
                const results = [];

                // 1. aria-invalid な入力欄を探す
                document.querySelectorAll(
                    'input[aria-invalid="true"], textarea[aria-invalid="true"], '
                    + 'select[aria-invalid="true"]'
                ).forEach(el => {
                    const fieldId = el.name || el.id || el.type || '不明';
                    // aria-describedby でエラーメッセージ要素を特定
                    let msg = '';
                    const descId = el.getAttribute('aria-describedby');
                    if (descId) {
                        const descEl = document.getElementById(descId);
                        if (descEl) msg = descEl.textContent.trim();
                    }
                    // 次の兄弟要素にエラーが書いてあることも多い
                    if (!msg) {
                        const next = el.nextElementSibling;
                        if (next && next.textContent.trim().length < 100)
                            msg = next.textContent.trim();
                    }
                    if (!msg) msg = '（エラー内容不明）';
                    results.push([fieldId, msg]);
                });

                // 2. エラー系クラスを持つ要素のテキスト
                const errorSelectors = [
                    '.error', '.is-error', '.has-error', '.invalid',
                    '.wpcf7-not-valid-tip',    // Contact Form 7
                    '.mw_wp_form_error',        // MW WP Form
                    '[class*="error-message"]', '[class*="error_message"]',
                    '[class*="errorMessage"]',  '[class*="ErrorMessage"]',
                    '[class*="validation"]',    '[role="alert"]',
                    '.form-error', '.field-error', '.input-error',
                ];
                errorSelectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const text = el.textContent.trim();
                        if (!text || text.length > 150) return;
                        // 近くの入力欄名を探す
                        const input = el.previousElementSibling
                            || el.closest('.form-group, .field, .form-field, tr, li')
                                ?.querySelector('input,textarea,select');
                        const fieldId = input
                            ? (input.name || input.id || input.type || sel)
                            : sel;
                        // 重複を避ける
                        if (!results.some(r => r[1] === text)) {
                            results.push([fieldId, text]);
                        }
                    });
                });

                // 3. required で空のまま残っている入力欄
                document.querySelectorAll(
                    'input[required]:not([type=hidden]):not([type=submit]),'
                    + 'textarea[required], select[required]'
                ).forEach(el => {
                    const val = el.value ? el.value.trim() : '';
                    if (!val) {
                        const fieldId = el.name || el.id || el.type || '?';
                        if (!results.some(r => r[0] === fieldId)) {
                            results.push([fieldId, '必須項目が未入力']);
                        }
                    }
                });

                return results.slice(0, 10);  // 最大10件
            }"""
        )
        return [(str(f), str(m)) for f, m in (errors or [])]
    except Exception as e:
        logger.debug("バリデーションエラー取得失敗: %s", str(e)[:80])
        return []


def _click_submit(page: Page, sel: str) -> None:
    """送信ボタンをクリックする（scroll → 通常 → force → JSの順でフォールバック）

    通常クリック失敗時は force:true → JSクリックの順で試みる。
    クリック前にスクロールして要素をビューポート内に入れる。

    Args:
        page: Playwrightのページ
        sel: 送信ボタンのCSSセレクタ
    """
    # まずスクロールしてボタンをビューポート内に入れる
    try:
        page.locator(sel).first.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    # ① 通常クリック
    try:
        page.click(sel, timeout=5000)
        return
    except Exception:
        pass

    # ② force:true クリック（オーバーレイ等で通常クリックが通らない場合）
    logger.warning("通常クリック失敗 → force:trueでリトライ: %s", sel)
    try:
        page.click(sel, timeout=3000, force=True)
        return
    except Exception:
        pass

    # ③ JSクリック（最終手段）
    logger.warning("force:trueも失敗 → JSクリックにフォールバック: %s", sel)
    try:
        page.evaluate(
            f"const el = document.querySelector({repr(sel)}); if(el) el.click();"
        )
    except Exception as e:
        logger.warning("JSクリックも失敗: %s", str(e)[:80])
        raise


def _wait_after_submit(page: Page) -> None:
    """送信ボタンクリック後の遷移を待つ（タイムアウト許容）"""
    time.sleep(POST_SUBMIT_WAIT)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass


def _get_body_text(page: Page) -> str:
    """ページのbodyテキストを取得する（小文字化）"""
    try:
        text = page.evaluate("document.body.innerText") or ""
    except Exception:
        text = ""
    return text.lower()


# 送信完了画面のキーワード（小文字）
_COMPLETION_KEYWORDS = [
    "送信完了", "送信されました", "送信しました",
    "ありがとうございました", "ありがとうございます",
    "受け付けました", "受付完了", "受付けました",
    "完了しました", "完了いたしました",
    "お問い合わせを受け付け", "問い合わせを受け付け",
    "お問い合わせいただき", "お問い合わせいただきありがとう",
    "いただきありがとう",
    "承りました", "拝受しました",
    "送信が完了", "フォームの送信",
    "確認次第ご連絡", "ご返信いたします",
    "担当者よりご連絡",
    # 追加：日本語完了表現パターン
    "以下の内容を受信", "以下の内容でお問い合わせ",
    "内容を承りました", "内容を受け付け",
    "ご連絡いただきありがとう", "ご連絡ありがとうございます",
    "お問い合わせありがとうございます",
    "メッセージを受信", "メッセージを承りました",
    "送信のお知らせ", "送信が正常に", "正常に送信",
    "折り返しご連絡", "折り返しご対応",
    "近日中にご連絡", "後日ご連絡",
    "自動返信メールを送信", "確認メールを送信",
    "入力内容を送信しました",
    # 追加：英語完了表現パターン
    "thank you", "thanks for", "we have received",
    "successfully sent", "submission complete",
    "complete", "completed", "successful",
    "your message has been", "message received",
    "has been submitted", "been sent",
    "form submitted", "inquiry received",
    "we will get back", "will contact you",
    "your inquiry", "your message",
]

# 完了URLパスキーワード（遷移後のURLで判定）
_COMPLETION_URL_KEYWORDS = [
    "thanks", "thank-you", "thankyou", "thank_you",
    "complete", "completed", "completion",
    "success", "successful", "succeeded",
    "done", "finish", "finished",
    "sent", "submit-success", "form-success",
    "/kanryo", "/done", "/finish", "/thanks",
    "toriauke", "uketsuke",
    # 追加：日本語URLパターン
    "kanryo", "kansei", "soushin", "jusin",
    "complete.php", "complete.html", "thanks.php", "thanks.html",
    "finish.php", "finish.html", "done.php", "done.html",
    "confirm-complete", "send-complete", "mail-complete",
]

# 確認画面のキーワード（小文字）
_CONFIRMATION_KEYWORDS = [
    "入力内容を確認", "入力内容のご確認", "ご確認ください",
    "確認画面", "内容確認", "以下の内容で",
    "上記の内容で", "送信前の確認",
    "送信内容のご確認", "確認してください",
    "please confirm", "confirm your",
]

# エラー画面のキーワード（小文字）
# ※「入力してください」「必須項目」は案内文として元フォームに書かれているため除外
# ※「please enter」「please fill」はplaceholder等に含まれるため除外
_ERROR_KEYWORDS = [
    "入力に誤り", "正しく入力",
    "入力されていません",
    "形式が正しくありません", "ご確認の上、再度",
    "validation error", "required field",
    "エラーが発生", "エラーがあります",
]


def _is_completion_url(url: str) -> bool:
    """URLパスに完了を示すキーワードが含まれるか判定する

    送信後にURLが /thanks 等に変わるサイトを検出する。

    Args:
        url: 現在のページURL

    Returns:
        完了URLと判定されればTrue
    """
    url_lower = url.lower()
    return any(k in url_lower for k in _COMPLETION_URL_KEYWORDS)


def _is_completion_page(body_lower: str) -> bool:
    """送信完了画面か判定する（ボディテキスト・タイトル両用）"""
    return any(k in body_lower for k in _COMPLETION_KEYWORDS)


def _check_page_completion(page: Page) -> bool:
    """URL変化・タイトル・ボディテキストの3段階で完了を判定する

    body_lowerを先に取得せず、URL → タイトル → ボディの順で高速判定する。
    bodyテキスト取得は最も重いため最後に行う。

    Args:
        page: Playwrightのページ

    Returns:
        完了と判定されればTrue
    """
    # 1. URLで判定（最速）
    try:
        if _is_completion_url(page.url):
            logger.info("完了判定: URLで確認 → %s", page.url[:80])
            return True
    except Exception:
        pass

    # 2. タイトルで判定
    try:
        title = page.title().lower()
        if _is_completion_page(title):
            logger.info("完了判定: タイトルで確認 → %s", title[:60])
            return True
    except Exception:
        pass

    # 3. ボディテキストで判定
    body = _get_body_text(page)
    if _is_completion_page(body):
        logger.info("完了判定: ボディテキストで確認")
        return True

    return False


def _is_form_still_visible(page: Page) -> bool:
    """送信後に編集可能なフォーム入力欄が表示されているか確認する

    readonly/disabled の入力欄は確認画面の表示用であるため除外する。
    編集可能な入力欄が2個以上残っていれば「フォーム残存（バリデーションエラー）」と判定する。

    Args:
        page: Playwrightのページ

    Returns:
        フォーム残存ならTrue（readonlyのみの確認画面はFalseを返す）
    """
    try:
        visible_inputs = page.evaluate(
            """() => {
                let count = 0;
                // readonly・disabled を除外：確認画面の読み取り専用フィールドを誤検知しないため
                const selector =
                    'form input:not([type=hidden]):not([type=submit])' +
                    ':not([type=button]):not([type=reset]):not([type=image])' +
                    ':not([readonly]):not([disabled]),' +
                    'form textarea:not([readonly]):not([disabled])';
                for (const el of document.querySelectorAll(selector)) {
                    const s = window.getComputedStyle(el);
                    if (s.display !== 'none' && s.visibility !== 'hidden'
                            && s.opacity !== '0') {
                        count++;
                    }
                }
                return count;
            }"""
        )
        return int(visible_inputs) >= 2
    except Exception:
        return False


def _is_confirmation_page(body_lower: str) -> bool:
    """確認画面か判定する（完了画面と被るキーワードは除外する）"""
    if _is_completion_page(body_lower):
        return False
    return any(k in body_lower for k in _CONFIRMATION_KEYWORDS)


def _is_error_page(body_lower: str) -> bool:
    """バリデーションエラー画面か判定する"""
    return any(k in body_lower for k in _ERROR_KEYWORDS)


def _find_confirm_button(page: Page) -> Optional[str]:
    """確認画面の送信ボタンセレクタを探す"""
    candidates = [
        # 日本語の最終送信ボタン
        'button:has-text("送信する")',
        'button:has-text("送信")',
        'button:has-text("同意して送信")',
        'button:has-text("上記内容で送信")',
        'button:has-text("この内容で送信")',
        'button:has-text("申し込む")',
        'input[value="送信する"]',
        'input[value="送信"]',
        'input[value*="送信"]',
        # 標準
        'input[type="submit"]',
        'button[type="submit"]',
        # 英語
        'button:has-text("Submit")',
        'button:has-text("Send")',
    ]
    for sel in candidates:
        if page.query_selector(sel):
            return sel
    return None


def _skip_result(status: str, detail: str, emails: Optional[list] = None) -> dict:
    """スキップ系の結果辞書を生成する（キャッシュ保存なし）

    Args:
        status: ステータス名
        detail: 詳細メッセージ
        emails: 手動対応用のメールアドレスリスト（no_form時等）
    """
    result = {
        "status": status, "detail": detail,
        "ai_used": False, "cache_used": False, "captcha_solved": False,
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
        "captcha_solved": False,
    }


def _split_phone(phone: str) -> dict[str, str]:
    """電話番号を3分割フィールド用に分解する

    "080-1899-3876" → {"phone1": "080", "phone2": "1899", "phone3": "3876"}

    Args:
        phone: ハイフン区切りの電話番号文字列

    Returns:
        phone1/phone2/phone3 のdict（分割できない場合は全て同じ値）
    """
    parts = phone.replace("ー", "-").replace("−", "-").split("-")
    if len(parts) == 3:
        return {"phone1": parts[0], "phone2": parts[1], "phone3": parts[2]}
    # ハイフンなしの場合は桁数で分割（市外局番を推定）
    digits = phone.replace("-", "").replace("−", "")
    if len(digits) == 11:  # 携帯 090/080/070
        return {"phone1": digits[:3], "phone2": digits[3:7], "phone3": digits[7:]}
    if len(digits) == 10:  # 固定 03/06等
        return {"phone1": digits[:2], "phone2": digits[2:6], "phone3": digits[6:]}
    return {"phone1": phone, "phone2": "", "phone3": ""}


def _kata_to_hira(text: str) -> str:
    """全角カタカナをひらがなに変換する"""
    return "".join(
        chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch
        for ch in text
    )


# 全角カタカナ → 半角カタカナ変換テーブル
# 濁点・半濁点付き文字は2文字に分解する
_KATA_TO_HAN = {
    "ア": "ｱ", "イ": "ｲ", "ウ": "ｳ", "エ": "ｴ", "オ": "ｵ",
    "カ": "ｶ", "キ": "ｷ", "ク": "ｸ", "ケ": "ｹ", "コ": "ｺ",
    "サ": "ｻ", "シ": "ｼ", "ス": "ｽ", "セ": "ｾ", "ソ": "ｿ",
    "タ": "ﾀ", "チ": "ﾁ", "ツ": "ﾂ", "テ": "ﾃ", "ト": "ﾄ",
    "ナ": "ﾅ", "ニ": "ﾆ", "ヌ": "ﾇ", "ネ": "ﾈ", "ノ": "ﾉ",
    "ハ": "ﾊ", "ヒ": "ﾋ", "フ": "ﾌ", "ヘ": "ﾍ", "ホ": "ﾎ",
    "マ": "ﾏ", "ミ": "ﾐ", "ム": "ﾑ", "メ": "ﾒ", "モ": "ﾓ",
    "ヤ": "ﾔ", "ユ": "ﾕ", "ヨ": "ﾖ",
    "ラ": "ﾗ", "リ": "ﾘ", "ル": "ﾙ", "レ": "ﾚ", "ロ": "ﾛ",
    "ワ": "ﾜ", "ヲ": "ｦ", "ン": "ﾝ",
    "ァ": "ｧ", "ィ": "ｨ", "ゥ": "ｩ", "ェ": "ｪ", "ォ": "ｫ",
    "ッ": "ｯ", "ャ": "ｬ", "ュ": "ｭ", "ョ": "ｮ",
    "ガ": "ｶﾞ", "ギ": "ｷﾞ", "グ": "ｸﾞ", "ゲ": "ｹﾞ", "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ", "ジ": "ｼﾞ", "ズ": "ｽﾞ", "ゼ": "ｾﾞ", "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ", "ヂ": "ﾁﾞ", "ヅ": "ﾂﾞ", "デ": "ﾃﾞ", "ド": "ﾄﾞ",
    "バ": "ﾊﾞ", "ビ": "ﾋﾞ", "ブ": "ﾌﾞ", "ベ": "ﾍﾞ", "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ", "ピ": "ﾋﾟ", "プ": "ﾌﾟ", "ペ": "ﾍﾟ", "ポ": "ﾎﾟ",
    "ヴ": "ｳﾞ", "ー": "ｰ", "。": "｡", "「": "｢", "」": "｣",
    "、": "､", "・": "･", "　": " ",
}


def _kata_to_hankaku(text: str) -> str:
    """全角カタカナを半角カタカナに変換する（濁点・半濁点は2文字に分解）"""
    return "".join(_KATA_TO_HAN.get(ch, ch) for ch in text)


def _detect_kana_type(page: Page, sel: str) -> str:
    """フィールドの属性・placeholder・ラベルからフリガナ形式を自動判定する

    placeholder・pattern・クラス名・ラベルテキストを検査し、
    ひらがなが期待されていれば 'hira'、それ以外は 'kata' を返す。

    Args:
        page: Playwrightのページ
        sel: フィールドのCSSセレクタ

    Returns:
        'hira': ひらがな入力が期待される
        'kata': 全角カタカナ入力が期待される（デフォルト）
    """
    try:
        result = page.evaluate(
            f"""() => {{
                const el = document.querySelector({repr(sel)});
                if (!el) return 'kata';
                const placeholder = (el.placeholder || '').toLowerCase();
                const pattern = el.getAttribute('pattern') || '';
                const cls = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const name = (el.name || '').toLowerCase();

                // ラベルのテキストも取得
                let labelText = '';
                if (el.id) {{
                    const lbl = document.querySelector('label[for="' + el.id + '"]');
                    if (lbl) labelText = lbl.textContent.toLowerCase();
                }}
                const label = el.closest('label');
                if (label) labelText += label.textContent.toLowerCase();

                const allText = placeholder + pattern + cls + id + name + labelText;

                // 半角カタカナ検出（優先度高）
                const hanPatterns = ['半角', 'hankaku', 'half', 'han-kana',
                    'halfkana', 'half_kana'];
                if (hanPatterns.some(p => allText.includes(p))) return 'han';

                // placeholderに半角カタカナ文字が含まれている（U+FF66-U+FF9F）
                if (/[ｦ-ﾟ]/.test(placeholder)) return 'han';

                // ひらがな検出キーワード
                const hiraPatterns = ['ひらがな', 'furigana', 'hira',
                    'よみ', 'よみがな', 'ふりがな（ひ'];
                if (hiraPatterns.some(p => allText.includes(p))) return 'hira';

                // placeholderにひらがな文字が含まれている
                if (/[ぁ-ん]/.test(placeholder)) return 'hira';

                // 全角カタカナ（デフォルト）
                return 'kata';
            }}"""
        )
        return result if result in ("hira", "kata", "han") else "kata"
    except Exception:
        return "kata"


def _fill_form(
    page: Page, mapping: dict, message: str, sender: dict
) -> bool:
    """マッピングに基づいてフォームに値を入力する"""
    email = sender.get("email", "")
    last_name = sender.get("last_name", "")
    first_name = sender.get("first_name", "")
    last_kana = sender.get("last_kana", "")
    first_kana = sender.get("first_kana", "")

    # first_name が空の場合は last_name を代入（姓・名分割必須フォーム対応）
    if not first_name and last_name:
        first_name = last_name
    if not first_kana and last_kana:
        first_kana = last_kana

    # フリガナ値の準備（全角カタカナをデフォルト、ひらがな・半角カタカナを代替として保持）
    # 大半の日本語フォームは全角カタカナを要求するためカタカナを優先する
    kana_full_kata = f"{last_kana} {first_kana}".strip()
    kana_full_hira = _kata_to_hira(kana_full_kata)
    kana_full_han  = _kata_to_hankaku(kana_full_kata)
    last_kana_hira = _kata_to_hira(last_kana)
    last_kana_han  = _kata_to_hankaku(last_kana)
    first_kana_hira = _kata_to_hira(first_kana)
    first_kana_han  = _kata_to_hankaku(first_kana)

    # フィールド別の代替値マップ（自動判定で差し替えに使う）
    # キー: (hira用, han用)
    kana_alt_map = {
        "kana":       (kana_full_hira,  kana_full_han),
        "last_kana":  (last_kana_hira,  last_kana_han),
        "first_kana": (first_kana_hira, first_kana_han),
    }

    values = {
        "company": sender.get("company", ""),
        "last_name": last_name,
        "first_name": first_name,
        "name": sender.get("name", f"{last_name}{first_name}".strip()),
        "last_kana": last_kana,          # 全角カタカナ（デフォルト）
        "first_kana": first_kana,        # 全角カタカナ（デフォルト）
        "kana": kana_full_kata,          # 全角カタカナ（デフォルト）
        "email": email,
        "email_confirm": email,
        "phone": sender.get("phone", ""),
        **_split_phone(sender.get("phone", "")),
        "postal": sender.get("postal", ""),
        "address": sender.get("address", ""),
        "prefecture": sender.get("prefecture", ""),
        "city": sender.get("city", ""),
        "street": sender.get("street", ""),
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

        elem_name = finfo["name"]
        # name属性 → id属性の順でフォールバック
        # ただし#idはCSSとして有効な識別子のみ（特殊文字を含む名前は除外）
        selectors = [f'[name="{elem_name}"]']
        if _CSS_ID_RE.match(elem_name):
            selectors.append(f'#{elem_name}')

        # フリガナフィールドはplaceholder等からひらがな/全角カタカナ/半角カタカナを自動判定
        if ftype in kana_alt_map:
            kana_type = _detect_kana_type(page, selectors[0])
            hira_val, han_val = kana_alt_map[ftype]
            if kana_type == "hira":
                value = hira_val
                logger.info("フリガナ形式: ひらがなで入力 [%s]", ftype)
            elif kana_type == "han":
                value = han_val
                logger.info("フリガナ形式: 半角カタカナで入力 [%s]", ftype)
            else:
                logger.info("フリガナ形式: 全角カタカナで入力 [%s]", ftype)

        for sel in selectors:
            if _fill_field(page, sel, ftype, value, filled):
                filled += 1
                # postal入力後はAJAXアドレス補完が走るため完了を待つ
                if ftype == "postal":
                    _wait_postal_ajax(page)
                break

    # 全フィールド入力後にblur/inputイベントを全体発火（wpcf7の有効化トリガー）
    if filled > 0:
        try:
            page.evaluate(
                """document.querySelectorAll('input,textarea,select').forEach(el => {
                    el.dispatchEvent(new Event('input', {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                    el.dispatchEvent(new Event('blur', {bubbles:true}));
                });"""
            )
        except Exception:
            pass

    # 同意チェックボックスを自動チェック（プライバシーポリシー等の必須同意）
    _check_consent_checkboxes(page)

    return filled > 0


def _wait_postal_ajax(page: Page, timeout_ms: int = 45000) -> None:
    """郵便番号入力後のAJAXアドレス補完完了を待つ

    郵便番号フィールド入力時にAJAX APIが住所を自動補完するサイトがある。
    補完完了前に次フィールドを入力するとフォームが壊れるため、
    networkidleを待ってからフォールバックで固定待機する。
    AJAXが30秒以上かかるサイトに対応するため45秒タイムアウト。
    AJAXのないサイトはnetworkidle即完了のためほぼ追加コストなし。

    Args:
        page: Playwrightのページ
        timeout_ms: networkidle待機タイムアウト（ミリ秒）
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
        logger.info("postal AJAX補完待機完了")
    except Exception:
        # タイムアウト時は固定3秒待機してから続行
        try:
            page.wait_for_timeout(3000)
        except Exception:
            pass


def _check_consent_checkboxes(page: Page) -> None:
    """フォーム内の同意・確認チェックボックスを自動チェックする

    プライバシーポリシー・個人情報取り扱い・利用規約などの
    必須同意チェックボックスが未チェックのままだとバリデーション失敗するため、
    全チェックボックスをチェック済みにする。

    改善点:
    - label経由クリックでカスタムUIにも対応
    - change/inputイベントも発火してJSバリデーションを確実にトリガー
    - 2パス処理（JSレンダリング後に未チェックが残っていれば再チェック）

    Args:
        page: Playwrightのページ
    """
    js_check = """() => {
        let count = 0;
        const checkboxes = document.querySelectorAll(
            'form input[type="checkbox"], input[type="checkbox"]'
        );
        checkboxes.forEach(cb => {
            if (cb.checked || cb.disabled) return;

            // カスタムUIはinputが隠れていてlabelをクリックする必要がある
            const label = (cb.id
                ? document.querySelector('label[for="' + cb.id + '"]')
                : null) || cb.closest('label');

            if (label) {
                label.click();
            } else {
                cb.click();
            }

            // JSバリデーションのために各種イベントを発火
            cb.dispatchEvent(new Event('change', {bubbles: true}));
            cb.dispatchEvent(new Event('input',  {bubbles: true}));
            count++;
        });
        return count;
    }"""

    try:
        # 1回目チェック
        checked = page.evaluate(js_check)
        if checked > 0:
            logger.info("チェックボックス自動チェック: %d個", checked)
            # JSレンダリングを待ってから2回目（動的に出現するチェックボックス対応）
            time.sleep(0.5)
            checked2 = page.evaluate(js_check)
            if checked2 > 0:
                logger.info("チェックボックス追加チェック（2回目）: %d個", checked2)
    except Exception as e:
        logger.debug("チェックボックス自動チェック失敗: %s", str(e)[:60])


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
    try:
        elem = page.query_selector(sel)
    except Exception as e:
        logger.debug("query_selector失敗 [%s]: %s", sel, str(e)[:80])
        return False
    if not elem:
        return False

    # フィールド間移動の待機
    if filled_count > 0:
        time.sleep(random.uniform(FIELD_MOVE_MIN, FIELD_MOVE_MAX))

    # select要素の場合は select_option を使う
    try:
        tag = elem.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            return _fill_select(elem, ftype, value)
    except Exception:
        pass

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
    # 検証失敗でも入力試行済みとして True を返す
    # （JSが後から値を変換・クリアするフォームもあるため、最終判断はフォーム側に委ねる）
    if not _verify_field_value(elem, value):
        logger.warning("入力検証失敗 [%s]: JSが値を上書きした可能性あり（送信は続行）", ftype)

    logger.info("入力: %s", ftype)
    return True


def _fill_select(elem, ftype: str, value: str) -> bool:
    """select要素のオプションを選択する

    値テキストに部分一致するオプションのみ選ぶ。
    subject フィールドのみ、一致なし時に最初の非空オプションを選択する。
    それ以外は一致なしで False を返す（ページ遷移リスク回避）。

    Args:
        elem: select要素のElementHandle
        ftype: フィールドタイプ名（ログ用）
        value: 選択候補テキスト

    Returns:
        選択成功ならTrue
    """
    try:
        elem.select_option(label=value)
        logger.info("select選択: %s = %s", ftype, value)
        return True
    except Exception as e:
        logger.debug("select選択失敗（一致なし）[%s]: %s", ftype, str(e)[:60])

    # subject フィールドのみ: 最初の非空オプションを自動選択
    # （問い合わせ種別等の必須selectをスキップしないための措置）
    if ftype == "subject":
        try:
            options = elem.evaluate(
                "el => Array.from(el.options).map(o => o.text).filter(t => t.trim())"
            )
            # プレースホルダー文言を除外して最初の有効なオプションを選択
            _placeholder_keywords = (
                "選択", "選んで", "お選び", "ください", "---", "===", "please", "select"
            )
            valid = [
                o for o in options
                if not any(kw in o.lower() for kw in _placeholder_keywords)
            ]
            if valid:
                elem.select_option(label=valid[0])
                logger.info("select最初の有効オプション選択: %s = %s", ftype, valid[0])
                return True
        except Exception as e:
            logger.debug("subject select最初のオプション失敗: %s", str(e)[:60])

    return False


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


def _wait_for_submit_enabled(page: Page, submit_sel: str, max_wait: int = 5) -> bool:
    """送信ボタンが有効になるまで待機する（wpcf7 disabled対応）

    wpcf7等は全必須フィールド入力後にJSがボタンを有効化する。
    入力イベントを再発火しながら最大 max_wait 秒間待つ。

    Args:
        page: Playwrightのページ
        submit_sel: 送信ボタンのCSSセレクタ
        max_wait: 最大待機秒数

    Returns:
        ボタンが有効ならTrue、タイムアウトしてもdisabledならFalse
    """
    for _ in range(max_wait):
        try:
            elem = page.query_selector(submit_sel)
        except Exception:
            return True  # ページ遷移済みなら有効扱い
        if not elem:
            return False
        try:
            if not elem.is_disabled():
                return True
        except Exception:
            return True  # is_disabled が使えない要素は有効扱い
        # 再度イベント発火して有効化を促す
        try:
            page.evaluate(
                """document.querySelectorAll('input,textarea,select').forEach(el => {
                    el.dispatchEvent(new Event('input', {bubbles:true}));
                    el.dispatchEvent(new Event('change', {bubbles:true}));
                    el.dispatchEvent(new Event('blur', {bubbles:true}));
                });"""
            )
        except Exception:
            pass
        time.sleep(1)
    logger.warning("送信ボタンが有効にならなかった: %s", submit_sel)
    return False


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

    # JSで全要素を対象に送信関連テキスト・onclickを検索（最終フォールバック）
    return _find_submit_by_js(page)


def _find_submit_by_js(page: Page) -> Optional[str]:
    """JSで全要素を走査して送信ボタンを探す（最終フォールバック）

    送信関連のテキスト・value・onclick を持つ要素に一時IDを付与し
    そのセレクタを返す。

    Args:
        page: Playwrightのページ

    Returns:
        発見したセレクタ、なければNone
    """
    keywords = ["送信", "確認", "問い合わせ", "申し込", "send", "submit", "次へ", "進む"]
    try:
        sel = page.evaluate(
            """(keywords) => {
                const tags = ['input', 'button', 'a', 'span', 'div'];
                for (const tag of tags) {
                    for (const el of document.querySelectorAll(tag)) {
                        const text = (el.innerText || el.value || el.textContent || '').trim();
                        const onclick = el.getAttribute('onclick') || '';
                        const cls = el.className || '';
                        if (keywords.some(kw => text.includes(kw))
                            || /submit|send/i.test(onclick)
                            || /submit|send/i.test(cls)) {
                            const tempId = 'tmp_submit_find_' + Date.now();
                            el.setAttribute('data-tmp-find', tempId);
                            return '[data-tmp-find="' + tempId + '"]';
                        }
                    }
                }
                return null;
            }""",
            keywords,
        )
        if sel:
            logger.info("JS全探索で送信ボタン発見: %s", sel[:60])
        return sel
    except Exception as e:
        logger.debug("JS送信ボタン全探索失敗: %s", str(e)[:60])
        return None


# 送信ボタン検出セレクタ（優先度順）
_SUBMIT_SELECTORS = [
    # 標準的なsubmit要素
    'input[type="submit"]',
    'button[type="submit"]',
    'input[type="image"]',
    # 日本語テキストボタン（button）
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
    # value属性（input[type="submit"] / input[type="button"]）
    'input[value="送信"]',
    'input[value="確認"]',
    'input[value="確認する"]',
    'input[value="問い合わせる"]',
    'input[value="お申し込み"]',
    'input[value="申し込む"]',
    'input[value*="送信"]',
    'input[value*="確認"]',
    'input[type="button"][value*="送信"]',
    'input[type="button"][value*="確認"]',
    'input[type="button"][value*="問い合わせ"]',
    # class属性フォールバック
    'button[class*="submit"]',
    'button[class*="send"]',
    'button[class*="form-submit"]',
    'input[class*="submit"]',
    'input[class*="send"]',
    # aタグボタン
    'a[role="button"]:has-text("送信")',
    'a[role="button"]:has-text("確認")',
    'a[role="button"]:has-text("問い合わせ")',
    'a[class*="btn"]:has-text("送信")',
    'a[class*="btn"]:has-text("確認")',
    'a[class*="btn"]:has-text("問い合わせ")',
    'a:has-text("送信する")',
    'a:has-text("問い合わせる")',
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
