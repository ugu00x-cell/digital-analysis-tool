"""メッセージ設定画面 - テンプレート編集・送信者情報設定"""

import streamlit as st

from config import DEFAULT_SENDER

# デフォルトのメッセージテンプレート
DEFAULT_SUBJECT = "サービスのご提案"
DEFAULT_BODY = """{{company_name}} ご担当者様

突然のご連絡失礼いたします。
株式会社サンプルの山田と申します。

貴社のWebサイトを拝見し、弊社のサービスが
お役に立てるのではないかと思いご連絡いたしました。

ご興味をお持ちいただけましたら、
お気軽にご返信いただけますと幸いです。

何卒よろしくお願いいたします。

━━━━━━━━━━━━━━━━
株式会社サンプル
山田 太郎
Email: taro@example.com
TEL: 03-1234-5678
━━━━━━━━━━━━━━━━"""


def render() -> None:
    """メッセージ設定画面を描画する"""
    st.header("✉️ メッセージ設定")

    # 送信者情報
    st.subheader("送信者情報")
    col1, col2 = st.columns(2)

    sender = st.session_state.get("sender", DEFAULT_SENDER.copy())

    with col1:
        sender["company"] = st.text_input(
            "会社名", value=sender.get("company", "")
        )
        sender["name"] = st.text_input(
            "氏名", value=sender.get("name", "")
        )
    with col2:
        sender["email"] = st.text_input(
            "メールアドレス", value=sender.get("email", "")
        )
        sender["phone"] = st.text_input(
            "電話番号", value=sender.get("phone", "")
        )

    st.session_state["sender"] = sender

    st.divider()

    # メッセージテンプレート
    st.subheader("メッセージテンプレート")
    st.caption("{{company_name}} は企業名に自動置換されます")

    subject = st.text_input(
        "件名",
        value=st.session_state.get("subject", DEFAULT_SUBJECT),
    )
    st.session_state["subject"] = subject

    body = st.text_area(
        "本文",
        value=st.session_state.get("message_body", DEFAULT_BODY),
        height=350,
    )
    st.session_state["message_body"] = body

    # プレビュー
    with st.expander("📧 プレビュー（企業名 = テスト株式会社）"):
        preview = body.replace("{{company_name}}", "テスト株式会社")
        st.text(f"件名: {subject}")
        st.text(preview)
