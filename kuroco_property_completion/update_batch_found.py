"""残り検証で判明した5件を反映（既存値がある場合は上書きしない）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("残り検証で判明した5件を反映")
logger.info("=" * 70)

updates = [
    {
        'code': '35210012', 'name': 'ポレスター学研奈良登美ヶ丘',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '79'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '学研奈良登美ヶ丘'), "
               "ensenmei = COALESCE(ensenmei, '近鉄けいはんな線'), "
               "toho_fun = COALESCE(toho_fun, '8'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '36210004', 'name': 'ブランシエラ長浜元浜町',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '42'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '7'), "
               "biko = 'haseko.co.jp公式プレスリリースで確認。総戸数42戸(うち非分譲住戸6戸)'",
    },
    {
        'code': '36210030', 'name': 'ヴェリテ大阪福島',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '84'), "
               "chijoukaisuu = COALESCE(chijoukaisuu, '13'), "
               "tochinokenrikubun = '所有権', "
               "ekimei = COALESCE(ekimei, '野田阪神'), "
               "ensenmei = COALESCE(ensenmei, '大阪メトロ千日前線'), "
               "toho_fun = COALESCE(toho_fun, '11'), "
               "kakunin_status = '確認済'",
    },
    {
        'code': '41104700', 'name': 'ルネテラス市川須和田',
        'set': "tochinokenrikubun = '所有権', "
               "biko = 'sgr-sumai.jp公式サイトで確認。総棟数13棟(建築確認未取得区画7棟含む)。JR総武線快速市川駅徒歩15分/京成本線市川真間駅徒歩9-10分'",
    },
    {
        'code': '41103800', 'name': 'グローイングスクエア練馬北町グランデ',
        'set': "soukosuujuukyo = COALESCE(soukosuujuukyo, '9'), "
               "ekimei = COALESCE(ekimei, '地下鉄赤塚'), "
               "ensenmei = COALESCE(ensenmei, '東京メトロ有楽町線・副都心線'), "
               "toho_fun = COALESCE(toho_fun, '6')",
    },
]

for u in updates:
    query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET {u['set']}
    WHERE purojiekutokoodo = '{u['code']}'
    """
    job = bq.execute_query(query)
    logger.info(f"✓ {u['code']}({u['name']}): affected {job.num_dml_affected_rows}")

# 全体進捗確認
progress_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '' AND tochinokenrikubun != '不明') as rights_confirmed
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"\n=== 全体進捗 ===")
logger.info(f"総戸数入力済み: {p.units_filled}/{p.total}件（{p.units_filled/p.total*100:.1f}%）")
logger.info(f"土地権利確定済み(不明以外): {p.rights_confirmed}/{p.total}件（{p.rights_confirmed/p.total*100:.1f}%）")

logger.info("\n" + "=" * 70)
