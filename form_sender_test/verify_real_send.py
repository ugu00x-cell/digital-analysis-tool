"""A: 実送信検証 - 過去ドライラン成功企業1社に実送信

倫理配慮：
- テンプレートに「テスト送信・破棄依頼」を明記
- 差出人は本人（竹中）の名前・メアド
- 1社のみ送信
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ["GEMINI_API_KEY"] = "AIzaSyCNfeTZlzD8FbFeE2lXh04y8HSDfwPM5tE"
os.environ["TWO_CAPTCHA_API_KEY"] = "bcfb1b60177dc58978a44d93f2c75cf5"

from utils.db import init_db
from utils.db_logs import save_setting
from utils.form_sender import send_to_company

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 送信先（CAPTCHA無し・シンプル構造で純粋な送信動作を検証）
TARGET_URL = "https://www.marutake8880.co.jp/company.html"
TARGET_NAME = "株式会社マルタケ"

# 差出人（竹中本人）
SENDER = {
    "company": "個人",
    "last_name": "竹中",
    "first_name": "純也",
    "name": "竹中 純也",
    "last_kana": "タケナカ",
    "first_kana": "ジュンヤ",
    "kana": "タケナカ ジュンヤ",
    "email": "ugu00x@gmail.com",
    "phone": "0312345678",
    "postal": "2430000",
    "address": "神奈川県海老名市",
    "subject": "【動作検証テスト】お手数ですが破棄をお願いします",
}

# テンプレート（明確にテスト送信と表記）
TEMPLATE = """※本メッセージは自動送信ツールの動作検証目的で送信しております。
※実際のお問い合わせ内容ではございませんので、お手数ですが破棄をお願いいたします。
※ご迷惑をおかけし大変申し訳ございません。

―――――――――――――――――――――
ツール開発者：竹中 純也
連絡先: ugu00x@gmail.com
日時: 動作検証テスト
―――――――――――――――――――――

このメッセージへの返信・対応は不要です。
本テストは、自動送信が実際にサーバー側で受信されているかを
確認する目的のみで実施しております。
"""


def main() -> None:
    init_db()
    save_setting("two_captcha_api_key", os.environ["TWO_CAPTCHA_API_KEY"])

    import streamlit as st
    st.session_state["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    st.session_state["two_captcha_api_key"] = os.environ["TWO_CAPTCHA_API_KEY"]

    print("=" * 70)
    print("A: 実送信検証（1社のみ）")
    print("=" * 70)
    print(f"送信先: {TARGET_NAME}")
    print(f"URL: {TARGET_URL}")
    print(f"差出人メアド: {SENDER['email']}")
    print(f"モード: dry_run=False (★実送信)")
    print("=" * 70)
    print()

    result = send_to_company(
        url=TARGET_URL,
        company_name=TARGET_NAME,
        message=TEMPLATE,
        sender=SENDER,
        headless=True,
        dry_run=False,
    )

    print()
    print("=" * 70)
    print("送信結果")
    print("=" * 70)
    print(f"ステータス: {result['status']}")
    print(f"詳細: {result.get('detail', '')}")
    print(f"AI使用: {result.get('ai_used', False)}")
    print(f"CAPTCHA解決: {result.get('captcha_solved', False)}")
    print(f"リトライ回数: {result.get('retry_count', 0)}")
    print()

    if result["status"] == "success":
        print("[OK] ツール側で「送信成功」と判定")
        print()
        print("【次のステップ】")
        print(f"  ugu00x@gmail.com の受信トレイを1〜5分後に確認してください")
        print("  ・サンキューメール（自動返信）が届けば → 完全成功")
        print("  ・届かない場合 → サイト側が自動応答を設定していない")
    else:
        print(f"[NG] 送信失敗: {result['status']}")


if __name__ == "__main__":
    main()
