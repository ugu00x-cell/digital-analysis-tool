"""
通勤距離分析（直線距離版）のオーケストレーションスクリプト

customer_dataからユニークな駅名を抽出し、Geocoding APIで緯度経度を取得、
station_masterテーブルに保存した上で、BigQuery側で直線距離を計算する。

※ Google Maps Platformの仕様上、日本の交通事業者はTRANSIT（電車移動時間）モードに
  非対応のため、簡易指標として直線距離を採用している（2026/08/06クライアント合意）。
"""
import logging
import time
from typing import List

from kuroco_customer_analysis.models.station_pair import StationLocation
from kuroco_customer_analysis.services.bigquery_client import BigQueryStationClient
from kuroco_customer_analysis.services.geocoding_client import GeocodingClient
from kuroco_customer_analysis.utils.station_name_utils import normalize_station_name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REQUEST_INTERVAL_SECONDS = 0.05  # APIレート制限を考慮した待機時間


def geocode_stations(station_names: List[str], client: GeocodingClient) -> List[StationLocation]:
    """駅名のリストをジオコーディングし、緯度経度を取得する

    Args:
        station_names: 正規化済みの駅名リスト（重複なし前提）
        client: GeocodingClientのインスタンス

    Returns:
        StationLocationのリスト
    """
    results: List[StationLocation] = []
    total = len(station_names)

    for index, name in enumerate(station_names, start=1):
        results.append(client.geocode_station(name))
        if index % 100 == 0:
            logger.info("ジオコーディング進捗: %d/%d件", index, total)
        time.sleep(REQUEST_INTERVAL_SECONDS)

    return results


def main() -> None:
    """通勤距離分析（直線距離版）のメイン処理"""
    bq_client = BigQueryStationClient()
    geocoding_client = GeocodingClient()

    logger.info("customer_dataからユニークな駅名を抽出します")
    raw_names = bq_client.fetch_unique_station_names()
    normalized_names = sorted({normalize_station_name(n) for n in raw_names if n})
    logger.info("%d件のユニーク駅名を抽出しました", len(normalized_names))

    locations = geocode_stations(normalized_names, geocoding_client)
    success_count = sum(1 for loc in locations if loc.status == "OK")
    logger.info("ジオコーディング完了: %d/%d件成功", success_count, len(locations))

    bq_client.save_station_master(locations)
    bq_client.compute_straight_line_distances("dj-ga4.scd.commute_distance_results")

    logger.info("通勤距離分析（直線距離版）が完了しました")


if __name__ == "__main__":
    main()
