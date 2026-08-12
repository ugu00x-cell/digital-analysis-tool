"""同期後の research_results データを確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT
    purojiekutokoodo,
    bukkenmei,
    yubinkodo1,
    ekimei,
    ensenmei,
    tochinokenrikubun,
    soukosuujuukyo
FROM `dj-ga4.scd.research_results`
LIMIT 10
"""

results = bq.fetch_results(query)

print("=== 同期後の research_results サンプル ===\n")
for row in results:
    print(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    print(f"  郵便番号: {row.yubinkodo1} | 駅名: {row.ekimei} | 沿線: {row.ensenmei}")
    print(f"  権利: {row.tochinokenrikubun} | 総戸数: {row.soukosuujuukyo}\n")
