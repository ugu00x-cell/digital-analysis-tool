"""送信ボタンクリック後の画面遷移を詳しく調査

「成功」判定の根拠を確認する：
- 送信後のURL
- ページタイトル
- 主要なテキスト内容
- スクリーンショット保存
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ["GEMINI_API_KEY"] = "AIzaSyCNfeTZlzD8FbFeE2lXh04y8HSDfwPM5tE"
os.environ["TWO_CAPTCHA_API_KEY"] = "bcfb1b60177dc58978a44d93f2c75cf5"

from playwright.sync_api import sync_playwright

from utils.captcha_detector import detect_captcha_info
from utils.captcha_solver import solve_captcha


URL = "https://www.hillprint.co.jp/contact/"


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"[1] アクセス: {URL}")
        page.goto(URL, wait_until="networkidle", timeout=15000)

        url_before = page.url
        title_before = page.title()
        print(f"    URL前: {url_before}")
        print(f"    タイトル前: {title_before}")

        # CAPTCHA検出
        html = page.content()
        captcha_info = detect_captcha_info(html)
        print(f"\n[2] CAPTCHA: {captcha_info['type']} sitekey={(captcha_info.get('sitekey') or '')[:20]}...")

        # CAPTCHA解決
        if captcha_info["present"]:
            print("[3] CAPTCHA解決中...")
            solve_result = solve_captcha(page, page.url, captcha_info)
            print(f"    解決結果: solved={solve_result['solved']}, error={solve_result.get('error')}")

        # フォーム入力
        print("\n[4] フォーム入力")
        # 主要なフィールドを推測で入力
        try:
            page.fill('[name="your-name"]', "竹中 純也", timeout=3000)
            print("    your-name: OK")
        except Exception as e:
            print(f"    your-name: NG ({str(e)[:50]})")
        try:
            page.fill('[name="your-email"]', "ugu00x@gmail.com", timeout=3000)
            print("    your-email: OK")
        except Exception as e:
            print(f"    your-email: NG ({str(e)[:50]})")
        try:
            page.fill('[name="your-message"]', "テスト送信です。破棄をお願いします。", timeout=3000)
            print("    your-message: OK")
        except Exception as e:
            print(f"    your-message: NG ({str(e)[:50]})")

        # スクリーンショット（送信前）
        page.screenshot(path="before_submit.png", full_page=True)
        print("\n[5] スクリーンショット保存: before_submit.png")

        # 送信ボタンクリック
        print("\n[6] 送信ボタンクリック")
        submit = page.query_selector('input[type="submit"], button[type="submit"]')
        if submit:
            print(f"    ボタン発見: {submit.inner_text() or submit.get_attribute('value')}")
            submit.click()
        else:
            print("    [NG] 送信ボタンが見つからない")
            return

        # 送信後の状態を観察
        print("\n[7] 送信後の状態を観察（10秒間）")
        import time
        time.sleep(5)

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            print("    networkidle待機タイムアウト")

        url_after = page.url
        title_after = page.title()
        body_text = page.evaluate("document.body.innerText")[:1500]

        print(f"\n[8] 結果")
        print(f"    URL後: {url_after}")
        print(f"    タイトル後: {title_after}")
        print(f"    URL変化: {'YES' if url_after != url_before else 'NO ★ 同じURL'}")
        print()
        print("    ページ内容（先頭1500文字）:")
        print("    " + body_text.replace("\n", "\n    "))

        # 成功キーワード判定
        keywords_success = ["送信完了", "送信されました", "ありがとうございました",
                            "受け付けました", "thank you", "completed", "successful"]
        keywords_error = ["エラー", "失敗", "必須項目", "入力してください",
                          "error", "invalid", "required", "違反", "もう一度"]

        body_lower = body_text.lower()
        found_success = [k for k in keywords_success if k.lower() in body_lower]
        found_error = [k for k in keywords_error if k.lower() in body_lower]

        print(f"\n[9] キーワード判定")
        print(f"    成功キーワード: {found_success}")
        print(f"    エラーキーワード: {found_error}")

        # スクリーンショット（送信後）
        page.screenshot(path="after_submit.png", full_page=True)
        print(f"\n[10] スクリーンショット保存: after_submit.png")

        browser.close()


if __name__ == "__main__":
    main()
