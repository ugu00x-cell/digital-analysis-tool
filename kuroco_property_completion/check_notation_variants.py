"""未マッチ駅名のうち、表記ゆれの可能性があるものをproject_infoの全駅名リストと類似度比較"""

from difflib import SequenceMatcher
from services.bigquery_handler import BigQueryHandler

bq = BigQueryHandler('dj-ga4', 'scd')

# project_infoの全駅名（コードあり）を取得
master_query = """
SELECT DISTINCT ekimei, ekikoodo
FROM `dj-ga4.scd.project_info`
WHERE ekimei IS NOT NULL AND ekimei != '' AND ekikoodo IS NOT NULL AND ekikoodo != ''
"""
master = bq.fetch_results(master_query)
master_names = [(r.ekimei, r.ekikoodo) for r in master]

unmatched_names = [
    'あざみ野', '与野本町', '中神', '久我山', '勝山町', '北国分', '北綾瀬', '北茅ヶ崎',
    '南平岸', '南栗橋', '南町田グランベリーパーク', '南砂町', '南阿佐ヶ谷', '古島', '国立',
    '土浦', '地下鉄成増', '大泉学園', '大町西公園', '天台', '宮崎神宮', '小田原', '新井宿',
    '朝雺', '本八幕', '東武動物公園', '東海神', '東陽町', '栃木', '桑園', '水戸',
    '流山おおたかの森', '浜野', '海神', '環状通東', '田町', '祖師ヶ谷大蔵', '稲毛', '花畑',
    '茶山', '葛西', '葛西臨海公園', '西28丁目', '西大宮', '西白井', '西葛西', '西調布',
    '谷塚', '赤十字病院前', '赤迫', '辻堂', '都府楼前', '都賀', '金沢', '金町',
    '電車事業所前', '青森', '高根公団', '鷒池',
]

print("=== 類似度70%以上の候補（表記ゆれの可能性） ===\n")
for name in unmatched_names:
    best_match = None
    best_score = 0
    for m_name, m_code in master_names:
        score = SequenceMatcher(None, name, m_name).ratio()
        if score > best_score:
            best_score = score
            best_match = (m_name, m_code)

    if best_score >= 0.6:
        print(f"{name!r} → 候補: {best_match[0]!r} (コード:{best_match[1]}, 類似度:{best_score:.2f})")
