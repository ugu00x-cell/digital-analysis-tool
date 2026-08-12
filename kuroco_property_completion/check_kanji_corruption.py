"""既知の誤字パターン（難読漢字誤変換）を全テキストカラムでスキャン"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# 過去に発見された誤字パターン（正しい字 → 誤って変換された字）
# 珍しい字（團・鑑・牡・鐵・荸）は文脈問わず高確度で誤字。茂・荷は普通の字なので文脈確認が必要
rare_suspects = ['團', '鐵', '荸']  # ほぼ確実に誤字と判断できる、実用で滅多に使われない字

print("=== 珍しい誤字候補文字（團・鐵・荸）のスキャン ===\n")
for char in rare_suspects:
    query = f"""
    SELECT purojiekutokoodo, bukkenmei, ensenmei, ekimei, biko, chousa_bukkenmei
    FROM `dj-ga4.scd.research_results`
    WHERE bukkenmei LIKE '%{char}%'
        OR ensenmei LIKE '%{char}%'
        OR ekimei LIKE '%{char}%'
        OR biko LIKE '%{char}%'
        OR chousa_bukkenmei LIKE '%{char}%'
    """
    results = bq.fetch_results(query)
    if results:
        print(f"「{char}」を含む: {len(results)}件")
        for row in results:
            print(f"  {row.purojiekutokoodo}: bukkenmei={row.bukkenmei!r}")
            print(f"    ensenmei={row.ensenmei!r} ekimei={row.ekimei!r}")
            print(f"    biko={row.biko!r}")
    else:
        print(f"「{char}」を含む: 0件")
    print()

# 「磐」→「鑑」誤変換の疑いがある文脈（常磐線→常鑑線など）
print("=== 「鑑」を含むレコード（磐の誤変換疑い） ===\n")
query_kagami = """
SELECT purojiekutokoodo, bukkenmei, ensenmei, ekimei, biko
FROM `dj-ga4.scd.research_results`
WHERE bukkenmei LIKE '%鑑%' OR ensenmei LIKE '%鑑%' OR ekimei LIKE '%鑑%' OR biko LIKE '%鑑%'
"""
results = bq.fetch_results(query_kagami)
print(f"件数: {len(results)}件")
for row in results:
    print(f"  {row.purojiekutokoodo}: ensenmei={row.ensenmei!r} ekimei={row.ekimei!r} biko={row.biko!r}")

# 「牡」を含むレコード（牟の誤変換疑い）
print("\n=== 「牡」を含むレコード（牟の誤変換疑い） ===\n")
query_boshi = """
SELECT purojiekutokoodo, bukkenmei, ensenmei, ekimei, biko
FROM `dj-ga4.scd.research_results`
WHERE bukkenmei LIKE '%牡%' OR ensenmei LIKE '%牡%' OR ekimei LIKE '%牡%' OR biko LIKE '%牡%'
"""
results = bq.fetch_results(query_boshi)
print(f"件数: {len(results)}件")
for row in results:
    print(f"  {row.purojiekutokoodo}: ensenmei={row.ensenmei!r} ekimei={row.ekimei!r} biko={row.biko!r}")

# 「荷」を含むレコード（荻の誤変換疑い・文脈確認要）
print("\n=== 「荷」を含むレコード（荻の誤変換疑いあり・要文脈確認） ===\n")
query_ni = """
SELECT purojiekutokoodo, bukkenmei, ensenmei, ekimei, biko
FROM `dj-ga4.scd.research_results`
WHERE bukkenmei LIKE '%荷%' OR ensenmei LIKE '%荷%' OR ekimei LIKE '%荷%' OR biko LIKE '%荷%'
"""
results = bq.fetch_results(query_ni)
print(f"件数: {len(results)}件")
for row in results:
    print(f"  {row.purojiekutokoodo}: ensenmei={row.ensenmei!r} ekimei={row.ekimei!r} biko={row.biko!r}")

# 「茂」を含むレコード（茅の誤変換疑い・文脈確認要）
print("\n=== 「茂」を含むレコード（茅の誤変換疑いあり・要文脈確認） ===\n")
query_mo = """
SELECT purojiekutokoodo, bukkenmei, ensenmei, ekimei, biko
FROM `dj-ga4.scd.research_results`
WHERE bukkenmei LIKE '%茂%' OR ensenmei LIKE '%茂%' OR ekimei LIKE '%茂%' OR biko LIKE '%茂%'
"""
results = bq.fetch_results(query_mo)
print(f"件数: {len(results)}件")
for row in results:
    print(f"  {row.purojiekutokoodo}: bukkenmei={row.bukkenmei!r} ensenmei={row.ensenmei!r} ekimei={row.ekimei!r} biko={row.biko!r}")
