"""ココナラ ユーザー情報スクレイピングモジュール"""

import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Set

from bs4 import BeautifulSoup as BS
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .utils import gs_client, print_log, random_sleep, chrome_driver


class CoconaláScrape:
    """ココナラのユーザー情報を収集し、Googleスプレッドシートに書き込むクラス"""

    # 設定
    COCONALA_HOST = "https://coconala.com"
    INTERVAL_TIME = 1.5

    # 職種（大カテゴリ）名 → experienceJobCategoryId 対応表
    # ノートブック上で選択式にする際はこのキー一覧を選択肢として使う
    JOB_CATEGORIES = {
        "イラスト作成・漫画制作": 9,
        "デザイン制作": 18,
        "Web制作・HP作成・EC構築": 22,
        "動画編集・映像制作": 10,
        "集客・マーケティング相談": 16,
        "ビジネス代行・事務代行": 13,
        "音楽制作・ナレーション": 23,
        "IT相談・システム開発": 11,
        "ライティング・翻訳": 19,
        "コンサルティング・士業": 27,
        "生成AI活用・開発・制作": 28,
        "占い": 3,
        "悩み相談・カウンセリング": 2,
        "学習指導・資格・キャリア相談": 12,
        "住まい・美容・生活相談": 5,
        "オンラインレッスン・習い事": 26,
        "ハンドメイド制作": 1001,
        "出張撮影・出張サービス": 29,
        "資産運用・副業の相談": 17,
    }

    # 最終ログイン絞り込みの選択肢（表示名 → 何日以内か）
    # ノートブック上で選択式にする際はこのキー一覧を選択肢として使う
    LAST_LOGIN_OPTIONS = {
        "絞り込まない": None,
        "1日以内": 1,
        "1週間以内": 7,
        "1ヶ月以内": 30,
        "3ヶ月以内": 90,
    }

    def __init__(
        self,
        job_category: str,
        gs_key: str,
        gs_sheet_name: str,
        limit: int = 0,
        last_login_within: str = "絞り込まない",
    ) -> None:
        """
        Args:
            job_category: 職種名。JOB_CATEGORIES のキーのいずれかを指定する
            gs_key: GoogleスプレッドシートのキーID
            gs_sheet_name: 書き込み先シート名
            limit: 取得件数上限（0=全件）
            last_login_within: 最終ログインの絞り込み。LAST_LOGIN_OPTIONS のキーのいずれかを指定する
                （ココナラ側にURLパラメータが無いため、取得後にツール側でフィルタリングする）
        """
        if job_category not in self.JOB_CATEGORIES:
            raise ValueError(
                f"job_categoryは次のいずれかを指定してください: {list(self.JOB_CATEGORIES.keys())}"
            )
        if last_login_within not in self.LAST_LOGIN_OPTIONS:
            raise ValueError(
                f"last_login_withinは次のいずれかを指定してください: {list(self.LAST_LOGIN_OPTIONS.keys())}"
            )

        category_id = self.JOB_CATEGORIES[job_category]
        self.list_url = f"{self.COCONALA_HOST}/users/search?experienceJobCategoryId={category_id}"
        self.job_category = job_category
        self.last_login_within_days = self.LAST_LOGIN_OPTIONS[last_login_within]
        self.gs_key = gs_key
        self.gs_sheet_name = gs_sheet_name
        self.limit = limit
        self.lock = threading.Lock()
        self.user_paths: List[str] = []
        self.users: List[list] = []

    def exec(self) -> None:
        """メイン実行: ユーザー一覧取得 → 詳細取得 → 最終ログイン絞り込み → スプレッドシート書き込み"""
        print_log(f"職種「{self.job_category}」でユーザー一覧の読み込みを開始します。")
        self.__fetch_user_paths()
        print_log(f"ユーザー一覧の読み込みを終了します。（{len(self.user_paths)}件）")
        self.__fetch_user_details()
        print_log(f"ユーザー詳細取得完了。（{len(self.users)}件）")

        if self.last_login_within_days is not None:
            before_count = len(self.users)
            self.__filter_by_last_login()
            print_log(
                f"最終ログイン絞り込み完了。（{before_count}件 → {len(self.users)}件）"
            )

        print_log("スプレッドシートの書き込みを開始します。")
        self.__write_to_spreadsheet()
        print_log("スプレッドシートの書き込みを終了します。")

    # ------------------------------------------------------------------ #
    #  ユーザー一覧ページからプロフィールURLを収集
    # ------------------------------------------------------------------ #

    def __fetch_user_paths(self) -> None:
        """ユーザー一覧ページからプロフィールパスを取得する（Selenium使用）"""
        seen: Set[str] = set()
        limit_reached = False
        current_url = self.list_url
        page_num = 1

        while True:
            driver, wait = chrome_driver()
            try:
                driver.get(current_url)

                # ユーザーカードが描画されるまで待機
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[href*='/users/']")
                        )
                    )
                except TimeoutException:
                    print_log(f"ページ{page_num}: ユーザーリンクが見つかりませんでした。終了します。")
                    break

                soup = BS(driver.page_source, "html.parser")
            finally:
                driver.quit()

            # /users/数字 のパスのみ抽出（/users/search 等は除外）
            all_links = soup.select("a[href*='/users/']")
            page_count = 0

            for link in all_links:
                href = link.get("href", "")

                # 絶対URLを相対パスに正規化
                if href.startswith(self.COCONALA_HOST):
                    path = href[len(self.COCONALA_HOST):]
                else:
                    path = href

                # クエリパラメータを除去
                path_only = path.split("?")[0]

                # /users/数字 の形式のみ対象（/users/search 等は除外）
                parts = path_only.rstrip("/").split("/")
                if (
                    len(parts) == 3
                    and parts[1] == "users"
                    and parts[2].isdigit()
                    and path_only not in seen
                ):
                    seen.add(path_only)
                    self.user_paths.append(path_only)
                    page_count += 1
                    if self.limit != 0 and len(self.user_paths) >= self.limit:
                        limit_reached = True
                        break

            print_log(f"ページ{page_num}: {page_count}件取得（累計: {len(self.user_paths)}件）")

            if limit_reached:
                break

            # 次ページURLを取得
            next_url = self.__get_next_page_url(soup, page_num)
            if next_url is None:
                print_log(f"ページ{page_num}で次ページリンクが見つかりませんでした。")
                break

            current_url = next_url
            time.sleep(self.INTERVAL_TIME)
            page_num += 1

        print_log(f"ユーザーURL取得完了: {len(self.user_paths)}件")

    def __get_next_page_url(self, soup: BS, current_page: int) -> Optional[str]:
        """次ページのURLを返す。見つからない場合はNoneを返す"""
        # ?page=N 形式のリンクから次ページを探す
        next_page = current_page + 1

        # パターン1: <a href="...?page=N"> または <a href="...page/N">
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if f"page={next_page}" in href or f"page/{next_page}" in href:
                if href.startswith("http"):
                    return href
                return self.COCONALA_HOST + href

        # パターン2: "次へ" テキストを持つリンク
        for link in soup.select("a"):
            text = link.get_text(strip=True)
            if "次へ" in text or "次のページ" in text:
                href = link.get("href", "")
                if not href:
                    return None
                if href.startswith("http"):
                    return href
                return self.COCONALA_HOST + href

        return None

    # ------------------------------------------------------------------ #
    #  ユーザー詳細情報を並列取得
    # ------------------------------------------------------------------ #

    def __fetch_user_details(self) -> None:
        """マルチスレッドでユーザー詳細情報を取得する"""
        user_count = len(self.user_paths)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for i, user_path in enumerate(self.user_paths, start=1):
                future = executor.submit(self.__fetch_single_user, i, user_count, user_path)
                futures.append(future)

            for future in as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    print_log(f"ユーザー取得中に予期しないエラー: {exc}")

    def __fetch_single_user(self, index: int, total: int, user_path: str) -> None:
        """個別ユーザーの詳細情報を取得する"""
        user_url = self.COCONALA_HOST + user_path

        if index == 1 or index % 10 == 0 or index == total:
            print_log(f"ユーザー詳細読み込み中。{index}/{total}")

        driver, wait = chrome_driver()
        try:
            driver.get(user_url)

            # ユーザー名が表示されるまで待機
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

            # ユーザー名
            username = self.__safe_find_text(driver, By.TAG_NAME, "h1")

            # 評価スコア（複数セレクターで試みる）
            evaluation = self.__get_evaluation(driver)

            # 販売実績件数
            sales_count = self.__get_stat_by_label(driver, "販売実績")

            # フォロワー数
            followers = self.__get_stat_by_label(driver, "フォロワー")

            # 最終ログイン
            last_login = self.__get_last_login(driver)

            # カテゴリ（出品サービスのカテゴリ）
            categories = self.__get_categories(driver)

            # 出品サービス数
            service_count = self.__get_service_count(driver)

            with self.lock:
                self.users.append(
                    [
                        f'=HYPERLINK("{user_url}","{username}")',
                        username,
                        user_url,
                        evaluation,
                        sales_count,
                        followers,
                        last_login,
                        categories,
                        service_count,
                    ]
                )

            random_sleep()

        except TimeoutException:
            print_log(f"{user_url} がタイムアウトしました。スキップします。")
        except Exception as e:
            print_log(f"{user_url} 異常が発生しました。スキップします。")
            print_log(str(e))
        finally:
            driver.quit()

    # ------------------------------------------------------------------ #
    #  各フィールド取得ヘルパー（要素が変わっても壊れにくい設計）
    # ------------------------------------------------------------------ #

    def __safe_find_text(self, driver, by, selector: str, default: str = "") -> str:
        """要素を安全に取得してテキストを返す。見つからない場合はdefaultを返す"""
        try:
            elem = driver.find_element(by, selector)
            return elem.text.strip()
        except Exception:
            return default

    def __get_evaluation(self, driver) -> str:
        """評価スコアを取得する（複数セレクターでフォールバック）"""
        # セレクター候補リスト（上から順に試みる）
        selectors = [
            (By.CSS_SELECTOR, "[class*='evaluation'] [class*='score']"),
            (By.CSS_SELECTOR, "[class*='rating'] [class*='score']"),
            (By.CSS_SELECTOR, "[class*='rating']"),
            (By.XPATH, "//*[contains(text(),'評価')]/following-sibling::*[1]"),
        ]
        for by, selector in selectors:
            try:
                elem = driver.find_element(by, selector)
                text = elem.text.strip()
                if text and re.search(r"\d+\.?\d*", text):
                    return text
            except Exception:
                continue

        # フォールバック: ページ全体から評価スコアらしい数値を探す
        try:
            page_source = driver.page_source
            match = re.search(r'"averageScore":\s*([\d.]+)', page_source)
            if match:
                return match.group(1)
        except Exception:
            pass

        return ""

    def __get_stat_by_label(self, driver, label: str) -> str:
        """「販売実績」「フォロワー」等のラベルに隣接する数値を取得する"""
        try:
            # ラベルテキストを含む要素の隣の数値要素を探す
            elems = driver.find_elements(By.XPATH, f"//*[contains(text(),'{label}')]")
            for elem in elems:
                # 親要素内で数値を探す
                parent = elem.find_element(By.XPATH, "..")
                nums = re.findall(r"[\d,]+", parent.text)
                if nums:
                    return nums[0].replace(",", "")
        except Exception:
            pass
        return ""

    def __get_last_login(self, driver) -> str:
        """最終ログイン情報を取得する"""
        try:
            elems = driver.find_elements(
                By.XPATH, "//*[contains(text(),'ログイン')]"
            )
            for elem in elems:
                text = elem.text.strip()
                if "最終ログイン" in text or "ログイン" in text:
                    # 「最終ログイン：24分前」→「24分前」
                    cleaned = re.sub(r"最終ログイン[：:]\s*", "", text).strip()
                    if cleaned:
                        return cleaned
        except Exception:
            pass
        return ""

    def __get_categories(self, driver) -> str:
        """カテゴリ情報をカンマ区切りで取得する"""
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, "a[href*='/categories/']")
            cats = list(dict.fromkeys([e.text.strip() for e in elems if e.text.strip()]))
            return "、".join(cats[:3])  # 最大3カテゴリ
        except Exception:
            return ""

    def __get_service_count(self, driver) -> str:
        """出品サービス数を取得する"""
        try:
            elems = driver.find_elements(
                By.XPATH, "//*[contains(text(),'出品サービス')]"
            )
            for elem in elems:
                nums = re.findall(r"\d+", elem.text)
                if nums:
                    return nums[0]
        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------ #
    #  最終ログイン絞り込み（ココナラ側にURLパラメータが無いため後段フィルタ）
    # ------------------------------------------------------------------ #

    def __parse_last_login_to_days(self, text: str) -> Optional[float]:
        """「3日前」「2週間前」等の日本語表記を経過日数（float）に変換する。
        解析できない場合はNoneを返す（絞り込み対象外として扱う）
        """
        if not text:
            return None

        text = text.strip()

        if "たった今" in text or "オンライン" in text:
            return 0.0

        # 分・時間前 → 1日未満扱い
        if re.search(r"分前|時間前", text):
            return 0.0

        patterns = [
            (r"(\d+)\s*日前", 1),
            (r"(\d+)\s*週間前", 7),
            (r"(\d+)\s*ヶ月前|(\d+)\s*か月前", 30),
            (r"(\d+)\s*年前", 365),
        ]
        for pattern, unit_days in patterns:
            match = re.search(pattern, text)
            if match:
                num = next(g for g in match.groups() if g is not None)
                return float(num) * unit_days

        if "年以上前" in text:
            return 365.0 * 2  # 十分に古いものとして扱う

        return None

    def __filter_by_last_login(self) -> None:
        """self.users を最終ログイン日数でフィルタリングする（列インデックス6が最終ログイン）"""
        if self.last_login_within_days is None:
            return

        filtered = []
        for row in self.users:
            last_login_text = row[6]
            days = self.__parse_last_login_to_days(last_login_text)
            # 解析できなかった行は誤って除外しないよう残す
            if days is None or days <= self.last_login_within_days:
                filtered.append(row)

        self.users = filtered

    # ------------------------------------------------------------------ #
    #  スプレッドシート書き込み
    # ------------------------------------------------------------------ #

    def __write_to_spreadsheet(self) -> None:
        """収集したユーザー情報をGoogleスプレッドシートに書き込む"""
        client = gs_client()
        workbook = client.open_by_key(self.gs_key)

        # シート存在チェック
        sheets = workbook.worksheets()
        sheet = None
        for s in sheets:
            if self.gs_sheet_name == s.title:
                sheet = s
                sheet.clear()
                break

        # 存在しなければ作成
        if sheet is None:
            sheet = workbook.add_worksheet(title=self.gs_sheet_name, rows=100, cols=9)

        header = [
            "ユーザー名",
            "ID",
            "URL",
            "評価",
            "販売実績",
            "フォロワー",
            "最終ログイン",
            "カテゴリ",
            "出品サービス数",
        ]

        sheet.append_row(header)
        workbook.values_append(
            self.gs_sheet_name,
            {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            {"values": self.users},
        )

        # 1行目固定・B列C列非表示
        sheet.freeze(rows=1)
        sheet.hide_columns(1, 3)
