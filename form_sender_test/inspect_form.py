"""ヒル・プリント様のフォーム構造を詳しく調査"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.hillprint.co.jp/contact/", wait_until="networkidle", timeout=15000)

        # フォーム内の全input/textareaのname属性を取得
        fields = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('form input, form textarea, form select').forEach(el => {
                result.push({
                    tag: el.tagName,
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    required: el.required,
                    visible: el.offsetParent !== null,
                });
            });
            return result;
        }""")

        print("フォーム要素一覧:")
        for f in fields:
            tag = f["tag"]
            type_ = f["type"]
            name = f["name"]
            placeholder = f["placeholder"][:30]
            required = "required" if f["required"] else ""
            visible = "VISIBLE" if f["visible"] else "hidden"
            print(f"  {tag:8s} type={type_:10s} name='{name}' placeholder='{placeholder}' {required} {visible}")

        # 送信ボタン
        buttons = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('form input[type="submit"], form button, form input[type="image"]').forEach(el => {
                result.push({
                    tag: el.tagName,
                    type: el.type || '',
                    text: (el.innerText || el.value || '').substring(0, 50),
                });
            });
            return result;
        }""")

        print("\n送信ボタン:")
        for b in buttons:
            print(f"  {b['tag']} type={b['type']} text='{b['text']}'")

        browser.close()


if __name__ == "__main__":
    main()
