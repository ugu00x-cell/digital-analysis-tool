"""B-2: httpbin送信後の最終ページ内容を確認

ツール「success」判定時、実際にサーバーが受信したかを
ブラウザの最終URL/ページ内容で検証。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        # フォームページにアクセス
        url = "https://httpbin.org/forms/post"
        print(f"アクセス: {url}")
        page.goto(url, wait_until="networkidle", timeout=15000)

        # フォーム入力
        page.fill('[name="custname"]', "高野 検証")
        page.fill('[name="custtel"]', "0312345678")
        page.fill('[name="custemail"]', "info@puravida.co.jp")
        page.fill('[name="comments"]', "送信検証テスト本文")
        page.check('[name="size"][value="medium"]')
        page.check('[name="topping"][value="bacon"]')

        print("送信ボタンをクリック...")
        page.click('button')

        # 遷移完了まで待機
        page.wait_for_load_state("networkidle", timeout=15000)

        final_url = page.url
        body_text = page.evaluate("document.body.innerText")

        print()
        print("=" * 60)
        print("【検証結果】")
        print("=" * 60)
        print(f"最終URL: {final_url}")
        print()
        print(f"ページ内容（先頭500文字）:")
        print(body_text[:500])
        print()

        # 判定
        if "/post" in final_url and ("custname" in body_text or "高野" in body_text):
            print("[OK] サーバー側でPOST受信を確認")
            print("[OK] 送信内容がエコーバックされている")
        elif final_url == url:
            print("[NG] URLが変わっていない（送信されていない可能性）")
        else:
            print(f"[?] 想定外の遷移: {final_url}")

        browser.close()


if __name__ == "__main__":
    main()
