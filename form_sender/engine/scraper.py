"""フォーム解析エンジン - BeautifulSoupによるフォーム要素の自動判定"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# フィールドタイプ → 検出パターンのマッピング
FIELD_PATTERNS: dict[str, list[str]] = {
    "company": [
        "company", "corp", "kaisha", "会社", "企業", "法人",
        "organization", "org",
    ],
    "name": [
        "name", "namae", "shimei", "氏名", "お名前", "担当者",
        "fullname", "your-name",
    ],
    "email": [
        "email", "mail", "メール", "e-mail", "address",
    ],
    "phone": [
        "tel", "phone", "denwa", "電話", "携帯",
    ],
    "subject": [
        "subject", "title", "件名", "タイトル", "用件",
    ],
    "message": [
        "message", "body", "content", "inquiry", "本文",
        "内容", "お問い合わせ", "メッセージ", "相談",
    ],
}


def find_contact_url(html: str, base_url: str) -> Optional[str]:
    """HTMLからお問い合わせページのリンクを探す

    Args:
        html: ページのHTMLテキスト
        base_url: ベースURL（相対パス解決用）

    Returns:
        お問い合わせページのURL、見つからなければNone
    """
    soup = BeautifulSoup(html, "html.parser")
    # お問い合わせ系のキーワード
    keywords = ["問い合わせ", "お問合せ", "contact", "inquiry", "相談"]

    for link in soup.find_all("a", href=True):
        text = link.get_text(strip=True).lower()
        href = link["href"].lower()
        # リンクテキストまたはhrefにキーワードが含まれるか
        for kw in keywords:
            if kw in text or kw in href:
                full_url = urljoin(base_url, link["href"])
                logger.info("お問い合わせURL発見: %s", full_url)
                return full_url

    logger.warning("お問い合わせリンクが見つかりません: %s", base_url)
    return None


def extract_forms(html: str) -> list[Tag]:
    """HTMLからform要素を全て抽出する

    Args:
        html: ページのHTMLテキスト

    Returns:
        form要素のリスト
    """
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    logger.info("フォーム要素数: %d", len(forms))
    return forms


def _get_field_hints(element: Tag) -> str:
    """フォーム要素からヒント文字列を収集する

    Args:
        element: input/textarea/select要素

    Returns:
        判定用のヒント文字列（小文字化済み）
    """
    hints: list[str] = []

    # name属性・id属性・placeholder
    for attr in ["name", "id", "placeholder", "aria-label"]:
        val = element.get(attr, "")
        if val:
            hints.append(str(val))

    # type属性
    hints.append(element.get("type", ""))

    # 親のlabel要素
    parent = element.find_parent("label")
    if parent:
        hints.append(parent.get_text(strip=True))

    # for属性で紐づくlabel
    elem_id = element.get("id", "")
    if elem_id:
        soup = element.find_parent()
        if soup:
            label = soup.find("label", attrs={"for": elem_id})
            if label:
                hints.append(label.get_text(strip=True))

    return " ".join(hints).lower()


def classify_field(element: Tag) -> Optional[str]:
    """フォーム要素のフィールドタイプを推定する

    Args:
        element: input/textarea/select要素

    Returns:
        フィールドタイプ名、判定不能ならNone
    """
    # type="email" は確定
    if element.get("type") == "email":
        return "email"
    # type="tel" は確定
    if element.get("type") == "tel":
        return "phone"
    # textarea はメッセージ
    if element.name == "textarea":
        return "message"

    hints = _get_field_hints(element)

    # パターンマッチング（優先度順に判定）
    for field_type, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            if pattern in hints:
                return field_type

    return None


def analyze_form(form: Tag) -> dict[str, dict]:
    """フォーム内の全要素を解析してマッピングを作成する

    Args:
        form: form要素

    Returns:
        {フィールドタイプ: {name: 要素名, tag: タグ名}} のマッピング
    """
    mapping: dict[str, dict] = {}
    # hidden/submitは除外
    skip_types = {"hidden", "submit", "button", "image", "reset"}

    elements = form.find_all(["input", "textarea", "select"])

    for elem in elements:
        input_type = elem.get("type", "text")
        if input_type in skip_types:
            continue

        field_type = classify_field(elem)
        if field_type and field_type not in mapping:
            elem_name = elem.get("name", elem.get("id", ""))
            mapping[field_type] = {
                "name": elem_name,
                "tag": elem.name,
                "type": input_type,
            }

    logger.info("フォーム解析結果: %s", list(mapping.keys()))
    return mapping


def detect_captcha(html: str) -> bool:
    """CAPTCHA要素を検出する

    Args:
        html: ページのHTMLテキスト

    Returns:
        CAPTCHA検出ならTrue
    """
    captcha_patterns = [
        "g-recaptcha", "h-captcha", "captcha",
        "cf-turnstile", "recaptcha",
    ]
    html_lower = html.lower()
    for pattern in captcha_patterns:
        if pattern in html_lower:
            logger.warning("CAPTCHA検出: %s", pattern)
            return True
    return False
