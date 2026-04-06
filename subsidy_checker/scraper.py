"""Webページ取得・リンク探索モジュール。"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup

from config import (
    MAX_RETRIES,
    REQUEST_INTERVAL,
    REQUEST_TIMEOUT,
    SEARCH_KEYWORDS,
    USER_AGENT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# 最後のリクエスト時刻（レート制限用）
_last_request_time: float = 0.0


def _wait_for_rate_limit() -> None:
    """レート制限を守るためにウェイトを挿入する。"""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_INTERVAL:
        time.sleep(REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def fetch_page(url: str) -> Optional[str]:
    """指定URLのHTMLを取得する。

    Args:
        url: 取得対象のURL

    Returns:
        HTMLテキスト。取得失敗時はNone
    """
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(MAX_RETRIES):
        try:
            _wait_for_rate_limit()
            response = requests.get(
                url, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            # 文字化け対策：apparent_encodingで推定
            response.encoding = response.apparent_encoding
            return response.text
        except requests.exceptions.HTTPError as e:
            logger.warning("HTTP %s エラー: %s (試行 %d)", e.response.status_code, url, attempt + 1)
        except requests.exceptions.Timeout:
            logger.warning("タイムアウト: %s (試行 %d)", url, attempt + 1)
        except requests.exceptions.RequestException as e:
            logger.warning("リクエスト失敗: %s - %s", url, e)
            break
    return None


def fetch_pdf_text(url: str) -> Optional[str]:
    """PDFをダウンロードしてテキストを抽出する。

    Args:
        url: PDFファイルのURL

    Returns:
        抽出テキスト。失敗時はNone
    """
    import tempfile
    headers = {"User-Agent": USER_AGENT}
    try:
        _wait_for_rate_limit()
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        # 一時ファイルに保存して読み取り
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts) if text_parts else None
    except Exception as e:
        logger.warning("PDF取得/解析失敗: %s - %s", url, e)
        return None


def find_subsidy_links(
    base_url: str,
    keywords: Optional[list[str]] = None,
    max_depth: int = 2,
) -> list[dict[str, str]]:
    """市区町村HPから助成金関連ページのリンクを探索する。

    Args:
        base_url: 市区町村HPのトップURL
        keywords: 検索キーワード（デフォルトはconfig値）
        max_depth: 探索階層の深さ

    Returns:
        [{"url": "...", "title": "...", "matched_keyword": "..."}] のリスト
    """
    if keywords is None:
        keywords = SEARCH_KEYWORDS

    html = fetch_page(base_url)
    if html is None:
        return []

    soup = BeautifulSoup(html, "html.parser")
    found_links: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    base_domain = urlparse(base_url).netloc

    # トップページのリンクを走査
    _scan_links(soup, base_url, base_domain, keywords, found_links, seen_urls)

    # 2階層目：見つかったページ内のリンクも走査
    if max_depth >= 2:
        first_level_urls = [link["url"] for link in found_links]
        for page_url in first_level_urls[:10]:  # 最大10ページまで
            page_html = fetch_page(page_url)
            if page_html:
                page_soup = BeautifulSoup(page_html, "html.parser")
                _scan_links(
                    page_soup, page_url, base_domain,
                    keywords, found_links, seen_urls,
                )

    logger.info("%s から %d 件の助成金関連リンクを発見", base_url, len(found_links))
    return found_links


def _scan_links(
    soup: BeautifulSoup,
    current_url: str,
    base_domain: str,
    keywords: list[str],
    found_links: list[dict[str, str]],
    seen_urls: set[str],
) -> None:
    """HTMLからキーワードに合致するリンクを抽出する。

    Args:
        soup: パース済みHTML
        current_url: 現在のページURL
        base_domain: ベースドメイン（同一ドメイン内のみ探索）
        keywords: マッチングキーワード
        found_links: 発見済みリンクリスト（破壊的に追加）
        seen_urls: 探索済みURLセット（重複排除用）
    """
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        full_url = urljoin(current_url, href)
        # 同一ドメインのみ対象
        if urlparse(full_url).netloc != base_domain:
            continue
        if full_url in seen_urls:
            continue

        link_text = a_tag.get_text(strip=True)
        # リンクテキストまたはURLにキーワードが含まれるか
        for kw in keywords:
            if kw in link_text or kw in full_url:
                seen_urls.add(full_url)
                found_links.append({
                    "url": full_url,
                    "title": link_text[:100],
                    "matched_keyword": kw,
                })
                break


def extract_page_text(url: str) -> Optional[str]:
    """URLからテキストを抽出する（HTML/PDF自動判定）。

    Args:
        url: 対象URL

    Returns:
        抽出テキスト。失敗時はNone
    """
    # PDF判定
    if url.lower().endswith(".pdf") or "pdf" in url.lower():
        text = fetch_pdf_text(url)
        if text:
            return text

    # HTML取得
    html = fetch_page(url)
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")
    # 不要タグを除去
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    return soup.get_text(separator="\n", strip=True)


def check_year_validity(url: str, target_year: int = 2026) -> str:
    """昨年の助成金URLが今年度も有効かを判定する。

    Args:
        url: 昨年の助成金ページURL
        target_year: 対象年度

    Returns:
        "有効" / "期限切れ" / "要確認" / "取得失敗"
    """
    text = extract_page_text(url)
    if text is None:
        return "取得失敗"

    # 年度表記のパターン
    current_fy = f"令和{target_year - 2018}年度"  # 2026→令和8年度
    prev_fy = f"令和{target_year - 2019}年度"
    current_western = f"{target_year}年度"
    prev_western = f"{target_year - 1}年度"

    has_current = current_fy in text or current_western in text
    has_prev_only = (prev_fy in text or prev_western in text) and not has_current

    # 終了・締切の表現を検索
    expired_patterns = ["受付終了", "募集終了", "終了しました", "受付は締め切り"]
    is_expired = any(p in text for p in expired_patterns)

    if has_current and not is_expired:
        return "有効"
    if is_expired or has_prev_only:
        return "期限切れ"
    return "要確認"
