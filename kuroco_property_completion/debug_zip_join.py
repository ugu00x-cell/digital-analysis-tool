"""郵便番号JOINの問題を診断"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# サンプルの郵便番号を取得
sample = bq.fetch_results("""
SELECT purojiekutokoodo, bukkenmei, yubinkodo1, yubinkodo2
FROM `dj-ga4.scd.research_results`
WHERE yubinkodo1 IS NOT NULL AND yubinkodo1 != ''
LIMIT 3
""")

print("=== research_results のサンプル郵便番号 ===")
for row in sample:
    print(f"{row.purojiekutokoodo}: {row.bukkenmei}")
    print(f"  yubinkodo1='{row.yubinkodo1}' (型: {type(row.yubinkodo1).__name__})")
    print(f"  yubinkodo2='{row.yubinkodo2}' (型: {type(row.yubinkodo2).__name__})")

    # この郵便番号でzipcode_masterを検索
    zip1 = row.yubinkodo1
    zip2 = row.yubinkodo2

    search = bq.fetch_results(f"""
    SELECT int64_field_0, int64_field_1, string_field_6, string_field_7
    FROM `dj-ga4.scd.zipcode_master`
    WHERE int64_field_0 = {int(zip1)}
    LIMIT 3
    """)

    print(f"  zipcode_masterでの検索結果（上3桁={int(zip1)}）:")
    for s in search:
        print(f"    上{s.int64_field_0} 下{s.int64_field_1}: {s.string_field_6}{s.string_field_7}")
    print()
