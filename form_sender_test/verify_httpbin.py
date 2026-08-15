"""B: httpbin.org/forms/post への実送信検証

httpbinが提供するテストフォームに実送信し、サーバー側に届いた
内容を確認する。送信判定が「成功」のときに本当にPOSTされているか検証。
"""

import logging
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))

os.environ["GEMINI_API_KEY"] = "AIzaSyCNfeTZlzD8FbFeE2lXh04y8HSDfwPM5tE"

from utils.db import init_db
from utils.form_sender import send_to_company

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# httpbinのフォームページ
URL = "https://httpbin.org/forms/post"

SENDER = {
    "company": "株式会社Puravida",
    "last_name": "高野",
    "first_name": "",
    "name": "高野 検証",
    "last_kana": "タカノ",
    "first_kana": "",
    "kana": "タカノ ケンショウ",
    "email": "info@puravida.co.jp",
    "phone": "0312345678",
    "postal": "1000001",
    "address": "東京都千代田区千代田1-1",
    "subject": "送信検証テスト",
}

MESSAGE = """これは送信検証テストです。
httpbinのフォームに送信され、サーバー側で受信内容を確認します。

タイムスタンプ: {ts}
""".format(ts=time.strftime("%Y-%m-%d %H:%M:%S"))


def main() -> None:
    init_db()

    print("=" * 60)
    print("Phase B: httpbin.org への実送信検証")
    print("=" * 60)
    print(f"対象URL: {URL}")
    print(f"送信モード: dry_run=False（実送信）")
    print()

    # 実送信
    result = send_to_company(
        url=URL,
        company_name="httpbinテスト",
        message=MESSAGE,
        sender=SENDER,
        headless=True,
        dry_run=False,  # ★実送信
    )

    print()
    print("=" * 60)
    print("送信結果")
    print("=" * 60)
    print(f"ステータス: {result['status']}")
    print(f"詳細: {result.get('detail', '')}")
    print(f"AI使用: {result.get('ai_used', False)}")
    print(f"CAPTCHA解決: {result.get('captcha_solved', False)}")
    print()

    if result["status"] == "success":
        print("✅ ツール側で「送信成功」と判定されました")
        print("→ 次はhttpbinのレスポンスを直接確認します")
    else:
        print(f"❌ 送信失敗: {result['status']}")


if __name__ == "__main__":
    main()
