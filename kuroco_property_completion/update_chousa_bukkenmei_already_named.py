"""bukkenmei自体が既に実物件名(ブランド名付き)になっている4件をそのまま転記"""

import logging
from services.bigquery_handler import BigQueryHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bq = BigQueryHandler('dj-ga4', 'scd')

logger.info("=" * 70)
logger.info("bukkenmeiが既に実物件名の4件をそのまま転記")
logger.info("=" * 70)

updates = {
    '37110017': 'サンメゾン久留米西町',
    '39108200': 'ブランシエラ札幌東区役所前',
    '40108100': 'サンメゾン春日原',
    '41106800': 'ドルフィーノ朝霞本町',
}

for code, name in updates.items():
    safe_name = name.replace("'", "''")
    update_query = f"""
    UPDATE `dj-ga4.scd.research_results`
    SET chousa_bukkenmei = '{safe_name}'
    WHERE purojiekutokoodo = '{code}'
    """
    try:
        job = bq.execute_query(update_query)
        affected = getattr(job, "num_dml_affected_rows", None)
        logger.info(f"✓ {code}: {name} (affected: {affected})")
    except Exception as e:
        logger.error(f"✗ {code}: {e}")

logger.info("\n" + "=" * 70)
