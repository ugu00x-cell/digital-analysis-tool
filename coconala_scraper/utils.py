"""ココナラスクレイピングツール共通ユーティリティ"""

import datetime
import random
import time

import gspread
from google.oauth2.service_account import Credentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait


def gs_client():
    """Googleスプレッドシートクライアントを認証して返す"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
    ]

    credentials = Credentials.from_service_account_file("./credentials.json", scopes=scopes)

    return gspread.authorize(credentials)


def print_log(message: str) -> None:
    """タイムスタンプ付きでログを出力する"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now}\t{message}")


def random_sleep() -> None:
    """1〜2秒のランダムな待機（ブロック対策）"""
    time.sleep(random.uniform(1, 2))


def chrome_driver(profile=False):
    """ヘッドレスChromeドライバーを生成して返す"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")

    if profile:
        options.add_argument("user-data-dir=" + profile)

    driver = webdriver.Chrome(options=options)

    wait = WebDriverWait(driver, 60)

    return driver, wait
