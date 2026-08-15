"""総戸数未取得レコードのうち、まだ一度もチェックしていないURLが残っていないか最終確認"""

from urllib.parse import urlparse
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# 今夜チェック済みのURL(ドメイン単位)
checked_domains = {
    'geo.8984.jp', 'growing.hosoda.co.jp', 'house.goo.ne.jp', 'realestate.its-mo.com',
    'suumo.jp', 'www.athome.co.jp', 'www.bc-nishiurawa.jp', 'www.branchera-garden.com',
    'www.daiei-re.jp', 'www.haseko.co.jp', 'www.homes.co.jp', 'www.hosoda.co.jp',
    'www.livable.co.jp', 'www.morioka.clare.jp', 'www.navitime.co.jp', 'www.sgr-sumai.jp',
    'www.succeed-inc.co.jp', 'www.towa-house.co.jp', 'db.self-in.com',
    'www.mansion-review.jp',  # 竹中さんが手動で11件確認済み
}

query = """
SELECT purojiekutokoodo, purojiekutoedaban, bukkenmei, source_url
FROM `dj-ga4.scd.research_results`
WHERE (soukosuujuukyo IS NULL OR soukosuujuukyo = '')
    AND source_url IS NOT NULL AND source_url != ''
"""
results = bq.fetch_results(query)

unchecked = []
for row in results:
    domain = urlparse(row.source_url).netloc
    if domain not in checked_domains:
        unchecked.append((row.purojiekutokoodo, row.bukkenmei, row.source_url, domain))

print(f"総戸数未取得レコード総数: {len(results)}件")
print(f"未チェックのドメインを持つレコード: {len(unchecked)}件\n")

if unchecked:
    for code, name, url, domain in unchecked:
        print(f"{code}: {name} | {domain} | {url}")
else:
    print("✅ すべてのレコードのドメインを今夜中にチェック済みです。")

# source_urlが空のレコード数も確認(これらはそもそもチェック対象外)
no_url_query = """
SELECT COUNT(*) as cnt
FROM `dj-ga4.scd.research_results`
WHERE (soukosuujuukyo IS NULL OR soukosuujuukyo = '')
    AND (source_url IS NULL OR source_url = '')
"""
no_url = bq.fetch_results(no_url_query)[0]
print(f"\nsource_urlが元々ないレコード(チェック対象外): {no_url.cnt}件")
