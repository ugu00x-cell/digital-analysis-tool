"""
共通設定モジュール

環境変数から各種設定を読み込む
"""

import os
from pathlib import Path

# データベースパス
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get(
    "DB_PATH", str(BASE_DIR / "data" / "vibration.db"),
)

# サンプリング周波数（M5StickC Plus2のデフォルト）
SAMPLING_RATE = int(os.environ.get("SAMPLING_RATE", "500"))

# 異常検知しきい値（Zスコア）
ANOMALY_THRESHOLD = float(os.environ.get("ANOMALY_THRESHOLD", "3.0"))

# セグメント長（秒）
SEGMENT_SEC = float(os.environ.get("SEGMENT_SEC", "1.0"))
SEGMENT_LEN = int(SAMPLING_RATE * SEGMENT_SEC)

# 各サービスのポート
COLLECTOR_PORT = int(os.environ.get("COLLECTOR_PORT", "8001"))
ANALYZER_PORT = int(os.environ.get("ANALYZER_PORT", "8002"))
NOTIFIER_PORT = int(os.environ.get("NOTIFIER_PORT", "8003"))

# サービス間通信URL
NOTIFIER_URL = os.environ.get(
    "NOTIFIER_URL", f"http://localhost:{NOTIFIER_PORT}",
)

# Slack Webhook URL
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
