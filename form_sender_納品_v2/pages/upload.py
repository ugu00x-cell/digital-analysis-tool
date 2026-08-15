"""リスト管理画面 - CSVアップロード・プレビュー・ステータス管理

大容量CSV対応（chunksize分割読み込み）、送信済みURL自動グレーアウト。
"""

import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from config import INPUT_DIR
from utils.db import init_db
from utils.db_logs import get_sent_urls

init_db()
logger = logging.getLogger(__name__)

# チャンクサイズ（大容量CSV対応）
CHUNK_SIZE = 1000

st.header("📋 企業リスト管理")

# --- CSVアップロード ---
uploaded = st.file_uploader(
    "企業リストCSVをアップロード",
    type=["csv"],
    help="必須カラム: 企業名, URL",
)

if uploaded is not None:
    try:
        # chunksize分割で大容量CSV対応
        chunks = pd.read_csv(uploaded, chunksize=CHUNK_SIZE)
        df = pd.concat(chunks, ignore_index=True)
    except Exception as e:
        st.error(f"CSV読み込みエラー: {e}")
        st.stop()

    # 必須カラムチェック
    missing = [c for c in ["企業名", "URL"] if c not in df.columns]
    if missing:
        for col in missing:
            st.error(f"❌ 必須カラム「{col}」がありません")
        st.stop()

    if df["URL"].isna().any():
        st.warning("⚠️ URLが空の行があります（スキップされます）")

    # ステータスカラム追加
    if "ステータス" not in df.columns:
        df["ステータス"] = "未送信"

    # 送信済みURLと照合してステータスを反映
    sent_urls = get_sent_urls()
    if sent_urls:
        mask = df["URL"].isin(sent_urls)
        # まだ「未送信」のままの行だけ上書き（手動変更を尊重）
        update_mask = mask & (df["ステータス"] == "未送信")
        df.loc[update_mask, "ステータス"] = "送信済み"

    st.session_state["company_list"] = df

    # ファイル保存
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = INPUT_DIR / uploaded.name
    save_path.write_bytes(uploaded.getvalue())
    logger.info("CSV保存: %s (%d件)", save_path, len(df))

    st.success(f"✅ {len(df)}件の企業を読み込みました")

# --- プレビュー ---
if "company_list" in st.session_state:
    df = st.session_state["company_list"]

    # 件数サマリー
    total_count = len(df)
    sent_count = len(df[df["ステータス"].isin(["送信済み", "送信成功"])])
    unsent_count = len(df[df["ステータス"] == "未送信"])
    other_count = total_count - sent_count - unsent_count

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("総件数", total_count)
    col2.metric("送信済み", sent_count)
    col3.metric("未送信", unsent_count)
    col4.metric("その他", other_count)

    st.divider()

    # ステータスフィルター
    status_filter = st.selectbox(
        "ステータスで絞り込み",
        ["すべて", "未送信", "送信済み", "送信成功", "送信失敗",
         "CAPTCHA", "フォームなし", "robots拒否"],
    )
    filtered = df if status_filter == "すべて" else df[
        df["ステータス"] == status_filter
    ]

    # 送信済み行をグレーアウト表示（スタイル適用）
    def _highlight_sent(row: pd.Series) -> list[str]:
        """送信済み行をグレー背景にする"""
        if row["ステータス"] in ("送信済み", "送信成功"):
            return ["background-color: #f0f0f0; color: #999"] * len(row)
        return [""] * len(row)

    styled = filtered.style.apply(_highlight_sent, axis=1)
    st.dataframe(styled, use_container_width=True)
    st.caption(f"表示: {len(filtered)} / 全{total_count}件")
else:
    st.info("CSVファイルをアップロードしてください")
