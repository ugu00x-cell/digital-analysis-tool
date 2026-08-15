"""
Google Geocoding APIを呼び出し、駅名から緯度経度を取得するクライアント
"""
import logging
import os
import time
from typing import Optional

import requests

from kuroco_customer_analysis.models.station_pair import StationLocation

logger = logging.getLogger(__name__)

GEOCODING_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_WAIT_SECONDS = 1.0


class GeocodingClient:
    """駅名を緯度経度に変換するクライアント"""

    def __init__(self, api_key: Optional[str] = None) -> None:
        """APIキーを環境変数または引数から読み込んで初期化する

        Args:
            api_key: Google Maps APIキー。省略時は環境変数GOOGLE_MAPS_API_KEYを使用

        Raises:
            ValueError: APIキーが設定されていない場合
        """
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google Maps APIキーが設定されていません。"
                "環境変数GOOGLE_MAPS_API_KEYを設定してください。"
            )

    def geocode_station(self, station_name: str) -> StationLocation:
        """駅名を緯度経度に変換する

        Args:
            station_name: ジオコーディング対象の駅名（例：「東京駅」）

        Returns:
            StationLocation（失敗時もstatusを含めて返す）
        """
        params = {
            "address": station_name,
            "language": "ja",
            "region": "jp",
            "key": self.api_key,
        }

        for attempt in range(1, DEFAULT_RETRY_COUNT + 1):
            try:
                response = requests.get(
                    GEOCODING_API_URL, params=params, timeout=DEFAULT_TIMEOUT_SECONDS
                )
                response.raise_for_status()
                return self._parse_response(station_name, response.json())
            except requests.RequestException as exc:
                logger.warning(
                    "Geocoding API呼び出し失敗（%d/%d回目）: %s",
                    attempt, DEFAULT_RETRY_COUNT, exc,
                )
                if attempt < DEFAULT_RETRY_COUNT:
                    time.sleep(DEFAULT_RETRY_WAIT_SECONDS * attempt)

        return StationLocation(
            station_name=station_name, latitude=None, longitude=None, status="REQUEST_FAILED"
        )

    def _parse_response(self, station_name: str, payload: dict) -> StationLocation:
        """Geocoding APIのレスポンスJSONを解析し、緯度経度を抽出する

        Args:
            station_name: 対象の駅名
            payload: APIレスポンスのJSON

        Returns:
            解析結果を表すStationLocation
        """
        status = payload.get("status", "UNKNOWN")
        results = payload.get("results", [])
        if status != "OK" or not results:
            logger.info(
                "駅名 %s のジオコーディングに失敗しました（status=%s）", station_name, status
            )
            return StationLocation(
                station_name=station_name, latitude=None, longitude=None, status=status
            )

        result = results[0]
        if not self._is_in_japan(result):
            logger.info(
                "駅名 %s は日本国外の住所に誤マッチしたため除外します（formatted_address=%s）",
                station_name, result.get("formatted_address"),
            )
            return StationLocation(
                station_name=station_name, latitude=None, longitude=None, status="NOT_IN_JAPAN"
            )

        location = result["geometry"]["location"]
        return StationLocation(
            station_name=station_name,
            latitude=location["lat"],
            longitude=location["lng"],
            status="OK",
        )

    def _is_in_japan(self, result: dict) -> bool:
        """ジオコーディング結果が日本国内の住所かどうかを判定する

        自由記述の駅名データが海外の地名等に誤マッチするのを防ぐため、
        address_componentsの国コードがJPかどうかで検証する。

        Args:
            result: Geocoding APIレスポンスの1件分の結果

        Returns:
            日本国内の住所であればTrue
        """
        for component in result.get("address_components", []):
            if "country" in component.get("types", []):
                return component.get("short_name") == "JP"
        return False
