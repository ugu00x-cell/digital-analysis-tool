"""
Service 1: データ収集APIのテスト

正常系2・異常系2・境界値1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from services.collector.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """テスト用クライアント（一時DBを使用）"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("shared.config.DB_PATH", db_path)
    monkeypatch.setattr("shared.database.DB_PATH", db_path)
    from shared.database import init_db
    init_db()
    return TestClient(app)


class TestReceiveVibration:
    """振動データ1件受信のテスト"""

    def test_normal_single(self, client: TestClient) -> None:
        """正常系: 1件の振動データを正常に保存できる"""
        resp = client.post("/api/v1/vibration", json={
            "device_id": "m5stick_01",
            "timestamp": "2026-04-12T10:00:00",
            "x": 0.01, "y": -0.03, "z": 1.02,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["saved_count"] == 1

    def test_normal_count_increments(self, client: TestClient) -> None:
        """正常系: 連続送信でカウントが増加する"""
        for i in range(3):
            client.post("/api/v1/vibration", json={
                "device_id": "m5stick_01",
                "timestamp": f"2026-04-12T10:00:0{i}",
                "x": 0.01, "y": 0.02, "z": 1.0,
            })
        resp = client.get("/api/v1/devices/m5stick_01/count")
        assert resp.json()["data_count"] == 3

    def test_error_missing_field(self, client: TestClient) -> None:
        """異常系: 必須フィールド欠落で422"""
        resp = client.post("/api/v1/vibration", json={
            "device_id": "m5stick_01",
            "x": 0.01,
        })
        assert resp.status_code == 422

    def test_error_invalid_timestamp(self, client: TestClient) -> None:
        """異常系: 不正なtimestamp形式で422"""
        resp = client.post("/api/v1/vibration", json={
            "device_id": "m5stick_01",
            "timestamp": "not-a-date",
            "x": 0.01, "y": 0.02, "z": 1.0,
        })
        assert resp.status_code == 422

    def test_boundary_zero_values(self, client: TestClient) -> None:
        """境界値: x=y=z=0.0でも正常に保存できる"""
        resp = client.post("/api/v1/vibration", json={
            "device_id": "m5stick_01",
            "timestamp": "2026-04-12T10:00:00",
            "x": 0.0, "y": 0.0, "z": 0.0,
        })
        assert resp.status_code == 200


class TestBatchReceive:
    """一括受信のテスト"""

    def test_normal_batch(self, client: TestClient) -> None:
        """正常系: 複数サンプルを一括保存"""
        samples = [
            {
                "device_id": "m5stick_01",
                "timestamp": f"2026-04-12T10:00:0{i}",
                "x": 0.01, "y": 0.02, "z": 1.0 + i * 0.01,
            }
            for i in range(5)
        ]
        resp = client.post("/api/v1/vibration/batch", json={
            "device_id": "m5stick_01",
            "samples": samples,
        })
        assert resp.status_code == 200
        assert resp.json()["saved_count"] == 5


class TestHealth:
    """ヘルスチェックのテスト"""

    def test_health(self, client: TestClient) -> None:
        """正常系: ヘルスチェックが応答する"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
