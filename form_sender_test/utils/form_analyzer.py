"""フォーム解析エンジン - BS4によるフォーム要素の自動判定

Playwrightで取得したHTMLをBeautifulSoupで解析し、
フォームのフィールドタイプを推定する。
robots.txt / CAPTCHA検知による安全な回避機能付き。
お問い合わせリンク検出・検索フォーム除外・フォームスコアリング対応。
"""

import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# フィールドタイプ → 検出パターン（拡張済み）
FIELD_PATTERNS: dict[str, list[str]] = {
    "company": [
        "company", "corp", "kaisha", "会社", "企業", "法人",
        "organization", "org",
    ],
    "last_name": [
        "last_name", "lastname", "family", "sei", "姓",
    ],
    "first_name": [
        "first_name", "firstname", "given", "mei", "名",
    ],
    "name": [
        "name", "namae", "shimei", "氏名", "お名前", "担当者",
        "fullname", "your-name",
    ],
    "last_kana": [
        "last_kana", "lastkana", "セイ", "姓カナ", "seikana",
    ],
    "first_kana": [
        "first_kana", "firstkana", "メイ", "名カナ", "meikana",
    ],
    "kana": [
        "kana", "furigana", "フリガナ", "ふりがな", "カナ",
    ],
    "email": [
        "email", "mail", "メール", "e-mail",
    ],
    "phone": [
        "tel", "phone", "denwa", "電話", "携帯",
    ],
    "postal": [
        "zip", "postal", "郵便", "〒", "zipcode", "postcode",
    ],
    "address": [
        "address", "住所", "所在地", "addr",
    ],
    "subject": [
        "subject", "title", "件名", "タイトル", "用件",
    ],
    "message": [
        "message", "body", "content", "inquiry", "本文",
        "内容", "お問い合わせ", "メッセージ", "相談",
    ],
}

# お問い合わせリンク検出用キーワード
CONTACT_KEYWORDS = [
    "問い合わせ", "お問合せ", "お問い合わせ", "contact", "inquiry",
    "相談", "ご連絡", "メールフォーム", "資料請求", "お申し込み",
]

# お問い合わせURL パスパターン
CONTACT_PATH_PATTERNS = [
    "/contact", "/inquiry", "/form", "/toiawase",
    "/otoiawase", "/mail", "/ask",
]

# 直接推測用のお問い合わせURLパス候補
CONTACT_URL_GUESSES = [
    "/contact", "/contact/", "/contact.html", "/contact.php",
    "/inquiry", "/inquiry/", "/toiawase", "/toiawase/",
    "/otoiawase", "/otoiawase/", "/form", "/form/",
    "/contact/index.html", "/contact/form.html",
]


def check_robots_txt(url: str) -> bool:
    """robots.txtでクローリングが許可されているか確認する

    Args:
        url: 対象URL

    Returns:
        許可されていればTrue、拒否またはエラーならFalse
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        resp = requests.get(robots_url, timeout=10)
        if resp.status_code != 200:
            return True

        for line in resp.text.splitlines():
            line = line.strip().lower()
            if line.startswith("disallow: /") and line == "disallow: /":
                logger.warning("robots.txt: 全ページ拒否 %s", url)
                return False
        return True

    except Exception as e:
        logger.warning("robots.txt取得失敗（許可扱い）: %s", e)
        return True


def detect_captcha(html: str) -> bool:
    """CAPTCHA要素を検出する

    Args:
        html: ページのHTMLテキスト

    Returns:
        CAPTCHA検出ならTrue
    """
    patterns = [
        "g-recaptcha", "h-captcha", "captcha",
        "cf-turnstile", "recaptcha", "hcaptcha",
    ]
    html_lower = html.lower()
    for pat in patterns:
        if pat in html_lower:
            logger.warning("CAPTCHA検出: %s", pat)
            return True
    return False


def _is_valid_link(href: str) -> bool:
    """リンクが有効な遷移先か判定する（tel:/mailto:等を除外）"""
    invalid_prefixes = ("tel:", "mailto:", "javascript:", "#", "fax:")
    return not href.lower().startswith(invalid_prefixes)


def _matches_contact_patterns(text: str, href: str) -> bool:
    """テキストまたはhrefがお問い合わせパターンに一致するか判定する"""
    text_lower = text.lower()
    href_lower = href.lower()

    # キーワードマッチ
    for kw in CONTACT_KEYWORDS:
        if kw in text_lower or kw in href_lower:
            return True

    # URLパスパターンマッチ
    try:
        path = urlparse(href_lower).path
        for pattern in CONTACT_PATH_PATTERNS:
            if pattern in path:
                return True
    except Exception:
        pass

    return False


def find_contact_url(html: str, base_url: str) -> Optional[str]:
    """お問い合わせページのリンクを探す

    ページ全体→footer の順で検索し、tel:/mailto:リンクは除外する。

    Args:
        html: ページのHTMLテキスト
        base_url: ベースURL

    Returns:
        お問い合わせURL、見つからなければNone
    """
    soup = BeautifulSoup(html, "html.parser")

    # ページ全体のリンクを検索
    result = _search_contact_links(soup.find_all("a", href=True), base_url)
    if result:
        return result

    # footer内のリンクをフォールバック検索
    footer = soup.find("footer")
    if footer:
        result = _search_contact_links(footer.find_all("a", href=True), base_url)
        if result:
            return result

    logger.warning("お問い合わせリンクなし: %s", base_url)
    return None


def _search_contact_links(links: list, base_url: str) -> Optional[str]:
    """リンクリストからお問い合わせリンクを検索する"""
    for link in links:
        href = link.get("href", "")
        if not href or not _is_valid_link(href):
            continue
        text = link.get_text(strip=True)
        if _matches_contact_patterns(text, href):
            full = urljoin(base_url, href)
            logger.info("お問い合わせURL: %s", full)
            return full
    return None


def guess_contact_url(base_url: str) -> Optional[str]:
    """ベースURLから典型的なお問い合わせURLを推測する

    HEAD リクエストで各候補URLが存在するか確認し、
    200応答を返した最初のURLを返す。

    Args:
        base_url: 企業サイトのベースURL

    Returns:
        存在するお問い合わせURL候補、なければNone
    """
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    for path in CONTACT_URL_GUESSES:
        candidate = root + path
        try:
            resp = requests.head(
                candidate, timeout=5, allow_redirects=True, headers=headers,
            )
            # 200 OK or 405 Method Not Allowed（HEAD非対応サイト）
            if resp.status_code in (200, 405):
                logger.info("お問い合わせURL推測成功: %s", candidate)
                return candidate
        except Exception:
            continue

    return None


def extract_contact_emails(html: str) -> list[str]:
    """HTMLからメールアドレスを抽出する（手動対応用）

    mailto:リンクとテキスト中のメールアドレスパターンを収集。
    重複を排除して返す。

    Args:
        html: ページのHTMLテキスト

    Returns:
        検出されたメールアドレスのリスト
    """
    import re

    emails: set[str] = set()

    # mailto:リンクから抽出
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if email and "@" in email:
                emails.add(email)

    # テキスト中のメールアドレスパターン抽出
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    text = soup.get_text(" ")
    for m in re.finditer(pattern, text):
        emails.add(m.group())

    # 無効な候補を除外（画像ファイル名等）
    filtered = [
        e for e in emails
        if not e.lower().endswith((".png", ".jpg", ".gif", ".svg"))
    ]

    return sorted(filtered)


# === 検索フォーム判定・スコアリング ===


def is_search_form(form: Tag) -> bool:
    """フォームが検索フォームかどうか判定する

    Args:
        form: form要素

    Returns:
        検索フォームならTrue
    """
    # role="search" 属性
    if form.get("role", "").lower() == "search":
        return True

    # action URLに"search"が含まれる
    action = form.get("action", "").lower()
    if "search" in action:
        return True

    # 親要素がheader/nav/role=search
    for parent_tag in ["header", "nav"]:
        if form.find_parent(parent_tag):
            # GETメソッド + 入力フィールド1個以下 → 検索フォーム
            if _is_minimal_get_form(form):
                return True

    # id/classに"search"が含まれる
    form_id = form.get("id", "").lower()
    form_class = " ".join(form.get("class", [])).lower()
    if "search" in form_id or "search" in form_class:
        return True

    return False


def _is_minimal_get_form(form: Tag) -> bool:
    """GETメソッドで入力フィールドが少ないフォームか判定する"""
    method = form.get("method", "get").lower()
    if method != "get":
        return False
    inputs = form.find_all("input", {"type": lambda t: t not in ("hidden", "submit", "button")})
    return len(inputs) <= 1


def score_contact_form(form: Tag) -> int:
    """フォームのコンタクトフォームらしさをスコアリングする

    Args:
        form: form要素

    Returns:
        スコア（高いほどコンタクトフォームらしい）
    """
    score = 0

    # textarea → メッセージ欄がある可能性大
    if form.find("textarea"):
        score += 10

    # type="email" → 連絡先入力
    if form.find("input", {"type": "email"}):
        score += 5

    # type="tel" → 電話番号入力
    if form.find("input", {"type": "tel"}):
        score += 3

    # main/article内にある → メインコンテンツ
    if form.find_parent("main") or form.find_parent("article"):
        score += 5

    # header/nav内にある → 検索フォームの可能性大
    if form.find_parent("header") or form.find_parent("nav"):
        score -= 20

    # 入力フィールド数（多いほどコンタクトフォーム）
    skip_types = {"hidden", "submit", "button", "image", "reset"}
    inputs = [e for e in form.find_all(["input", "textarea", "select"])
              if e.get("type", "text") not in skip_types]
    score += len(inputs) * 2

    return score


def select_best_form(forms: list[Tag]) -> Optional[Tag]:
    """検索フォームを除外し、最もコンタクトフォームらしいものを選ぶ

    Args:
        forms: form要素のリスト

    Returns:
        最適なフォーム、候補なしならNone
    """
    candidates = [f for f in forms if not is_search_form(f)]

    if not candidates:
        # 全て検索フォームと判定された場合、元のリストからスコア最高を選ぶ
        candidates = forms

    if not candidates:
        return None

    best = max(candidates, key=score_contact_form)
    score = score_contact_form(best)
    logger.info("フォーム選択: %d候補中, スコア=%d", len(candidates), score)
    return best


def build_virtual_form(soup: BeautifulSoup) -> Optional[Tag]:
    """`<form>`タグなしフォーム（div+JS送信型）を仮想フォームとして構築する

    モダンなサイトでは`<form>`タグを使わず、divと個別のinput/buttonで
    JSによる送信を行うケースがある。この場合、textareaを含む領域を
    探してその親要素を仮想的なフォームとして返す。

    Args:
        soup: ページ全体のBeautifulSoupオブジェクト

    Returns:
        仮想フォーム要素（Tag）、条件を満たすものがなければNone
    """
    # textareaは本文入力欄の強いシグナル
    textareas = soup.find_all("textarea")
    if not textareas:
        return None

    for textarea in textareas:
        # textareaの親要素を段階的に遡って、十分な入力欄を含む範囲を探す
        parent = textarea.find_parent()
        while parent and parent.name not in ("body", "html"):
            # 既存のform要素内なら対象外
            if parent.name == "form":
                break

            # 入力欄カウント
            inputs = parent.find_all("input", {"type": lambda t: t not in (
                "hidden", "submit", "button", "image", "reset"
            )})
            has_button = bool(parent.find("button")) or bool(
                parent.find("input", {"type": "submit"})
            )

            # input3個以上 + ボタンあり → 仮想フォームとみなす
            if len(inputs) >= 3 and has_button:
                logger.info(
                    "仮想フォーム検出: <%s> input=%d個",
                    parent.name, len(inputs),
                )
                return parent

            parent = parent.find_parent()

    return None


# === フィールド解析 ===


def _get_field_hints(elem: Tag) -> str:
    """フォーム要素からヒント文字列を収集する"""
    hints: list[str] = []

    for attr in ["name", "id", "placeholder", "aria-label"]:
        val = elem.get(attr, "")
        if val:
            hints.append(str(val))

    hints.append(elem.get("type", ""))

    # 親label
    parent = elem.find_parent("label")
    if parent:
        hints.append(parent.get_text(strip=True))

    # for属性のlabel
    elem_id = elem.get("id", "")
    if elem_id:
        root = elem.find_parent()
        if root:
            label = root.find("label", attrs={"for": elem_id})
            if label:
                hints.append(label.get_text(strip=True))

    return " ".join(hints).lower()


def classify_field(elem: Tag) -> Optional[str]:
    """フォーム要素のフィールドタイプを推定する"""
    if elem.get("type") == "email":
        return "email"
    if elem.get("type") == "tel":
        return "phone"
    if elem.name == "textarea":
        return "message"

    hints = _get_field_hints(elem)

    for field_type, patterns in FIELD_PATTERNS.items():
        for pat in patterns:
            if pat in hints:
                return field_type
    return None


def analyze_form_bs4(form: Tag) -> dict[str, dict]:
    """BS4でフォーム要素を解析しマッピングを作成する

    Args:
        form: form要素

    Returns:
        {フィールドタイプ: {name, tag, type}} のマッピング
    """
    mapping: dict[str, dict] = {}
    skip_types = {"hidden", "submit", "button", "image", "reset"}

    for elem in form.find_all(["input", "textarea", "select"]):
        input_type = elem.get("type", "text")
        if input_type in skip_types:
            continue

        field_type = classify_field(elem)
        if field_type and field_type not in mapping:
            mapping[field_type] = {
                "name": elem.get("name", elem.get("id", "")),
                "tag": elem.name,
                "type": input_type,
            }

    logger.info("BS4解析結果: %s", list(mapping.keys()))
    return mapping
