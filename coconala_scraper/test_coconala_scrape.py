"""coconala_scrape.py のセルフテスト（pytestで実行）"""

import re
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

# ------------------------------------------------------------------ #
#  utils モジュールをモックに差し替え（実環境依存を排除）
# ------------------------------------------------------------------ #

mock_utils = types.ModuleType("coconala_scraper.utils")
mock_utils.gs_client = MagicMock()
mock_utils.print_log = lambda msg: print(f"[LOG] {msg}")
mock_utils.random_sleep = MagicMock()
mock_utils.chrome_driver = MagicMock()
sys.modules["coconala_scraper.utils"] = mock_utils

from coconala_scraper.coconala_scrape import CoconaláScrape  # noqa: E402
from bs4 import BeautifulSoup as BS  # noqa: E402


# ------------------------------------------------------------------ #
#  ヘルパー
# ------------------------------------------------------------------ #

def make_scrape(**kwargs) -> CoconaláScrape:
    """テスト用インスタンスを生成する"""
    defaults = dict(
        job_category="デザイン制作",
        gs_key="DUMMY_KEY",
        gs_sheet_name="テスト",
        limit=0,
    )
    defaults.update(kwargs)
    return CoconaláScrape(**defaults)


def make_soup(html: str) -> BS:
    return BS(html, "html.parser")


# ------------------------------------------------------------------ #
#  1. __init__ の初期化テスト
# ------------------------------------------------------------------ #

class TestInit(unittest.TestCase):

    def test_normal_init(self):
        """正常系: 全パラメータが正しく設定され、list_urlが職種IDから組み立てられる"""
        s = make_scrape(limit=10, job_category="デザイン制作")
        self.assertIn("experienceJobCategoryId=18", s.list_url)
        self.assertEqual(s.gs_key, "DUMMY_KEY")
        self.assertEqual(s.gs_sheet_name, "テスト")
        self.assertEqual(s.limit, 10)
        self.assertEqual(s.user_paths, [])
        self.assertEqual(s.users, [])

    def test_default_limit_is_zero(self):
        """正常系: limitのデフォルト値は0（全件）"""
        s = make_scrape()
        self.assertEqual(s.limit, 0)

    def test_default_last_login_is_no_filter(self):
        """正常系: last_login_withinのデフォルトは絞り込まない（None）"""
        s = make_scrape()
        self.assertIsNone(s.last_login_within_days)

    def test_invalid_job_category_raises(self):
        """異常系: 未定義の職種名を指定するとValueErrorになる"""
        with self.assertRaises(ValueError):
            make_scrape(job_category="存在しない職種")

    def test_invalid_last_login_option_raises(self):
        """異常系: 未定義の最終ログイン選択肢を指定するとValueErrorになる"""
        with self.assertRaises(ValueError):
            make_scrape(last_login_within="存在しない選択肢")

    def test_last_login_within_days_mapping(self):
        """境界値: 「1週間以内」が7日に正しくマッピングされる"""
        s = make_scrape(last_login_within="1週間以内")
        self.assertEqual(s.last_login_within_days, 7)


# ------------------------------------------------------------------ #
#  2. __get_next_page_url テスト
# ------------------------------------------------------------------ #

class TestGetNextPageUrl(unittest.TestCase):

    def setUp(self):
        self.s = make_scrape()

    def test_finds_page_param(self):
        """正常系: ?page=N 形式の次ページリンクを正しく返す"""
        html = '<a href="/users?page=2">次へ</a>'
        soup = make_soup(html)
        result = self.s._CoconaláScrape__get_next_page_url(soup, 1)
        self.assertIsNotNone(result)
        self.assertIn("page=2", result)

    def test_finds_next_text_link(self):
        """正常系: 「次へ」テキストを持つリンクを返す"""
        html = '<a href="/users?page=3">次へ</a>'
        soup = make_soup(html)
        result = self.s._CoconaláScrape__get_next_page_url(soup, 2)
        self.assertIsNotNone(result)
        self.assertIn("page=3", result)

    def test_returns_none_when_no_next(self):
        """異常系: 次ページリンクがない場合はNoneを返す"""
        html = '<a href="/users?page=1">1</a>'
        soup = make_soup(html)
        result = self.s._CoconaláScrape__get_next_page_url(soup, 1)
        self.assertIsNone(result)

    def test_returns_none_on_empty_html(self):
        """異常系: HTMLが空の場合はNoneを返す"""
        soup = make_soup("")
        result = self.s._CoconaláScrape__get_next_page_url(soup, 1)
        self.assertIsNone(result)

    def test_absolute_url_returned_as_is(self):
        """境界値: 絶対URLのリンクはそのまま返す"""
        html = '<a href="https://coconala.com/users?page=2">次へ</a>'
        soup = make_soup(html)
        result = self.s._CoconaláScrape__get_next_page_url(soup, 1)
        self.assertEqual(result, "https://coconala.com/users?page=2")


# ------------------------------------------------------------------ #
#  3. __fetch_user_paths のユーザーID抽出ロジックテスト
# ------------------------------------------------------------------ #

class TestUserPathExtraction(unittest.TestCase):
    """一覧ページのリンク抽出ロジックをユニットテスト"""

    def _extract_paths(self, html: str, limit: int = 0):
        """テスト用: HTMLからユーザーパスを抽出するロジックを再現"""
        COCONALA_HOST = "https://coconala.com"
        soup = make_soup(html)
        seen = set()
        paths = []
        for link in soup.select("a[href*='/users/']"):
            href = link.get("href", "")
            if href.startswith(COCONALA_HOST):
                path = href[len(COCONALA_HOST):]
            else:
                path = href
            path_only = path.split("?")[0]
            parts = path_only.rstrip("/").split("/")
            if (
                len(parts) == 3
                and parts[1] == "users"
                and parts[2].isdigit()
                and path_only not in seen
            ):
                seen.add(path_only)
                paths.append(path_only)
                if limit != 0 and len(paths) >= limit:
                    break
        return paths

    def test_extracts_user_ids(self):
        """正常系: /users/数字 リンクを正しく抽出する"""
        html = '''
        <a href="/users/123">ユーザーA</a>
        <a href="/users/456">ユーザーB</a>
        '''
        paths = self._extract_paths(html)
        self.assertEqual(paths, ["/users/123", "/users/456"])

    def test_excludes_search_and_non_numeric(self):
        """正常系: /users/search など数字以外のパスを除外する"""
        html = '''
        <a href="/users/search">検索</a>
        <a href="/users/123">ユーザーA</a>
        <a href="/users/ranking">ランキング</a>
        '''
        paths = self._extract_paths(html)
        self.assertEqual(paths, ["/users/123"])

    def test_deduplication(self):
        """正常系: 同じユーザーIDは重複しない"""
        html = '''
        <a href="/users/123">ユーザーA</a>
        <a href="/users/123">ユーザーA（再掲）</a>
        '''
        paths = self._extract_paths(html)
        self.assertEqual(paths, ["/users/123"])

    def test_limit_respected(self):
        """境界値: limitが指定された場合はそれ以上取得しない"""
        html = "".join(f'<a href="/users/{i}">U{i}</a>' for i in range(10))
        paths = self._extract_paths(html, limit=3)
        self.assertEqual(len(paths), 3)

    def test_empty_html_returns_empty(self):
        """異常系: リンクが1件もない場合は空リストを返す"""
        paths = self._extract_paths("<div>コンテンツなし</div>")
        self.assertEqual(paths, [])


# ------------------------------------------------------------------ #
#  4. __get_stat_by_label テスト（モックdriver使用）
# ------------------------------------------------------------------ #

class TestGetStatByLabel(unittest.TestCase):

    def setUp(self):
        self.s = make_scrape()

    def _make_driver_with_text(self, label: str, full_text: str):
        """指定テキストを持つ要素を返すモックdriverを生成"""
        elem = MagicMock()
        elem.text = full_text
        parent = MagicMock()
        parent.text = full_text
        elem.find_element.return_value = parent
        driver = MagicMock()
        driver.find_elements.return_value = [elem]
        return driver

    def test_extracts_sales_count(self):
        """正常系: 「販売実績 1,234」から数値を取得する"""
        driver = self._make_driver_with_text("販売実績", "販売実績 1,234")
        result = self.s._CoconaláScrape__get_stat_by_label(driver, "販売実績")
        self.assertEqual(result, "1234")

    def test_extracts_followers(self):
        """正常系: 「フォロワー 567」から数値を取得する"""
        driver = self._make_driver_with_text("フォロワー", "フォロワー 567")
        result = self.s._CoconaláScrape__get_stat_by_label(driver, "フォロワー")
        self.assertEqual(result, "567")

    def test_returns_empty_when_no_element(self):
        """異常系: 対象要素が存在しない場合は空文字を返す"""
        driver = MagicMock()
        driver.find_elements.return_value = []
        result = self.s._CoconaláScrape__get_stat_by_label(driver, "販売実績")
        self.assertEqual(result, "")


# ------------------------------------------------------------------ #
#  5. __parse_last_login_to_days テスト
# ------------------------------------------------------------------ #

class TestParseLastLoginToDays(unittest.TestCase):

    def setUp(self):
        self.s = make_scrape()

    def test_minutes_ago_is_zero_days(self):
        """正常系: 「24分前」は0日として扱う"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("24分前")
        self.assertEqual(result, 0.0)

    def test_days_ago(self):
        """正常系: 「3日前」は3.0日に変換される"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("3日前")
        self.assertEqual(result, 3.0)

    def test_weeks_ago(self):
        """正常系: 「2週間前」は14.0日に変換される"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("2週間前")
        self.assertEqual(result, 14.0)

    def test_unparseable_text_returns_none(self):
        """異常系: 解析不能な文字列はNoneを返す"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("不明なステータス")
        self.assertIsNone(result)

    def test_empty_text_returns_none(self):
        """異常系: 空文字はNoneを返す"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("")
        self.assertIsNone(result)

    def test_months_ago(self):
        """境界値: 「1ヶ月前」は30.0日に変換される"""
        result = self.s._CoconaláScrape__parse_last_login_to_days("1ヶ月前")
        self.assertEqual(result, 30.0)


# ------------------------------------------------------------------ #
#  6. __filter_by_last_login テスト
# ------------------------------------------------------------------ #

class TestFilterByLastLogin(unittest.TestCase):

    def _make_user_row(self, last_login_text: str) -> list:
        """列インデックス6が最終ログインの9列ダミー行を作る"""
        return ["名前", "1", "url", "5.0", "10", "3", last_login_text, "デザイン", "2"]

    def test_filters_within_range(self):
        """正常系: 範囲内のユーザーのみ残る"""
        s = make_scrape(last_login_within="1週間以内")
        s.users = [
            self._make_user_row("3日前"),   # 残る
            self._make_user_row("2ヶ月前"),  # 除外される
        ]
        s._CoconaláScrape__filter_by_last_login()
        self.assertEqual(len(s.users), 1)
        self.assertEqual(s.users[0][6], "3日前")

    def test_no_filter_keeps_all(self):
        """正常系: 「絞り込まない」の場合は全件残す"""
        s = make_scrape(last_login_within="絞り込まない")
        s.users = [
            self._make_user_row("3日前"),
            self._make_user_row("2ヶ月前"),
        ]
        s._CoconaláScrape__filter_by_last_login()
        self.assertEqual(len(s.users), 2)

    def test_unparseable_login_kept(self):
        """異常系: 最終ログインが解析不能な行は誤除外せず残す"""
        s = make_scrape(last_login_within="1日以内")
        s.users = [self._make_user_row("不明")]
        s._CoconaláScrape__filter_by_last_login()
        self.assertEqual(len(s.users), 1)

    def test_empty_users_stays_empty(self):
        """境界値: usersが空リストの場合は空リストのまま"""
        s = make_scrape(last_login_within="1日以内")
        s.users = []
        s._CoconaláScrape__filter_by_last_login()
        self.assertEqual(s.users, [])

    def test_boundary_exact_days(self):
        """境界値: ちょうど7日前は「1週間以内」に含まれる"""
        s = make_scrape(last_login_within="1週間以内")
        s.users = [self._make_user_row("7日前")]
        s._CoconaláScrape__filter_by_last_login()
        self.assertEqual(len(s.users), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
