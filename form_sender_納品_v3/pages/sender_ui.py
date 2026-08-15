"""送信実行画面 - 送信開始・停止・進捗リアルタイム表示"""

import logging
import time

import streamlit as st

from config import DAILY_LIMIT
from engine.learner import get_stats
from engine.sender import random_wait, send_to_company

logger = logging.getLogger(__name__)


def _get_message(company_name: str) -> str:
    """企業名を埋め込んだメッセージを生成する

    Args:
        company_name: 企業名

    Returns:
        テンプレート変数を置換済みのメッセージ
    """
    body = st.session_state.get("message_body", "")
    return body.replace("{{company_name}}", company_name)


def render() -> None:
    """送信実行画面を描画する"""
    st.header("🚀 送信実行")

    # 企業リストの確認
    if "company_list" not in st.session_state:
        st.warning("先に「リスト管理」タブでCSVをアップロードしてください")
        return

    df = st.session_state["company_list"]
    unsent = df[df["ステータス"] == "未送信"]

    if len(unsent) == 0:
        st.info("未送信の企業はありません")
        return

    # 送信設定
    col1, col2 = st.columns(2)
    with col1:
        daily_limit = st.number_input(
            "1日の送信上限", min_value=1, value=DAILY_LIMIT
        )
    with col2:
        headless = st.checkbox("ヘッドレスモード（ブラウザ非表示）")

    # 今日の送信数チェック
    stats = get_stats()
    remaining = max(0, daily_limit - stats["today_count"])
    st.info(
        f"未送信: **{len(unsent)}**件 / "
        f"今日の残り枠: **{remaining}**件"
    )

    # 送信対象数
    target_count = min(len(unsent), remaining)

    # 送信開始ボタン
    if st.button(
        f"📨 {target_count}件に送信開始",
        type="primary",
        disabled=target_count == 0,
    ):
        _execute_sending(df, unsent, target_count, headless)


def _execute_sending(
    df, unsent, target_count: int, headless: bool
) -> None:
    """送信処理を実行する

    Args:
        df: 全企業のDataFrame
        unsent: 未送信企業のDataFrame
        target_count: 送信対象数
        headless: ヘッドレスモード
    """
    sender = st.session_state.get("sender", {})
    progress = st.progress(0, text="送信準備中...")
    status_area = st.empty()
    results_area = st.container()

    targets = unsent.head(target_count)

    for i, (idx, row) in enumerate(targets.iterrows()):
        company = row["企業名"]
        url = row["URL"]
        message = _get_message(company)

        progress.progress(
            (i + 1) / target_count,
            text=f"送信中: {company}（{i+1}/{target_count}）",
        )
        status_area.info(f"🔄 {company} に送信中...")

        # 送信実行
        result = send_to_company(
            url, company, message, sender, headless
        )

        # ステータス更新
        status_label = {
            "success": "送信成功",
            "captcha": "CAPTCHA",
            "no_form": "フォームなし",
            "error": "送信失敗",
        }.get(result["status"], "送信失敗")

        df.loc[idx, "ステータス"] = status_label
        st.session_state["company_list"] = df

        # 結果表示
        with results_area:
            icon = "✅" if result["status"] == "success" else "❌"
            st.write(f"{icon} {company}: {result['detail']}")

        # ウェイト（最後の1件以外）
        if i < target_count - 1:
            wait = random_wait()
            status_area.info(f"⏳ {wait:.0f}秒待機中...")
            time.sleep(wait)

    progress.progress(1.0, text="送信完了！")
    status_area.success(f"✅ {target_count}件の送信処理が完了しました")
