"""ログ・レポート画面 - 送信履歴・CSVダウンロード"""

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from config import LOGS_DIR
from engine.learner import get_all_results

logger = logging.getLogger(__name__)


def render() -> None:
    """ログ・レポート画面を描画する"""
    st.header("📄 送信ログ・レポート")

    results = get_all_results()

    if not results:
        st.info("まだ送信履歴がありません")
        return

    df = pd.DataFrame(results)

    # 表示用にカラム名を日本語化
    df_display = df.rename(columns={
        "company_name": "企業名",
        "url": "URL",
        "status": "ステータス",
        "error_detail": "詳細",
        "sent_at": "送信日時",
    })

    # ステータスフィルター
    statuses = ["すべて"] + df_display["ステータス"].unique().tolist()
    selected = st.selectbox("ステータスで絞り込み", statuses)

    if selected != "すべて":
        df_display = df_display[df_display["ステータス"] == selected]

    st.dataframe(
        df_display[["企業名", "URL", "ステータス", "詳細", "送信日時"]],
        use_container_width=True,
    )
    st.caption(f"表示: {len(df_display)}件")

    st.divider()

    # CSVダウンロード
    csv_data = df_display.to_csv(index=False).encode("utf-8-sig")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        "📥 結果CSVをダウンロード",
        data=csv_data,
        file_name=f"send_results_{timestamp}.csv",
        mime="text/csv",
    )

    # ログフォルダにも保存
    _save_log_csv(df_display, timestamp)


def _save_log_csv(df: pd.DataFrame, timestamp: str) -> None:
    """ログCSVをファイルに保存する

    Args:
        df: 結果DataFrame
        timestamp: タイムスタンプ文字列
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    path = LOGS_DIR / f"send_results_{timestamp}.csv"

    # 同名ファイルが既にある場合はスキップ
    if not path.exists():
        df.to_csv(path, index=False, encoding="utf-8-sig")
        logger.info("ログCSV保存: %s", path)
