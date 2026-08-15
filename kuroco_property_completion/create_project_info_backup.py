"""project_info のバックアップ(project_info_bk)を作成"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("project_info_bk（バックアップ）を作成")
logger.info("=" * 70)

# 既存件数を確認
before = bq.fetch_results("SELECT COUNT(*) as cnt FROM `dj-ga4.scd.project_info`")[0]
logger.info(f"\nproject_info 現在の件数: {before.cnt}件")

# CREATE OR REPLACEでバックアップテーブルを作成
backup_query = """
CREATE OR REPLACE TABLE `dj-ga4.scd.project_info_bk` AS
SELECT * FROM `dj-ga4.scd.project_info`
"""
job = bq.execute_query(backup_query)
logger.info("✓ project_info_bk を作成しました")

# 確認
after = bq.fetch_results("SELECT COUNT(*) as cnt FROM `dj-ga4.scd.project_info_bk`")[0]
logger.info(f"project_info_bk の件数: {after.cnt}件")

if after.cnt == before.cnt:
    logger.info("\n✅ バックアップ完了：件数が一致しています")
else:
    logger.warning(f"\n⚠️ 件数が一致しません（元:{before.cnt} バックアップ:{after.cnt}）")

logger.info("\n" + "=" * 70)
