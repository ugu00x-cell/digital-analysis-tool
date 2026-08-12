"""biko カラムから住所を抽出して郵便番号を検索"""

import logging
import re
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("郵便番号補完 - biko から住所を抽出")
logger.info("=" * 70)

# 補完前の状態確認
before_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as filled
FROM `dj-ga4.scd.research_results`
"""

before = bq.fetch_results(before_query)[0]
logger.info(f"\n=== 補完前 ===")
logger.info(f"総件数: {before.total}件")
logger.info(f"郵便番号入力済み: {before.filled}件")

# biko に住所情報が含まれているレコードを取得
biko_query = """
SELECT
    purojiekutokoodo,
    biko
FROM `dj-ga4.scd.research_results`
WHERE (yubinkodo1 IS NULL OR yubinkodo1 = '')
    AND biko IS NOT NULL AND biko != ''
"""

results = bq.fetch_results(biko_query)
logger.info(f"\nbiko に住所情報がある未入力レコード: {len(results)}件")

# 都道府県・市区町村パターン
pref_pattern = re.compile(
    r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|'
    r'新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|'
    r'奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|'
    r'熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
)

success = 0
for row in results[:20]:  # 試験実行：最初の20件
    code = row.purojiekutokoodo
    biko_text = row.biko

    # biko から都道府県を抽出
    pref_match = pref_pattern.search(biko_text)
    if pref_match:
        pref = pref_match.group(1)
        logger.info(f"\n{code}:")
        logger.info(f"  biko: {biko_text[:80]}")
        logger.info(f"  抽出都道府県: {pref}")

        # zipcode_master で照合
        lookup_query = f"""
        SELECT DISTINCT
            string_field_6 as pref,
            string_field_7 as city,
            CAST(int64_field_0 AS STRING) as zip_upper,
            CAST(int64_field_1 AS STRING) as zip_lower
        FROM `dj-ga4.scd.zipcode_master`
        WHERE string_field_6 = '{pref}'
        LIMIT 1
        """

        try:
            matches = bq.fetch_results(lookup_query)
            if matches:
                m = matches[0]
                logger.info(f"  → 郵便番号: {m.zip_upper}-{m.zip_lower}")
                success += 1
            else:
                logger.warning(f"  → 郵便番号未検出")
        except Exception as e:
            logger.error(f"  → エラー: {e}")

logger.info(f"\n=== 試験実行結果 ===")
logger.info(f"成功: {success}件")

logger.info("\n" + "=" * 70)
logger.info("試験実行完了")
logger.info("=" * 70)
