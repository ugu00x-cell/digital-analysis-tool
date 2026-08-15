"""
V0 リンク集ページ収集スクレイパー

製造業・工業系の「リンク集」「会員一覧」ページを
DDGs検索 + 同一ドメイン浅探索で収集し、CSVに保存する。
"""

import csv
import logging
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from tqdm import tqdm

# ──────────────────────────────────────────
# ログ設定
# ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('v0_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────
# 設定（ここだけ変えれば動作が変わる）
# ──────────────────────────────────────────
SEARCH_QUERIES: list[str] = [
    '"製造業 リンク集"',
    '"企業リンク集"',
    '"工業組合 会員一覧"',
    '"協会 会員企業 一覧"',
]

# ページ本文・タイトルでヒットさせるキーワード
PAGE_KEYWORDS: list[str] = ["リンク", "一覧", "企業", "会員", "加盟"]

# URLに含まれていたらリンク集っぽいと判断する文字列
URL_KEYWORDS: list[str] = ["link", "member", "list", "ichiran", "kaiin", "kigyo"]

# これ以上の外部リンク数があればリンク集と判定
MIN_LINK_COUNT: int = 10

# スキップするドメイン（大手ポータル・SNSは除外）
EXCLUDE_DOMAINS: list[str] = [
    "wikipedia.org", "twitter.com", "facebook.com",
    "youtube.com", "amazon.co.jp", "rakuten.co.jp",
    "linkedin.com", "instagram.com",
]

SLEEP_SEC: float = 1.5          # リクエスト間隔（秒）
REQUEST_TIMEOUT: int = 10       # タイムアウト（秒）
OUTPUT_FILE: str = "input_urls.csv"

HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ──────────────────────────────────────────
# ユーティリティ関数
# ──────────────────────────────────────────

def is_same_domain(url1: str, url2: str) -> bool:
    """2つのURLが同一ドメインかどうかを判定する"""
    return urlparse(url1).netloc == urlparse(url2).netloc


def is_excluded(url: str) -> bool:
    """除外ドメインに含まれているかチェックする"""
    domain = urlparse(url).netloc
    return any(ex in domain for ex in EXCLUDE_DOMAINS)


def count_external_links(soup: BeautifulSoup, base_url: str) -> int:
    """ページ内にある外部リンクの数を数える"""
    count = 0
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if href.startswith("http") and not is_same_domain(base_url, href):
            count += 1
    return count


def is_target_page(soup: BeautifulSoup, url: str) -> bool:
    """
    リンク集っぽいページかどうかを判定する。
    タイトル・見出し・URLキーワード・外部リンク数で総合判断。
    """
    # URLパターンで引っかかるか
    url_hit = any(kw in url.lower() for kw in URL_KEYWORDS)

    # タイトル・見出しにキーワードが含まれるか（全文チェックは精度が低いので絞る）
    target_tags = [soup.title, *soup.find_all(["h1", "h2", "h3", "nav"])]
    heading_text = " ".join(t.get_text() for t in target_tags if t)
    heading_hit = any(kw in heading_text for kw in PAGE_KEYWORDS)

    # 本文の先頭3000文字にキーワードが含まれるか
    body_text = soup.get_text()[:3000]
    body_hit = any(kw in body_text for kw in PAGE_KEYWORDS)

    # 外部リンクが一定数以上あるか
    link_count = count_external_links(soup, url)
    link_hit = link_count >= MIN_LINK_COUNT

    # 条件：（URLかタイトル）AND（本文）AND（リンク数）
    return (url_hit or heading_hit) and body_hit and link_hit


# ──────────────────────────────────────────
# 検索・スクレイピング関数
# ──────────────────────────────────────────

def search_ddgs(query: str, max_results: int = 20) -> list[str]:
    """
    DuckDuckGo（ddgsライブラリ）で検索し、結果URLのリストを返す。
    失敗した場合は空リストを返す。
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        # 除外ドメインを除いたURLだけ返す
        links = [
            r["href"] for r in results
            if r.get("href", "").startswith("http") and not is_excluded(r["href"])
        ]
        logger.info(f"  DDGs検索完了: {len(links)}件取得 [{query}]")
        return links

    except Exception as e:
        logger.warning(f"  DDGs検索失敗: {e} [{query}]")
        return []


def fetch_page(url: str) -> BeautifulSoup | None:
    """
    指定URLのHTMLを取得してBeautifulSoupで返す。
    失敗したらNoneを返す。
    """
    try:
        res = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        res.raise_for_status()
        return BeautifulSoup(res.text, "html.parser")
    except requests.RequestException as e:
        logger.debug(f"  取得失敗: {url} → {e}")
        return None


def explore_same_domain(base_url: str, soup: BeautifulSoup) -> list[str]:
    """
    同一ドメイン内のリンクを浅く探索し、
    アンカーテキストまたはURLがキーワードにヒットするURLを返す。
    """
    candidates = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if not href.startswith("http"):
            continue
        if not is_same_domain(base_url, href):
            continue
        if href == base_url:
            continue

        # アンカーテキストかURLどちらかがキーワードにヒットすれば候補に追加
        text = a.get_text()
        text_hit = any(kw in text for kw in PAGE_KEYWORDS)
        url_hit = any(kw in href.lower() for kw in URL_KEYWORDS)

        if text_hit or url_hit:
            candidates.append(href)

    return list(set(candidates))


# ──────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────

def run() -> None:
    """
    検索 → ページ取得 → リンク集判定 → CSV保存
    の一連の処理を実行する。
    """
    results: set[str] = set()

    for query in tqdm(SEARCH_QUERIES, desc="検索クエリ"):
        search_links = search_ddgs(query)
        time.sleep(SLEEP_SEC)

        for link in tqdm(search_links, desc="ページ探索", leave=False):
            soup = fetch_page(link)
            if soup is None:
                continue

            # 検索でヒットしたページ自体を判定
            if is_target_page(soup, link):
                results.add(link)
                logger.info(f"  ✅ ヒット: {link}")

            # 同一ドメイン内を浅く探索
            candidates = explore_same_domain(link, soup)
            for candidate in candidates:
                if candidate in results:
                    continue
                sub_soup = fetch_page(candidate)
                if sub_soup and is_target_page(sub_soup, candidate):
                    results.add(candidate)
                    logger.info(f"  ✅ ヒット（同一ドメイン）: {candidate}")
                time.sleep(SLEEP_SEC)

            time.sleep(SLEEP_SEC)

    # CSV保存
    save_results(results)
    logger.info(f"\nV0完了: {len(results)}件 → {OUTPUT_FILE}")


def save_results(results: set[str]) -> None:
    """
    収集したURLをCSVに保存する。
    BOM付きUTF-8でExcelでも文字化けしない。
    """
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["company_name", "url"])
        for url in sorted(results):
            writer.writerow(["seed", url])
    logger.info(f"{OUTPUT_FILE} に {len(results)} 件を保存しました")


if __name__ == "__main__":
    run()
