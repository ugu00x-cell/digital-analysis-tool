"""project_info反映の影響件数を事前確認（ドライラン・読み取りのみ）"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

print("=" * 70)
print("project_info 反映の影響件数（ドライラン）")
print("=" * 70)

columns = [
    ('yubinkodo1', 'yuubinbangou1_ue3keta'),
    ('yubinkodo2', 'yuubinbangou2_shita4keta'),
    ('ekimei', 'ekimei'),
    ('ensenmei', 'ensenmei'),
    ('soukosuujuukyo', 'soukosuujuukyo'),
    ('ekikoodo', 'ekikoodo'),
    ('ensenkoodo', 'ensenkoodo'),
]

for r_col, p_col in columns:
    query = f"""
    SELECT COUNT(*) as cnt
    FROM `dj-ga4.scd.research_results` r
    JOIN `dj-ga4.scd.project_info` p
        ON r.purojiekutokoodo = p.purojiekutokoodo
        AND r.purojiekutoedaban = p.purojiekutoedaban
    WHERE r.{r_col} IS NOT NULL AND r.{r_col} != ''
        AND (p.{p_col} IS NULL OR p.{p_col} = '')
    """
    result = bq.fetch_results(query)[0]
    print(f"{r_col} → {p_col}: {result.cnt}件 更新見込み")

# tochinokenrikubun は「空欄 or 未確認」も対象
query_rights = """
SELECT COUNT(*) as cnt
FROM `dj-ga4.scd.research_results` r
JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
    AND r.purojiekutoedaban = p.purojiekutoedaban
WHERE r.tochinokenrikubun IS NOT NULL AND r.tochinokenrikubun != '' AND r.tochinokenrikubun != '不明'
    AND (p.tochinokenrikubun IS NULL OR p.tochinokenrikubun = '' OR p.tochinokenrikubun = '不明')
"""
result_rights = bq.fetch_results(query_rights)[0]
print(f"tochinokenrikubun → tochinokenrikubun: {result_rights.cnt}件 更新見込み")

# 結合キーでマッチしないレコードも確認
query_nomatch = """
SELECT COUNT(*) as cnt
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p
    ON r.purojiekutokoodo = p.purojiekutokoodo
    AND r.purojiekutoedaban = p.purojiekutoedaban
WHERE p.purojiekutokoodo IS NULL
"""
nomatch = bq.fetch_results(query_nomatch)[0]
print(f"\nproject_info側にマッチしないレコード: {nomatch.cnt}件")

print("\n" + "=" * 70)
