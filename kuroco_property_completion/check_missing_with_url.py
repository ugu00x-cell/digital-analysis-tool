"""郵便番号未入力で source_url がある物件を確認"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# 郵便番号未入力のうち、source_url がある物件を確認
query = """
SELECT
    COUNT(*) as total,
    COUNTIF(source_url IS NOT NULL AND source_url != '') as with_url,
    COUNTIF(source_url IS NULL OR source_url = '') as without_url
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NULL OR yubinkodo1 = ''
"""

result = bq.fetch_results(query)[0]

print("=== 郵便番号未入力レコードの source_url 状況 ===\n")
print(f"総件数: {result.total}件")
print(f"source_url あり: {result.with_url}件")
print(f"source_url なし: {result.without_url}件")

# source_url がある物件のサンプルを確認
if result.with_url > 0:
    print(f"\n=== サンプル（source_url あり：最初の5件） ===\n")
    sample_query = """
    SELECT
        purojiekutokoodo,
        bukkenmei,
        source_url
    FROM `dj-ga4.scd.research_results`
    WHERE (yubinkodo1 IS NULL OR yubinkodo1 = '')
        AND source_url IS NOT NULL AND source_url != ''
    LIMIT 5
    """

    samples = bq.fetch_results(sample_query)
    for row in samples:
        print(f"{row.purojiekutokoodo}: {row.bukkenmei}")
        print(f"  URL: {row.source_url}\n")
