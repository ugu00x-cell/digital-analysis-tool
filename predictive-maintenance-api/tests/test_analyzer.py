"""
Service 2: 異常検知APIのテスト

正常系2・異常系2・境界値1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytest
from fastapi.testclient import TestClient

from services.analyzer.engine import analyze, compute_fft, preprocess
from services.analyzer.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """テスト用クライアント（一時DBを使用）"""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("shared.config.DB_PATH", db_path)
    monkeypatch.setattr("shared.database.DB_PATH", db_path)
    from shared.database import init_db
    init_db()
    return TestClient(app)


class TestEngine:
    """解析エンジン単体のテスト"""

    def test_normal_sine_wave(self) -> None:
        """正常系: 正弦波入力で異常なしと判定される"""
        t = np.linspace(0, 2, 1000)
        z = np.sin(2 * np.pi * 50 * t) * 0.1  # 50Hz, 振幅0.1g
        result = analyze(z)
        assert result["is_anomaly"] is False
        assert result["sample_count"] == 1000

    def test_normal_fft_peak(self) -> None:
        """正常系: FFTのピーク周波数が入力周波数と一致する"""
        fs = 500
        t = np.linspace(0, 1, fs, endpoint=False)
        x = np.sin(2 * np.pi * 100 * t)  # 100Hzの正弦波
        freq, amp = compute_fft(x, fs)
        peak = freq[np.argmax(amp)]
        assert abs(peak - 100.0) < 5.0  # 5Hz以内

    def test_error_short_data(self) -> None:
        """異常系: データ不足でValueError"""
        z = np.array([0.1, 0.2, 0.3])  # 3サンプルでは不足
        with pytest.raises(ValueError, match="データ不足"):
            analyze(z)

    def test_error_constant_data(self) -> None:
        """異常系: 定数データでもエラーにならない"""
        z = np.ones(1000) * 0.5
        result = analyze(z)
        assert result["mean_rms"] >= 0

    def test_boundary_anomaly_detection(self) -> None:
        """境界値: RMSレベルが異なるセグメントが混在すると異常検出される"""
        # 正常19セグメント + 異常1セグメント（比率を上げてZスコア>3に）
        z_normal = np.tile(
            np.sin(np.linspace(0, 2 * np.pi, 500)) * 0.01, 19,
        )
        z_anomaly = np.sin(np.linspace(0, 2 * np.pi, 500)) * 1.0
        z = np.concatenate([z_normal, z_anomaly])
        result = analyze(z)
        assert result["max_z_score"] > 3.0
        assert result["is_anomaly"] is True


class TestAnalyzeAPI:
    """解析APIエンドポイントのテスト"""

    def _insert_test_data(
        self, client: TestClient, n: int = 1000,
    ) -> None:
        """テスト用の振動データを投入する"""
        from services.collector.main import app as collector_app
        coll_client = TestClient(collector_app)

        samples = []
        for i in range(n):
            samples.append({
                "device_id": "test_device",
                "timestamp": f"2026-04-12T10:00:{i // 60:02d}.{i % 60 * 16666:06d}",
                "x": 0.01,
                "y": 0.02,
                "z": float(np.sin(2 * np.pi * 50 * i / 500) * 0.1),
            })
        coll_client.post("/api/v1/vibration/batch", json={
            "device_id": "test_device",
            "samples": samples,
        })

    def test_normal_analyze(self, client: TestClient) -> None:
        """正常系: データ投入後に解析が実行できる"""
        self._insert_test_data(client)
        resp = client.post("/api/v1/analyze", json={
            "device_id": "test_device",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "is_anomaly" in data
        assert "max_z_score" in data

    def test_error_no_data(self, client: TestClient) -> None:
        """異常系: データなしで404"""
        resp = client.post("/api/v1/analyze", json={
            "device_id": "nonexistent",
        })
        assert resp.status_code == 404


class TestStatusAPI:
    """ステータスAPIのテスト"""

    def test_normal_empty_status(self, client: TestClient) -> None:
        """正常系: データなしでも正常応答する"""
        resp = client.get("/api/v1/status/m5stick_01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_count"] == 0
        assert data["last_analysis"] is None
