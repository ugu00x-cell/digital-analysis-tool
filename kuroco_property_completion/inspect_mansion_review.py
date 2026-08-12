"""mansion-review.jp のページ構造を確認"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# テスト用URL
url = "https://www.mansion-review.jp/mansion/1433690.html"

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

try:
    print("ページを開いています...")
    driver.get(url)
    time.sleep(3)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # "総戸数" を含むすべての要素を検索
    print("\n=== 総戸数を含む全要素 ===")
    for elem in soup.find_all(string=lambda text: text and "総戸数" in text):
        parent = elem.parent
        print(f"\n親要素: {parent.name}")
        print(f"クラス: {parent.get('class')}")
        print(f"テキスト: {parent.text.strip()[:200]}")

        # 次の兄弟要素を確認
        if parent.next_sibling:
            print(f"次の兄弟: {parent.next_sibling.text.strip()[:100] if hasattr(parent.next_sibling, 'text') else parent.next_sibling}")

    # dt/dd パターンも確認
    print("\n=== dt/dd 要素の構造 ===")
    for dt in soup.find_all("dt"):
        print(f"dt: {dt.text.strip()}")
        if dt.next_sibling:
            dd = dt.next_sibling
            while dd and hasattr(dd, 'name') and dd.name != 'dd':
                dd = dd.next_sibling
            if dd and hasattr(dd, 'name') and dd.name == 'dd':
                print(f"  → dd: {dd.text.strip()}")

    # table パターンも確認
    print("\n=== table 要素の構造 ===")
    for table in soup.find_all("table"):
        for tr in table.find_all("tr")[:10]:
            cells = tr.find_all(["th", "td"])
            print(f"{' | '.join([c.text.strip()[:15] for c in cells])}")

finally:
    driver.quit()
