"""リスト管理画面 - CSVアップロード・企業一覧・ステータス管理"""

import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from config import INPUT_DIR

logger = logging.getLogger(__name__)


def _save_csv(uploaded_file) -> Path:
    """アップロードされたCSVを保存する

    Args:
        uploaded_file: StreamlitのUploadedFile

    Returns:
        保存先のパス
    """
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = INPUT_DIR / uploaded_file.name
    save_path.write_bytes(uploaded_file.getvalue())
    logger.info("CSV保存: %s", save_path)
    return save_path


def _validate_csv(df: pd.DataFrame) -> list[str]:
    """CSVの必須カラムをチェックする

    Args:
        df: 読み込んだDataFrame

    Returns:
        エラーメッセージのリスト（空なら問題なし）
    """
    errors: list[str] = []
    required = ["企業名", "URL"]

    for col in required:
        if col not in df.columns:
            errors.append(f"必須カラム「{col}」がありません")

    if errors:
        return errors

    if df["URL"].isna().any():
        errors.append("URLが空の行があります")

    return errors


def render() -> None:
    """リスト管理画面を描画する"""
    st.header("📋 企業リスト管理")

    # CSVアップロード
    uploaded = st.file_uploader(
        "企業リストCSVをアップロード",
        type=["csv"],
        help="必須カラム: 企業名, URL",
    )

    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"CSV読み込みエラー: {e}")
            return

        # バリデーション
        errors = _validate_csv(df)
        if errors:
            for err in errors:
                st.error(f"❌ {err}")
            return

        # ステータスカラム追加
        if "ステータス" not in df.columns:
            df["ステータス"] = "未送信"

        # セッションに保存
        st.session_state["company_list"] = df

        # 保存
        _save_csv(uploaded)
        st.success(f"✅ {len(df)}件の企業を読み込みました")

    # プレビュー表示
    if "company_list" in st.session_state:
        df = st.session_state["company_list"]

        # フィルター
        status_filter = st.selectbox(
            "ステータスで絞り込み",
            ["すべて", "未送信", "送信成功", "送信失敗", "CAPTCHA", "フォームなし"],
        )
        if status_filter != "すべて":
            filtered = df[df["ステータス"] == status_filter]
        else:
            filtered = df

        st.dataframe(filtered, use_container_width=True)
        st.caption(f"表示: {len(filtered)} / 全{len(df)}件")
    else:
        st.info("CSVファイルをアップロードしてください")
