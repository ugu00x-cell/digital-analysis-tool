"""SUUMO・HOLMES スクレイピング"""

import logging
import time
from typing import Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SuumoScraper:
    """
    SUUMO・HOLMES の物件詳細ページから情報を抽出するクラス
    """

    def __init__(self, headless: bool = True, timeout: int = 10):
        """
        Selenium ドライバーを初期化

        Args:
            headless: ヘッドレスモードで実行するか
            timeout: ページ読み込み待機タイムアウト（秒）
        """
        self.timeout = timeout
        self.driver = self._init_driver(headless)
        logger.info("SuumoScraper initialized")

    def _init_driver(self, headless: bool) -> webdriver.Chrome:
        """
        Chrome WebDriver を初期化

        Args:
            headless: ヘッドレスモードで実行するか

        Returns:
            WebDriver インスタンス
        """
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            driver = webdriver.Chrome(options=options)
            logger.info("Chrome WebDriver initialized")
            return driver
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    def scrape_property_details(self, url: str) -> Dict[str, Any]:
        """
        物件詳細ページから情報を抽出

        Args:
            url: SUUMO・HOLMES の物件詳細URL

        Returns:
            抽出した情報の辞書
        """
        if not url:
            logger.warning("URL is empty")
            return {}

        try:
            logger.info(f"Scraping URL: {url}")
            self.driver.get(url)

            # ページの読み込み待機
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            time.sleep(2)  # 動的コンテンツの読み込み待機

            # ページのHTMLを取得
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # 情報を抽出
            property_info = {
                "total_units": self._extract_total_units(soup),
                "stories": self._extract_stories(soup),
                "walking_minutes": self._extract_walking_minutes(soup),
                "land_rights": self._extract_land_rights(soup),
            }

            logger.info(f"Extracted info: {property_info}")
            return property_info

        except Exception as e:
            logger.error(f"Scraping failed for URL {url}: {e}")
            return {}

    def _extract_total_units(self, soup: BeautifulSoup) -> Optional[str]:
        """
        総戸数を抽出

        「戸」の直前の数字だけを正規表現で厳密に取り出し、
        1〜9999の妥当な範囲かを検証してから返す（無関係な数字の混入を防ぐ）。

        Args:
            soup: BeautifulSoup オブジェクト

        Returns:
            総戸数（文字列）。見つからない場合は None
        """
        import re

        def extract_valid_number(text: str) -> Optional[str]:
            """「◯◯戸」の直前の数字を正規表現で抽出し、妥当性を検証する"""
            # 「123戸」「総戸数：123戸」のように、数字の直後に「戸」が続くパターンのみを対象にする
            matches = re.findall(r'(\d{1,4})\s*戸', text)
            for m in matches:
                num = int(m)
                if 1 <= num <= 9999:  # 総戸数として妥当な範囲
                    return str(num)
            return None

        # パターン1：テーブル形式（ラベルセルが「総戸数」に完全一致するものを優先）
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = cells[0].text.strip()
            if label in ("総戸数", "総戸数（総区画数）") or label.startswith("総戸数"):
                value_text = cells[1].text.strip()
                result = extract_valid_number(value_text)
                if result:
                    logger.debug(f"Extracted total units (pattern 1, exact label): {result}")
                    return result

        # パターン1b：ラベルに「戸数」を含む行（部分一致・フォールバック）
        for row in soup.find_all("tr"):
            if "戸数" in row.text:
                cells = row.find_all(["th", "td"])
                if len(cells) > 1:
                    value_text = cells[1].text.strip()
                    result = extract_valid_number(value_text)
                    if result:
                        logger.debug(f"Extracted total units (pattern 1b, partial label): {result}")
                        return result

        # パターン2：リスト形式（dt/dd等）
        patterns = [
            ("dt", "総戸数"),
            ("dd.property-info__values", ""),
            ("li", "戸数"),
        ]

        for selector, keyword in patterns:
            elements = soup.select(selector)
            for elem in elements:
                if keyword in elem.text:
                    result = extract_valid_number(elem.text.strip())
                    if result:
                        logger.debug(f"Extracted total units (pattern 2): {result}")
                        return result

        logger.debug("Total units not found")
        return None

    def _extract_stories(self, soup: BeautifulSoup) -> Optional[str]:
        """
        地上階数を抽出

        Args:
            soup: BeautifulSoup オブジェクト

        Returns:
            階数（文字列）。見つからない場合は None
        """
        patterns = [
            ("dd.property-info__values", "地上"),
            ("div.property-detail__item", "階"),
        ]

        for selector, keyword in patterns:
            elements = soup.select(selector)
            for elem in elements:
                if keyword in elem.text:
                    text = elem.text.strip()
                    numbers = "".join(filter(str.isdigit, text.split("階")[0]))
                    if numbers:
                        logger.debug(f"Extracted stories: {numbers}")
                        return numbers

        logger.debug("Stories not found")
        return None

    def _extract_walking_minutes(self, soup: BeautifulSoup) -> Optional[str]:
        """
        徒歩分数を抽出

        Args:
            soup: BeautifulSoup オブジェクト

        Returns:
            徒歩分数（文字列）。見つからない場合は None
        """
        patterns = [
            ("dd.property-info__values", "徒歩"),
            ("span.icon-walk", ""),
        ]

        for selector, keyword in patterns:
            elements = soup.select(selector)
            for elem in elements:
                if keyword in elem.text or "分" in elem.text:
                    text = elem.text.strip()
                    numbers = "".join(filter(str.isdigit, text.split("分")[0]))
                    if numbers:
                        logger.debug(f"Extracted walking minutes: {numbers}")
                        return numbers

        logger.debug("Walking minutes not found")
        return None

    def _extract_land_rights(self, soup: BeautifulSoup) -> Optional[str]:
        """
        土地の権利区分を抽出

        Args:
            soup: BeautifulSoup オブジェクト

        Returns:
            権利区分（文字列）。見つからない場合は None
        """
        patterns = [
            ("dd.property-info__values", "権利"),
            ("div.property-detail__item", "権利"),
        ]

        for selector, keyword in patterns:
            elements = soup.select(selector)
            for elem in elements:
                if keyword in elem.text:
                    text = elem.text.strip()
                    logger.debug(f"Extracted land rights: {text}")
                    return text

        logger.debug("Land rights not found")
        return None

    def close(self) -> None:
        """
        WebDriver を終了
        """
        try:
            self.driver.quit()
            logger.info("WebDriver closed")
        except Exception as e:
            logger.error(f"Failed to close WebDriver: {e}")
