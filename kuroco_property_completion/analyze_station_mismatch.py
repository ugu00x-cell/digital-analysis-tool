"""駅名・沿線名の表記ゆれパターンを分析"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# research_results の駅名と、project_info内の同一駅名（表記違いも含む）候補を比較
query = """
SELECT DISTINCT
    r.purojiekutokoodo,
    r.ekimei as research_ekimei,
    r.ensenmei as research_ensenmei,
    p_exact.ekikoodo as exact_match_code
FROM `dj-ga4.scd.research_results` r
LEFT JOIN `dj-ga4.scd.project_info` p_exact
    ON r.purojiekutokoodo = p_exact.purojiekutokoodo AND r.ekimei = p_exact.ekimei
WHERE r.ekimei IS NOT NULL AND r.ekimei != ''
ORDER BY r.purojiekutokoodo
"""
results = bq.fetch_results(query)

unmatched = [r for r in results if not r.exact_match_code]
print(f"総駅名レコード: {len(results)}件")
print(f"完全一致でマッチ: {len(results) - len(unmatched)}件")
print(f"未マッチ: {len(unmatched)}件\n")

# project_info 側で、同じプロジェクトコードの駅名を確認（表記ゆれ比較用）
print("=== 未マッチレコードとproject_info側の実際の駅名を比較 ===\n")
for r in unmatched[:30]:
    p_query = f"""
    SELECT ekimei, ensenmei, ekikoodo, ensenkoodo
    FROM `dj-ga4.scd.project_info`
    WHERE purojiekutokoodo = '{r.purojiekutokoodo}'
    LIMIT 1
    """
    p_result = bq.fetch_results(p_query)
    if p_result:
        p = p_result[0]
        print(f"{r.purojiekutokoodo}:")
        print(f"  research: 駅={r.research_ekimei!r} 沿線={r.research_ensenmei!r}")
        print(f"  project_info: 駅={p.ekimei!r} 沿線={p.ensenmei!r} 駅コード={p.ekikoodo!r}")
        print()
