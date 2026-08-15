"""
geocoding_client.pyのテスト
"""
from unittest.mock import MagicMock, patch

import pytest

from kuroco_customer_analysis.services.geocoding_client import GeocodingClient


def test_init_raises_without_api_key(monkeypatch):
    """異常系: APIキー未設定の場合はValueErrorが発生する"""
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(ValueError):
        GeocodingClient()


def test_geocode_station_success():
    """正常系: 日本国内のOKレスポンスから緯度経度を正しく抽出する"""
    client = GeocodingClient(api_key="dummy-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "geometry": {"location": {"lat": 35.6812, "lng": 139.7671}},
            "address_components": [{"types": ["country"], "short_name": "JP"}],
        }],
    }
    mock_response.raise_for_status.return_value = None

    with patch(
        "kuroco_customer_analysis.services.geocoding_client.requests.get",
        return_value=mock_response,
    ):
        result = client.geocode_station("東京駅")

    assert result.status == "OK"
    assert result.latitude == 35.6812
    assert result.longitude == 139.7671


def test_geocode_station_outside_japan_rejected():
    """異常系: 日本国外にマッチした場合はNOT_IN_JAPANとして除外する"""
    client = GeocodingClient(api_key="dummy-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "OK",
        "results": [{
            "geometry": {"location": {"lat": 37.3387, "lng": -121.8852}},
            "formatted_address": "アメリカ合衆国 カリフォルニア州 サンノゼ",
            "address_components": [{"types": ["country"], "short_name": "US"}],
        }],
    }
    mock_response.raise_for_status.return_value = None

    with patch(
        "kuroco_customer_analysis.services.geocoding_client.requests.get",
        return_value=mock_response,
    ):
        result = client.geocode_station("San Jose, California駅")

    assert result.status == "NOT_IN_JAPAN"
    assert result.latitude is None
    assert result.longitude is None


def test_geocode_station_zero_results():
    """異常系: ZERO_RESULTSの場合は緯度経度がNoneになる"""
    client = GeocodingClient(api_key="dummy-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "ZERO_RESULTS", "results": []}
    mock_response.raise_for_status.return_value = None

    with patch(
        "kuroco_customer_analysis.services.geocoding_client.requests.get",
        return_value=mock_response,
    ):
        result = client.geocode_station("存在しない駅")

    assert result.status == "ZERO_RESULTS"
    assert result.latitude is None
    assert result.longitude is None


def test_geocode_station_empty_results_boundary():
    """境界値: statusがOKでもresultsが空配列の場合は失敗として扱う"""
    client = GeocodingClient(api_key="dummy-key")

    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "OK", "results": []}
    mock_response.raise_for_status.return_value = None

    with patch(
        "kuroco_customer_analysis.services.geocoding_client.requests.get",
        return_value=mock_response,
    ):
        result = client.geocode_station("東京駅")

    assert result.latitude is None
    assert result.longitude is None
