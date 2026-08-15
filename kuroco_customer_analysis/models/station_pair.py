"""
駅名・緯度経度データのデータクラス定義
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class StationLocation:
    """駅名と緯度経度を表すデータクラス

    Attributes:
        station_name: 駅名
        latitude: 緯度。ジオコーディング失敗時はNone
        longitude: 経度。ジオコーディング失敗時はNone
        status: ジオコーディング結果のステータス（"OK"、"ZERO_RESULTS"等）
    """
    station_name: str
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
