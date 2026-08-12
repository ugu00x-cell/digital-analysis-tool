"""project_info から research_results へデータを同期（個別UPDATE版）"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=== 方針変更：project_info から住所・郵便番号・駅・沿線コードを取得 ===")

# 1. research_results の各プロジェクトコードについて、project_info から対応データを取得
query = """
SELECT DISTINCT r.purojiekutokoodo
FROM `dj-ga4.scd.research_results` r
WHERE r.yubinkodo1 IS NULL OR r.yubinkodo1 = ''
"""

results = bq.fetch_results(query)
logger.info(f"郵便番号が未入力のプロジェクト: {len(results)}件")

# 2. 各プロジェクトコードについて project_info からデータを取得して同期
updated = 0
failed = 0
for i, row in enumerate(results, 1):  # 全量実行
    code = row.purojiekutokoodo
    if i % 50 == 0:
        logger.info(f"進捗: {i}/{len(results)}件処理中...")

    lookup_query = f"""
    SELECT
        yuubinbangou1_ue3keta,
        yuubinbangou2_shita4keta,
        todoufukenkoodo,
        shikuchousonkoodo,
        ensenkoodo,
        ekikoodo
    FROM `dj-ga4.scd.project_info`
    WHERE purojiekutokoodo = '{code}'
    LIMIT 1
    """

    project_rows = bq.fetch_results(lookup_query)
    if project_rows:
        p = project_rows[0]
        zip1 = p.yuubinbangou1_ue3keta or ""
        zip2 = p.yuubinbangou2_shita4keta or ""

        if zip1:  # 郵便番号がある場合だけ更新
            update_query = f"""
            UPDATE `dj-ga4.scd.research_results`
            SET yubinkodo1 = '{zip1}',
                yubinkodo2 = '{zip2}'
            WHERE purojiekutokoodo = '{code}'
            """

            try:
                bq.execute_query(update_query)
                updated += 1
            except Exception as e:
                failed += 1
                logger.error(f"✗ {code}: {e}")

logger.info(f"\n=== 郵便番号補完完了 ===")
logger.info(f"成功: {updated}件")
logger.info(f"失敗: {failed}件")
logger.info(f"スキップ: {len(results) - updated - failed}件（郵便番号なし）")

# 3. 最終確認
check_query = """
SELECT
    COUNT(*) as total,
    COUNTIF(yubinkodo1 IS NOT NULL AND yubinkodo1 != '') as filled
FROM `dj-ga4.scd.research_results`
"""

final = bq.fetch_results(check_query)
if final:
    f = final[0]
    logger.info(f"\n=== 最終状態 ===")
    logger.info(f"総件数: {f.total}件")
    logger.info(f"郵便番号入力済み: {f.filled}件")
    logger.info(f"補完率: {f.filled / f.total * 100:.1f}%")
