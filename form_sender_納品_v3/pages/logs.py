"""ログ・レポート画面 - 送信履歴一覧・CSVダウンロード・Excel出力

ステータスフィルター、CSV/Excelダウンロード、AI統計サマリーに対応。
"""

import io
import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from config import LOGS_DIR
from utils.db import init_db
from utils.db_logs import get_logs, get_log_stats, cleanup_old_logs

init_db()
logger = logging.getLogger(__name__)

st.header("📄 送信ログ・レポート")

# --- AI統計サマリー ---
stats = get_log_stats()

st.subheader("📊 統計サマリー")
col1, col2, col3 = st.columns(3)
col1.metric("総送信数", stats["total"])
col2.metric("成功率", f"{stats['success_rate']:.1f}%")
col3.metric("今日の送信", stats["today_count"])

col4, col5, col6 = st.columns(3)
col4.metric("AI利用回数", stats["ai_used"])
col5.metric("AI利用成功", stats["ai_success"])
col6.metric("AI成功率", f"{stats['ai_rate']:.1f}%")

st.divider()

# --- ログ一覧 ---
st.subheader("📋 送信履歴")

# ステータスフィルター
status_options = ["すべて"]
if stats["by_status"]:
    status_options += sorted(stats["by_status"].keys())

selected = st.selectbox("ステータスで絞り込み", status_options)

# DB からログ取得
if selected == "すべて":
    results = get_logs()
else:
    results = get_logs(status_filter=selected)

if not results:
    st.info("まだ送信履歴がありません")
    st.stop()

df = pd.DataFrame(results)

# カラム名を日本語化して表示用に整形
display_cols = {
    "id": "ID",
    "url": "URL",
    "company_name": "企業名",
    "status": "ステータス",
    "error_reason": "エラー理由",
    "retry_count": "リトライ回数",
    "ai_used_flag": "AI利用",
    "sent_at": "送信日時",
}
df_disp = df.rename(columns=display_cols)

# AI利用フラグを分かりやすく
if "AI利用" in df_disp.columns:
    df_disp["AI利用"] = df_disp["AI利用"].map({1: "あり", 0: "なし"})

# 表示カラム
show_cols = ["企業名", "URL", "ステータス", "エラー理由",
             "リトライ回数", "AI利用", "送信日時"]
show_cols = [c for c in show_cols if c in df_disp.columns]

st.dataframe(df_disp[show_cols], use_container_width=True)
st.caption(f"表示: {len(df_disp)}件")

st.divider()

# --- ダウンロードセクション ---
st.subheader("📥 ダウンロード")

col_dl1, col_dl2 = st.columns(2)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# CSVダウンロード（UTF-8 BOM付き）
with col_dl1:
    csv_data = df_disp[show_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSVダウンロード",
        data=csv_data,
        file_name=f"send_logs_{timestamp}.csv",
        mime="text/csv",
    )

# Excelダウンロード
with col_dl2:
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_disp[show_cols].to_excel(
                writer, index=False, sheet_name="送信ログ"
            )
        excel_data = buffer.getvalue()

        st.download_button(
            "📥 Excelダウンロード",
            data=excel_data,
            file_name=f"send_logs_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ImportError:
        st.info("Excel出力にはopenpyxlが必要です: pip install openpyxl")

st.divider()

# --- メンテナンス ---
st.subheader("🧹 メンテナンス")
if st.button("古いログを削除（1年超過＋10万件超過）", key="cleanup_logs"):
    deleted = cleanup_old_logs()
    if deleted > 0:
        st.success(f"✅ {deleted}件の古いログを削除しました")
    else:
        st.info("削除対象のログはありません")

# ログフォルダにも自動保存
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOGS_DIR / f"send_logs_{timestamp}.csv"
if not log_path.exists() and len(df_disp) > 0:
    df_disp[show_cols].to_csv(log_path, index=False, encoding="utf-8-sig")
    logger.info("ログCSV自動保存: %s", log_path)
