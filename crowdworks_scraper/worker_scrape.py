"""CrowdWorksワーカー情報スクレイピングモジュール"""

import re
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Set

import requests
from bs4 import BeautifulSoup as BS
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .utils import gs_client, print_log, random_sleep, chrome_driver


class WorkerScrape:
    """CrowdWorksのワーカー情報を収集し、スプレッドシートに書き込むクラス"""

    # 設定
    CROWD_WORKS_HOST = "https://crowdworks.jp"
    INTERVAL_TIME = 1.5

    def __init__(self, worker_url: str, gs_key: str, gs_sheet_name: str, limit: int = 0) -> None:
        self.worker_url = worker_url
        self.gs_key = gs_key
        self.gs_sheet_name = gs_sheet_name
        self.limit = limit
        self.lock = threading.Lock()
        self.worker_paths: List[str] = []
        self.workers: List[list] = []

    def exec(self) -> None:
        """メイン実行: ワーカー一覧取得 → 詳細取得 → スプレッドシート書き込み"""
        print_log("ワーカー一覧の読み込みを開始します。")
        self.__fetch_worker_paths()
        print_log("ワーカー一覧の読み込みを終了します。")
        self.__fetch_worker_details()
        print_log("スプレッドシートの書き込みを開始します。")
        self.__write_to_spreadsheet()
        print_log("スプレッドシートの書き込みを終了します。")

    def __fetch_worker_paths(self) -> None:
        """ワーカー一覧ページからプロフィールURLを取得する（Selenium使用）"""
        seen: Set[str] = set()
        limit_reached = False
        current_url = self.worker_url
        page_num = 1

        while True:
            driver, wait = chrome_driver()
            try:
                driver.get(current_url)

                # JS描画完了を待つ
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[href*='/public/employees/']")
                        )
                    )
                except TimeoutException:
                    print_log(f"ページ{page_num}: ワーカーリンクが見つかりませんでした。終了します。")
                    break

                soup = BS(driver.page_source, "html.parser")
            finally:
                driver.quit()

            # ワーカーリンクを抽出（/public/employees/数字 のみ）
            all_links = soup.select("a[href*='/public/employees/']")
            page_count = 0

            for link in all_links:
                href = link.get("href", "")

                # 絶対URLと相対URLの両方に対応
                if href.startswith(self.CROWD_WORKS_HOST):
                    path = href[len(self.CROWD_WORKS_HOST):]
                else:
                    path = href

                # クエリパラメータを除去して正規化
                path_only = path.split("?")[0]

                # /public/employees/数字 の形式のみ対象
                parts = path_only.split("/")
                if (len(parts) == 4
                        and parts[1] == "public"
                        and parts[2] == "employees"
                        and parts[3].isdigit()):
                    if path_only not in seen:
                        seen.add(path_only)
                        self.worker_paths.append(path_only)
                        page_count += 1
                        if self.limit != 0 and len(self.worker_paths) >= self.limit:
                            limit_reached = True
                            break

            print_log(f"ページ{page_num}: {page_count}件取得（累計: {len(self.worker_paths)}件）")

            if limit_reached:
                break

            # 次ページリンクを取得
            next_url = self.__get_next_page_url(soup)
            if next_url is None:
                print_log(f"ページ{page_num}で次ページリンクが見つかりませんでした。")
                break

            current_url = next_url
            time.sleep(self.INTERVAL_TIME)
            page_num += 1

        print_log(f"ワーカーURL取得完了: {len(self.worker_paths)}件")

    def __get_next_page_url(self, soup: BS) -> Optional[str]:
        """次ページのURLを返す。絶対URL・相対URL両方に対応"""
        page_links = soup.select("a[href*='page=']")

        for link in page_links:
            link_text = link.get_text(strip=True)
            if "次へ" in link_text or "次" in link_text or "→" in link_text:
                href = link.get("href", "")
                if not href:
                    return None
                if href.startswith("http"):
                    return href
                else:
                    return self.CROWD_WORKS_HOST + href

        return None

    def __fetch_worker_details(self) -> None:
        """マルチスレッドでワーカー詳細情報を取得する"""
        worker_count = len(self.worker_paths)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for i, worker_path in enumerate(self.worker_paths, start=1):
                future = executor.submit(self.__fetch_single_worker, i, worker_count, worker_path)
                futures.append(future)

            # 全タスクの完了を待ち、例外があればログ出力
            for future in as_completed(futures):
                exc = future.exception()
                if exc is not None:
                    print_log(f"ワーカー取得中に予期しないエラー: {exc}")

    def __fetch_single_worker(self, index: int, total: int, worker_path: str) -> None:
        """個別ワーカーの詳細情報を取得する"""
        worker_url = self.CROWD_WORKS_HOST + worker_path

        if index == 1 or index % 10 == 0 or index == total:
            print_log(f"ワーカー詳細読み込み中。{index}/{total}")

        driver, wait = chrome_driver()
        try:
            driver.get(worker_url)

            # IDが表示されるまで待機
            wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "user-display-name")))
            user_id = driver.find_element(By.CLASS_NAME, "user-display-name").text

            # ユーザータイプ / 性別 / 年代（都道府県）
            attributes_text = driver.find_element(By.CLASS_NAME, "attributes").text

            # 最終アクセス
            last_activity = driver.find_element(By.CLASS_NAME, "last_activity").text.replace("最終アクセス: ", "")

            # 評価（要素が存在しない場合は空文字）
            try:
                wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "employer-evaluation-wrapper")))
                evaluation = driver.find_element(
                    By.CSS_SELECTOR, ".employer-evaluation-wrapper > dl > dd > span"
                ).text
            except TimeoutException:
                evaluation_elems = driver.find_elements(By.CSS_SELECTOR, "[class*='evaluation'] span")
                evaluation = evaluation_elems[0].text if evaluation_elems else ""

            # 時間単価（要素が存在しない場合は空文字）
            try:
                employee_hourly_wage = driver.find_element(
                    By.XPATH, "//div[@class='employee-summaries']/div/dl[2]/dd"
                ).text
            except Exception:
                employee_hourly_wage = ""

            # 稼働可能時間/週（要素が存在しない場合は空文字）
            try:
                employee_hours_limit = driver.find_element(
                    By.XPATH, "//div[@class='employee-summaries']/div/dl[3]/dd"
                ).text
            except Exception:
                employee_hours_limit = ""

            # 本人認証・NDA・受注実績（要素が存在しない場合は空文字）
            try:
                achievements_data = driver.find_element(
                    By.ID, "pc-employee-achievements-container"
                ).get_attribute('data')
                achievements = json.loads(achievements_data)['employee']
                verified = "本人確認済み" if achievements['isIdentiryVerified'] else "本人未確認"
                concluded = "NDA締結済み" if achievements['nonDisclosureAgreementConcluded'] else "NDA未締結"
                achievement_count = achievements['projectFinishedRate']['totalFinishedCount']
            except Exception:
                verified = ""
                concluded = ""
                achievement_count = ""

            # 属性分解
            attrs = self.__split_attributes(attributes_text)

            # スレッドセーフにリストへ追加
            with self.lock:
                self.workers.append(
                    [
                        f'=HYPERLINK("{worker_url}","{user_id}")',
                        user_id,
                        worker_url,
                        attrs["sex"],
                        attrs["age_range"],
                        attrs["prefecture"],
                        last_activity,
                        achievement_count,
                        evaluation,
                        employee_hourly_wage,
                        employee_hours_limit,
                        verified,
                        concluded,
                    ]
                )

            random_sleep()

        except TimeoutException:
            print_log(f"{worker_url} がタイムアウトしました。スキップします。")
        except Exception as e:
            print_log(f"{worker_url} 異常が発生しました。スキップします。")
            print_log(str(e))
        finally:
            driver.quit()

    def __split_attributes(self, attributes_str: str) -> dict[str, str]:
        """属性文字列を分解する（例: '個人 / 女性 / 30代(東京都)'）"""
        attributes = [x.strip() for x in attributes_str.split("/")]
        prefecture = re.findall(r"\((.*?)\)", attributes[2])[0].strip()
        age_range = attributes[2].split("(")[0].strip()

        return {
            "user_type": attributes[0],
            "sex": attributes[1],
            "age_range": age_range,
            "prefecture": prefecture,
        }

    def __write_to_spreadsheet(self) -> None:
        """収集したワーカー情報をGoogleスプレッドシートに書き込む"""
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
            sheet = workbook.add_worksheet(title=self.gs_sheet_name, rows=100, cols=13)

        header = [
            "CW名", "ID", "URL", "性別", "年齢", "地域",
            "最終アクセス", "受注実績", "評価", "時間単価",
            "稼働可能時間/週", "本人確認", "NDA締結",
        ]

        sheet.append_row(header)
        workbook.values_append(
            self.gs_sheet_name,
            {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            {"values": self.workers},
        )

        # 1行目固定
        sheet.freeze(rows=1)

        # B列,C列を非表示
        sheet.hide_columns(1, 3)
