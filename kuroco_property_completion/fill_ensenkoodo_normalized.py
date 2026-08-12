"""事業者名表記ゆれを正規化して沿線コードを再照合"""

import logging
import re
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')


def normalize(name: str) -> str:
    """路線名の表記ゆれを吸収する正規化関数"""
    if not name:
        return ""
    n = name
    # 「(」以降の補足表記を削除（例：東海道線(JR神戸線) → 東海道線）
    n = re.sub(r'[（(].*?[）)]', '', n)
    # 事業者名の別名統一
    replacements = [
        ('東京メトロ', '東京地下鉄'),
        ('小田急電鉄', '小田急'),
        ('京王電鉄', '京王'),
        ('東武鉄道', '東武'),
        ('西武鉄道', '西武'),
        ('相模鉄道', '相鉄'),
        ('京成電鉄', '京成'),
        ('京浜急行電鉄', '京急'),
        ('阪急電鉄', '阪急'),
        ('阪神電鉄', '阪神'),
        ('南海電鉄', '南海'),
        ('名古屋市営', '名古屋市'),
        ('京都市営地下鉄', '京都市'),
        ('都営', '東京都'),
        ('JR', ''),
        ('ＪＲ', ''),
    ]
    for old, new in replacements:
        n = n.replace(old, new)
    return n.strip()


# project_infoの沿線マスタを正規化キー付きで取得
master_query = """
SELECT ensenmei, ensenkoodo, COUNT(*) as cnt
FROM `dj-ga4.scd.project_info`
WHERE ensenmei IS NOT NULL AND ensenmei != '' AND ensenkoodo IS NOT NULL AND ensenkoodo != ''
GROUP BY ensenmei, ensenkoodo
"""
master_rows = bq.fetch_results(master_query)

# 正規化名 → 最頻出コード のマップを構築
norm_map = {}
norm_counts = {}
for row in master_rows:
    norm_key = normalize(row.ensenmei)
    if norm_key not in norm_counts or row.cnt > norm_counts[norm_key]:
        norm_map[norm_key] = row.ensenkoodo
        norm_counts[norm_key] = row.cnt

logger.info(f"正規化後のユニークキー数: {len(norm_map)}件（元{len(master_rows)}件）")

# research_results の未マッチ沿線名を取得（複数路線が「・」区切りの場合は先頭のみ使用）
unmatched_query = """
SELECT purojiekutokoodo, ensenmei
FROM `dj-ga4.scd.research_results`
WHERE ensenmei IS NOT NULL AND ensenmei != ''
    AND (ensenkoodo IS NULL OR ensenkoodo = '')
"""
unmatched_rows = bq.fetch_results(unmatched_query)
logger.info(f"未マッチ件数: {len(unmatched_rows)}件\n")

updates = []
still_unmatched = []
for row in unmatched_rows:
    # 「・」で複数路線が連結されている場合は最初の路線名のみ使用
    first_line = row.ensenmei.split('・')[0]
    norm_key = normalize(first_line)

    if norm_key in norm_map:
        updates.append((row.purojiekutokoodo, row.ensenmei, norm_map[norm_key]))
    else:
        still_unmatched.append(row.ensenmei)

logger.info(f"正規化照合でマッチ: {len(updates)}件")
logger.info(f"依然として未マッチ: {len(set(still_unmatched))}種類\n")

# 個別UPDATE実行（同じコードごとにグループ化して効率化）
success = 0
for code, ensenmei, ensenkoodo in updates:
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET ensenkoodo = '{ensenkoodo}'
    WHERE purojiekutokoodo = '{code}' AND ensenmei = '{ensenmei.replace("'", "''")}'
        AND (ensenkoodo IS NULL OR ensenkoodo = '')
    """
    try:
        job = bq.execute_query(update_query)
        success += 1
    except Exception as e:
        logger.error(f"✗ {code}: {e}")

logger.info(f"UPDATE成功: {success}件\n")

# 最終進捗
progress_query = """
SELECT
    COUNTIF(ensenmei IS NOT NULL AND ensenmei != '') as ensenmei_filled,
    COUNTIF(ensenkoodo IS NOT NULL AND ensenkoodo != '') as ensenkoodo_filled
FROM `dj-ga4.scd.research_results`
"""
p = bq.fetch_results(progress_query)[0]
logger.info(f"=== 沿線コード最終進捗 ===")
logger.info(f"ensenmei入力済み: {p.ensenmei_filled}件")
logger.info(f"ensenkoodo入力済み: {p.ensenkoodo_filled}件（{p.ensenkoodo_filled / p.ensenmei_filled * 100:.1f}%）")

logger.info(f"\n=== 依然未マッチの沿線名（要確認） ===")
for name in sorted(set(still_unmatched)):
    logger.info(f"  {name!r}")
