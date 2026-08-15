"""Bingの応答を確認するデバッグスクリプト"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

# ブラウザに近いヘッダーを追加
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)

query = quote("製造業 リンク集")
url = f"https://www.bing.com/search?q={query}&count=10&setlang=ja-JP"

print(f"URL: {url}")
res = session.get(url, timeout=10)
print(f"Status: {res.status_code}")

soup = BeautifulSoup(res.text, "html.parser")

# セレクタ別ヒット数確認
selectors = [
    "li.b_algo h2 a",
    "li.b_algo a",
    "h2 a",
    ".b_title a",
    "cite",        # Bingの表示URLタグ
    "a[href]",
]
for sel in selectors:
    found = soup.select(sel)
    print(f"  {sel}: {len(found)}件")
    # ヒットしたものは最初の3件だけ表示
    for tag in found[:3]:
        href = tag.get("href", tag.get_text())
        print(f"    → {href[:80]}")

# ページタイトル確認
title = soup.title.string if soup.title else "タイトルなし"
print(f"\nページタイトル: {title}")
