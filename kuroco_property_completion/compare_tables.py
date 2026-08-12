"""research_results と project_info を具体的に比較"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# research_results のデータ
query_r = """
SELECT *
FROM `dj-ga4.scd.research_results`
WHERE purojiekutokoodo = '36210004'
"""

# project_info のデータ
query_p = """
SELECT *
FROM `dj-ga4.scd.project_info`
WHERE purojiekutokoodo = '36210004'
"""

print("=== research_results (プロジェクトコード 36210004) ===")
results_r = bq.fetch_results(query_r)
if results_r:
    row = results_r[0]
    print(f"purojiekutokoodo: {row.purojiekutokoodo}")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"yubinkodo1: {row.yubinkodo1}")
    print(f"yubinkodo2: {row.yubinkodo2}")
    print(f"ekimei: {row.ekimei}")
    print(f"ensenmei: {row.ensenmei}")
    print(f"soukosuujuukyo: {row.soukosuujuukyo}")
    print(f"tochinokenrikubun: {row.tochinokenrikubun}")

print("\n=== project_info (プロジェクトコード 36210004) ===")
results_p = bq.fetch_results(query_p)
if results_p:
    row = results_p[0]
    print(f"purojiekutokoodo: {row.purojiekutokoodo}")
    print(f"bukkenmei: {row.bukkenmei}")
    print(f"yuubinbangou1_ue3keta: {row.yuubinbangou1_ue3keta}")
    print(f"yuubinbangou2_shita4keta: {row.yuubinbangou2_shita4keta}")
    print(f"ekimei: {row.ekimei}")
    print(f"ensenmei: {row.ensenmei}")
    print(f"soukosuujuukyo: {row.soukosuujuukyo}")
    print(f"tochinokenrikubun: {row.tochinokenrikubun}")
