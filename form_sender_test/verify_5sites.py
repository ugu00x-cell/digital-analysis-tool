"""5社実機ドライラン - 修正版の動作検証

Streamlit経由ではなく send_to_company を直接呼び出して
Bug5（NotImplementedError解消）含む全機能を確認する。
"""

import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

os.environ["GEMINI_API_KEY"] = "AIzaSyCNfeTZlzD8FbFeE2lXh04y8HSDfwPM5tE"
os.environ["TWO_CAPTCHA_API_KEY"] = "bcfb1b60177dc58978a44d93f2c75cf5"

from utils.db import init_db
from utils.db_logs import save_setting
from utils.form_sender import send_to_company

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("verify.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# CAPTCHA設置サイト2社 + 通常サイト3社で検証
TARGETS = [
    ("ヒル・プリント株式会社", "https://www.hillprint.co.jp/contact/"),
    ("株式会社西村製作所", "https://www.nishimura-opt.co.jp/contact/"),
    ("株式会社遠藤製作所", "https://www.endo-mfg.co.jp/contact/"),
    ("MAE株式会社", "https://www.maeam.com/contact"),
    ("株式会社マルタケ", "https://www.marutake8880.co.jp/company.html"),
]

TEMPLATE = """検証用テンプレート（送信ボタンは押しません）"""

SENDER = {
    "company": "株式会社Puravida",
    "last_name": "高野",
    "first_name": "",
    "name": "高野",
    "last_kana": "タカノ",
    "first_kana": "",
    "kana": "タカノ",
    "email": "info@puravida.co.jp",
    "phone": "0312345678",
    "postal": "1000001",
    "address": "東京都千代田区千代田1-1",
    "subject": "ご案内",
}


def main() -> None:
    init_db()
    save_setting("two_captcha_api_key", os.environ["TWO_CAPTCHA_API_KEY"])

    import streamlit as st
    st.session_state["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    st.session_state["two_captcha_api_key"] = os.environ["TWO_CAPTCHA_API_KEY"]

    logger.info("=== 修正版動作検証: 5社ドライラン ===")
    results = []

    for i, (company, url) in enumerate(TARGETS):
        logger.info("[%d/5] %s", i + 1, company)
        try:
            result = send_to_company(
                url=url, company_name=company, message=TEMPLATE,
                sender=SENDER, headless=True, dry_run=True,
            )
            results.append({
                "企業名": company,
                "URL": url,
                "ステータス": result["status"],
                "詳細": result.get("detail", "")[:60],
                "AI": result.get("ai_used", False),
                "CAPTCHA解決": result.get("captcha_solved", False),
            })
            logger.info(
                "  → %s (CAPTCHA=%s, AI=%s)",
                result["status"],
                result.get("captcha_solved"),
                result.get("ai_used"),
            )
        except Exception as e:
            logger.error("  ❌ 例外: %s", e)
            results.append({
                "企業名": company, "URL": url,
                "ステータス": "exception",
                "詳細": str(e)[:60], "AI": False, "CAPTCHA解決": False,
            })

        if i < 4:
            time.sleep(3)

    # サマリー
    print("\n" + "=" * 70)
    print("検証結果")
    print("=" * 70)
    for r in results:
        icon = "[OK]" if r["ステータス"] == "dry_run" else "[NG]"
        captcha = " (CAPTCHA解決済)" if r["CAPTCHA解決"] else ""
        print(f"{icon} {r['企業名'][:25]:25s} | {r['ステータス']:12s}{captcha}")
    print("=" * 70)

    success = sum(1 for r in results if r["ステータス"] == "dry_run")
    captcha_solved = sum(1 for r in results if r["CAPTCHA解決"])
    print(f"\n  ドライラン成功: {success}/5")
    print(f"  CAPTCHA解決:   {captcha_solved}/5")

    pd.DataFrame(results).to_csv(
        "verify_results.csv", index=False, encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()
