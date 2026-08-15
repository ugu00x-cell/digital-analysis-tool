"""営業フォーム自動送信ツール - Streamlit UIエントリポイント"""

import logging
import os
import sys

import streamlit as st
from dotenv import load_dotenv

# パス解決の基準ディレクトリ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(BASE_DIR, "app.log"), encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)

from utils.db import init_db


def load_page(filename: str) -> None:
    """pagesフォルダのスクリプトを実行する

    Args:
        filename: pages/配下のファイル名
    """
    path = os.path.join(BASE_DIR, "pages", filename)
    with open(path, encoding="utf-8") as f:
        exec(f.read(), globals())


def main() -> None:
    """アプリケーションのメイン処理"""
    st.set_page_config(
        page_title="営業フォーム自動送信",
        page_icon="📨",
        layout="wide",
    )

    # DB初期化
    init_db()

    # サイドバーナビゲーション
    st.sidebar.title("📨 フォーム自動送信")
    page = st.sidebar.radio(
        "メニュー",
        ["📊 ダッシュボード", "📋 リスト管理", "⚙️ 設定", "📄 ログ"],
    )

    # ページルーティング
    page_map = {
        "📊 ダッシュボード": "dashboard.py",
        "📋 リスト管理": "upload.py",
        "⚙️ 設定": "settings.py",
        "📄 ログ": "logs.py",
    }
    load_page(page_map[page])


if __name__ == "__main__":
    main()
