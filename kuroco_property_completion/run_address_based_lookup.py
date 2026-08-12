"""bukkenmei と zipcode_master から郵便番号を逆引き"""

import logging
import re
from difflib import SequenceMatcher
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("郵便番号逆引き - bukkenmei と zipcode_master からの検索")
logger.info("=" * 70)

# 郵便番号未入力で source_url がある物件を取得
query = """
SELECT
    purojiekutokoodo,
    bukkenmei
FROM `dj-ga4.scd.research_results`
WHERE (yubinkodo1 IS NULL OR yubinkodo1 = '')
    AND source_url IS NOT NULL AND source_url != ''
"""

results = bq.fetch_results(query)
logger.info(f"\n郵便番号未入力で URL がある物件: {len(results)}件\n")

success = 0
failed = 0

for row in results[:10]:  # 試験実行：最初の10件
    code = row.purojiekutokoodo
    name = row.bukkenmei

    # bukkenmei から市区町村を抽出（例：「西浦和」「中野区」など）
    # 最後のカッコの中身を抽出
    address_match = re.search(r'（([^）]+)）', name)
    if address_match:
        address_text = address_match.group(1)
        logger.info(f"{code}: {name}")
        logger.info(f"  抽出住所: {address_text}")

        # zipcode_master で照合
        lookup_query = f"""
        SELECT
            string_field_6 as pref,
            string_field_7 as city,
            string_field_3 as pref_kana,
            string_field_4 as city_kana,
            int64_field_0 as zip_upper,
            int64_field_1 as zip_lower
        FROM `dj-ga4.scd.zipcode_master`
        WHERE string_field_7 LIKE '%{address_text.replace("区", "").replace("市", "")}%'
            OR string_field_6 = '{address_text}'
        LIMIT 3
        """

        try:
            matches = bq.fetch_results(lookup_query)
            if matches:
                m = matches[0]
                logger.info(f"  ✓ 見つかった: {m.pref}{m.city} ({m.zip_upper:03d}-{m.zip_lower:04d})")
                success += 1
            else:
                logger.warning(f"  ✗ 見つかりませんでした")
                failed += 1
        except Exception as e:
            logger.error(f"  ✗ エラー: {e}")
            failed += 1
    else:
        logger.warning(f"{code}: {name}")
        logger.warning(f"  ✗ 住所形式が異なる")
        failed += 1

logger.info(f"\n=== 試験実行結果 ===")
logger.info(f"成功: {success}件")
logger.info(f"失敗: {failed}件")

logger.info("\n" + "=" * 70)
logger.info("試験実行完了")
logger.info("=" * 70)
