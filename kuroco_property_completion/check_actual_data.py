"""research_results に実際に入っている駅名を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# ユニークな駅名数を確認
result = bq.fetch_results('SELECT COUNT(DISTINCT ekimei) as cnt FROM `dj-ga4.scd.research_results` WHERE ekimei IS NOT NULL AND ekimei != ""')
if result:
    print(f"ユニークな駅名数: {result[0].cnt}")

# 具体的な駅名一覧を表示
results = bq.fetch_results('SELECT DISTINCT ekimei FROM `dj-ga4.scd.research_results` WHERE ekimei IS NOT NULL AND ekimei != "" LIMIT 10')
print("\n駅名一覧:")
for row in results:
    print(f"  - {row.ekimei}")

# 沿線も確認
result2 = bq.fetch_results('SELECT COUNT(DISTINCT ensenmei) as cnt FROM `dj-ga4.scd.research_results` WHERE ensenmei IS NOT NULL AND ensenmei != ""')
if result2:
    print(f"\nユニークな沿線数: {result2[0].cnt}")

results2 = bq.fetch_results('SELECT DISTINCT ensenmei FROM `dj-ga4.scd.research_results` WHERE ensenmei IS NOT NULL AND ensenmei != "" LIMIT 10')
print("沿線一覧:")
for row in results2:
    print(f"  - {row.ensenmei}")

# 総戸数も確認
result3 = bq.fetch_results('SELECT COUNT(*) as cnt FROM `dj-ga4.scd.research_results` WHERE soukosuujuukyo IS NOT NULL AND soukosuujuukyo != ""')
if result3:
    print(f"\n総戸数が入っているレコード数: {result3[0].cnt}")
