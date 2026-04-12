"""
Service 3: Slack通知APIのテスト

正常系2・異常系2・境界値1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from services.notifier.main import app


@pytest.fixture
def client() -> TestClient:
    """テスト用クライアント"""
    return TestClient(app)


class TestNotifyAPI:
    """通知APIのテスト"""

    def test_normal_skip_without_webhook(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """正常系: Webhook未設定時はskippedで応答する"""
        monkeypatch.setattr(
            "services.notifier.main.SLACK_WEBHOOK_URL", "",
        )
        resp = client.post("/api/v1/notify", json={
            "device_id": "m5stick_01",
            "message": "テスト通知",
            "color": "good",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "skipped"

    def test_normal_valid_request_format(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """正常系: リクエスト形式が正しければ処理される"""
        monkeypatch.setattr(
            "services.notifier.main.SLACK_WEBHOOK_URL", "",
        )
        resp = client.post("/api/v1/notify", json={
            "device_id": "m5stick_01",
            "message": ":warning: 異常検出",
            "color": "danger",
        })
        assert resp.status_code == 200

    def test_error_missing_message(self, client: TestClient) -> None:
        """異常系: message欠落で422"""
        resp = client.post("/api/v1/notify", json={
            "device_id": "m5stick_01",
        })
        assert resp.status_code == 422

    def test_error_missing_device_id(self, client: TestClient) -> None:
        """異常系: device_id欠落で422"""
        resp = client.post("/api/v1/notify", json={
            "message": "テスト",
        })
        assert resp.status_code == 422

    def test_boundary_empty_message(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """境界値: 空文字メッセージでも処理される"""
        monkeypatch.setattr(
            "services.notifier.main.SLACK_WEBHOOK_URL", "",
        )
        resp = client.post("/api/v1/notify", json={
            "device_id": "m5stick_01",
            "message": "",
            "color": "good",
        })
        assert resp.status_code == 200


class TestHealth:
    """ヘルスチェックのテスト"""

    def test_health(self, client: TestClient) -> None:
        """正常系: ヘルスチェックが応答する"""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "notifier"
