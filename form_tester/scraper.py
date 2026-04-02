"""
フォーム検出・解析
Playwrightでページにアクセスし、お問い合わせフォームを探す
BeautifulSoupでフォーム要素を解析する
"""

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Page, TimeoutError as PwTimeout

from config import (
    CONTACT_LINK_KEYWORDS, FALLBACK_PATHS,
    CAPTCHA_PATTERNS, PAGE_TIMEOUT,
)

log = logging.getLogger(__name__)


def find_contact_link(page: Page, base_url: str) -> str | None:
    """トップページから「お問い合わせ」リンクを探す"""
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)

    for link in links:
        text = link.get_text(strip=True).lower()
        href = link['href'].lower()
        # テキストまたはhrefにキーワードが含まれるか
        for kw in CONTACT_LINK_KEYWORDS:
            if kw in text or kw in href:
                full_url = urljoin(base_url, link['href'])
                log.info(f"  コンタクトリンク発見: {full_url}")
                return full_url

    return None


def try_fallback_paths(page: Page, base_url: str) -> str | None:
    """フォールバックパスを順に試してフォームページを探す"""
    for path in FALLBACK_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
            if resp and resp.status < 400:
                # ページにformタグがあるか確認
                if page.query_selector('form'):
                    log.info(f"  フォールバックで発見: {url}")
                    return url
        except PwTimeout:
            continue
        except Exception:
            continue

    return None


def navigate_to_form(page: Page, base_url: str) -> str | None:
    """トップページからフォームページへ遷移する"""
    # トップページにアクセス
    try:
        page.goto(base_url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
    except PwTimeout:
        log.warning(f"  トップページタイムアウト: {base_url}")
        return None
    except Exception as e:
        log.warning(f"  トップページアクセス失敗: {e}")
        return None

    # コンタクトリンクを探す
    contact_url = find_contact_link(page, base_url)
    if contact_url:
        try:
            page.goto(contact_url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
            return contact_url
        except Exception:
            pass

    # フォールバックパスを試す
    return try_fallback_paths(page, base_url)


def extract_form_fields(page: Page) -> list[dict[str, str]]:
    """ページ内のフォーム要素（input/textarea/select）を全取得する"""
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form')
    if not form:
        return []

    fields: list[dict[str, str]] = []
    for tag in form.find_all(['input', 'textarea', 'select']):
        if not isinstance(tag, Tag):
            continue
        field = _parse_field(tag, soup)
        if field:
            fields.append(field)

    return fields


def _parse_field(tag: Tag, soup: BeautifulSoup) -> dict[str, str] | None:
    """1つのフォーム要素からフィールド情報を抽出する"""
    input_type = tag.get('type', 'text')
    # hidden/submitは除外
    if input_type in ('hidden', 'submit', 'button', 'image', 'reset'):
        return None

    name = tag.get('name', '')
    placeholder = tag.get('placeholder', '')
    tag_name = tag.name  # input / textarea / select

    # labelテキストを取得（for属性またはラッパー）
    label_text = _find_label(tag, soup)

    return {
        'tag': tag_name,
        'type': input_type,
        'name': name,
        'placeholder': placeholder,
        'label': label_text,
        'id': tag.get('id', ''),
    }


def _find_label(tag: Tag, soup: BeautifulSoup) -> str:
    """input要素に対応するlabelテキストを探す"""
    # for属性で紐づくlabel
    tag_id = tag.get('id', '')
    if tag_id:
        label = soup.find('label', attrs={'for': tag_id})
        if label:
            return label.get_text(strip=True)

    # 親要素がlabelの場合
    parent = tag.parent
    if parent and parent.name == 'label':
        return parent.get_text(strip=True)

    return ''


def detect_captcha(page: Page) -> bool:
    """reCAPTCHA・hCaptcha等のCAPTCHAを検出する"""
    html = page.content().lower()
    for pattern in CAPTCHA_PATTERNS:
        if pattern in html:
            log.info(f"  CAPTCHA検出: {pattern}")
            return True
    return False


def check_site_alive(page: Page, url: str) -> tuple[int, bool]:
    """サイトの死活確認（HTTPステータスを返す）

    Returns:
        (HTTPステータスコード, 成功フラグ)
    """
    try:
        resp = page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
        status = resp.status if resp else 0
        return status, 200 <= status < 400
    except PwTimeout:
        return 0, False
    except Exception:
        return 0, False


def detect_form_type(page: Page) -> str:
    """フォームが静的HTMLか、JS動的レンダリングかを判別する

    Returns:
        'static' / 'dynamic' / 'none'
    """
    # まずDOMに直接<form>があるか確認
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    forms = soup.find_all('form')

    if not forms:
        return 'none'

    # formタグ内にinput/textareaがあれば静的
    for form in forms:
        inputs = form.find_all(['input', 'textarea', 'select'])
        visible = [i for i in inputs if i.get('type') not in ('hidden',)]
        if visible:
            return 'static'

    # formはあるが中身が空 → JS動的の可能性
    return 'dynamic'
