"""実際のテーブル構造を直接確認（総戸数の全出現箇所）"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

url = "https://www.mansion-review.jp/mansion/1433690.html"  # つくばグランヴィラ（期待値203戸）

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

try:
    driver.get(url)
    time.sleep(3)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    print("=== 「総戸数」を含む全ての行(tr)を確認 ===\n")
    for i, row in enumerate(soup.find_all("tr")):
        if "総戸数" in row.text:
            cells = row.find_all(["th", "td"])
            cell_texts = [c.text.strip()[:30] for c in cells]
            print(f"行{i}: {cell_texts}")

finally:
    driver.quit()
