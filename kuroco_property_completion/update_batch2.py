"""竹中さんが確認してくれた5件を反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("竹中さん確認済み5件を反映")
logger.info("=" * 70)

updates = [
    {
        # I棟：824戸はレジデンス全体(I+II+III工区)の合計と思われるため、
        # 単独戸数は設定せず、駅・階建・biko注記のみ更新（II=380,III=152と重複回避）
        'code': '33210021', 'edaban': '0.0', 'name': 'ローレルスクエア健都 Ⅰ棟',
        'set': "chijoukaisuu = COALESCE(chijoukaisuu, '20'), "
               "ekimei = COALESCE(ekimei, '岸辺'), "
               "ensenmei = COALESCE(ensenmei, 'JR東海道本線'), "
               "toho_fun = COALESCE(toho_fun, '7'), "
               "biko = '既存値で埋まっていた項目は変更なし、土地権利のみ確認。"
               "mansion-review.jpの「ローレルスクエア健都ザ・レジデンス」ページでは総戸数824戸(Ⅰ+Ⅱ+Ⅲ工区合計と推定)。"
               "Ⅱ工区380戸・Ⅲ工区152戸は別途記録済みのためⅠ棟単独の内訳は不明のまま'",
    },
    {
        'code': '34210012', 'edaban': None, 'name': 'ルネ西宮仁川',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '236'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '14'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '仁川'), "
               "ensenmei = COALESCE(ensenmei, '阪急今津線'), "
               "toho_fun = COALESCE(toho_fun, '16'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '35210019', 'edaban': None, 'name': 'エムズシティ新安城ブランシエラ',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '163'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '15'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '新安城'), "
               "ensenmei = COALESCE(ensenmei, '名鉄名古屋本線'), "
               "toho_fun = COALESCE(toho_fun, '5'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '36210003', 'edaban': None, 'name': 'クラッシィハウス尼崎ＧＬＡＮＤＰＬＡＣＥ',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '457'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '15'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '尼崎'), "
               "ensenmei = COALESCE(ensenmei, 'JR東海道本線'), "
               "toho_fun = COALESCE(toho_fun, '3'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '36210017', 'edaban': None, 'name': 'アルバックス蒲郡レジデンス',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '55'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '蒲郡'), "
               "ensenmei = COALESCE(ensenmei, 'JR東海道本線'), "
               "toho_fun = COALESCE(toho_fun, '11'), "
               "kakunin_status = '確認済'",
    },
]

for u in updates:
    where = f"purojiekutokoodo = '{u['code']}'"
    if u['edaban']:
        where += f" AND purojiekutoedaban = '{u['edaban']}'"
    query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET {u['set']}
    WHERE {where}
    """
    job = bq.execute_query(query)
    logger.info(f"✓ {u['code']}({u['name']}): affected {job.num_dml_affected_rows}")

# 進捗確認
progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '' AND tochinokenrikubun != '不明') as rights_confirmed
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== 全体進捗 ===")
logger.info(f"総戸数: {p.units_filled}/{p.total}件（{p.units_filled/p.total*100:.1f}%）")
logger.info(f"土地権利確定: {p.rights_confirmed}/{p.total}件（{p.rights_confirmed/p.total*100:.1f}%）")
logger.info("\n" + "=" * 70)
