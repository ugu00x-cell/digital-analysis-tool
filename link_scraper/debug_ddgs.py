"""ddgsライブラリの動作確認"""
from ddgs import DDGS

with DDGS() as ddgs:
    results = list(ddgs.text("製造業 リンク集", max_results=10))

print(f"取得件数: {len(results)}")
for r in results:
    print(f"  {r['title']}")
    print(f"  {r['href']}")
    print()
