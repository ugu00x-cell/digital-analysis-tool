"""竹中さん確認済み残り5件（マンションレビュー11件チェック完了分）を反映"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("マンションレビュー確認 最終バッチ")
logger.info("=" * 70)

updates = [
    {
        'code': '36210019', 'edaban': None, 'name': 'メイツ京都唐橋',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '65'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '東寺'), "
               "ensenmei = COALESCE(ensenmei, '近鉄京都線'), "
               "toho_fun = COALESCE(toho_fun, '13'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '36210027', 'edaban': None, 'name': 'ルネ鶴見横堤',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '42'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '15'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '横堤'), "
               "ensenmei = COALESCE(ensenmei, '大阪メトロ長堀鶴見緑地線'), "
               "toho_fun = COALESCE(toho_fun, '4'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '36210031', 'edaban': None, 'name': 'メイツ京都梅津',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '68'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '西京極'), "
               "ensenmei = COALESCE(ensenmei, '阪急京都本線'), "
               "toho_fun = COALESCE(toho_fun, '19'), "
               "kakunin_status = '確認済'",
    },
    {
        # エムズシティ鳴子プレディア Ⅱ工区 2棟：333戸は5棟合計のため単独戸数は設定しない
        'code': '37210007', 'edaban': '1.0', 'name': 'エムズシティ鳴子プレディア(2棟)',
        'set': "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "biko = 'エムズシティ鳴子プレディアの一部(全5棟A~E棟構成)。棟別戸数不明。"
               "mansion-review.jpで確認した総戸数333戸は5棟合計のため単独戸数には未反映'",
    },
    {
        # レジデンシャル原ブランシエラ S棟：221戸は全体合計のため単独戸数は設定しない
        'code': '39100700', 'edaban': '1.0', 'name': 'レジデンシャル原ブランシエラ(S棟)',
        'set': "chijoukaisuu = COALESCE(chijoukaisuu, '14')",
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
logger.info(f"\n=== 全体進捗（マンションレビュー11件チェック後） ===")
logger.info(f"総戸数: {p.units_filled}/{p.total}件（{p.units_filled/p.total*100:.1f}%）")
logger.info(f"土地権利確定: {p.rights_confirmed}/{p.total}件（{p.rights_confirmed/p.total*100:.1f}%）")
logger.info("\n" + "=" * 70)
