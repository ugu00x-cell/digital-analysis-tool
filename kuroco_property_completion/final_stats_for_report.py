"""レポート用の最終統計値を取得"""

from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as zip_filled,
    COUNTIF(ekimei IS NOT NULL AND ekimei != '') as ekimei_filled,
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as ensenmei_filled,
    COUNTIF(ekikoodo IS NOT NULL AND ekikoodo != '') as ekikoodo_filled,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as ensenkoodo_filled,
    COUNTIF(tochinokenrikubun IS NOT NULL AND tochinokenrikubun != '' AND tochinokenrikubun != '不明') as rights_confirmed,
    COUNTIF(tochinokenrikubun = '不明') as rights_unknown,
    COUNTIF(soukosuujuukyo IS NOT NULL AND soukosuujuukyo != '') as units_filled,
    COUNTIF(chousa_bukkenmei IS NOT NULL AND chousa_bukkenmei != '') as chousa_filled
FROM `dj-ga4.scd.research_results`
"""
r = bq.fetch_results(query)[0]

print(f"総件数: {r.total}")
print(f"郵便番号: {r.zip_filled} ({r.zip_filled/r.total*100:.1f}%)")
print(f"駅名: {r.ekimei_filled} ({r.ekimei_filled/r.total*100:.1f}%)")
print(f"沿線名: {r.ensenmei_filled} ({r.ensenmei_filled/r.total*100:.1f}%)")
print(f"駅コード: {r.ekikoodo_filled}/{r.ekimei_filled} ({r.ekikoodo_filled/r.ekimei_filled*100:.1f}%)")
print(f"沿線コード: {r.ensenkoodo_filled}/{r.ensenmei_filled} ({r.ensenkoodo_filled/r.ensenmei_filled*100:.1f}%)")
print(f"土地権利確定(不明以外): {r.rights_confirmed} ({r.rights_confirmed/r.total*100:.1f}%)")
print(f"土地権利不明: {r.rights_unknown} ({r.rights_unknown/r.total*100:.1f}%)")
print(f"総戸数: {r.units_filled} ({r.units_filled/r.total*100:.1f}%)")
print(f"chousa_bukkenmei: {r.chousa_filled} ({r.chousa_filled/r.total*100:.1f}%)")
