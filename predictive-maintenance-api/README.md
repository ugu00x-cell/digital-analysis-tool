# Predictive Maintenance API

M5StickC Plus2で収集した振動データを受け取り、FFT + エンベロープ解析で異常検知し、Slack通知するマイクロサービスAPI。

## アーキテクチャ

```
M5StickC Plus2 ──POST──▶ [Collector :8001] ──SQLite──▶ [Analyzer :8002] ──▶ [Notifier :8003] ──▶ Slack
                          データ収集             異常検知                  通知
```

| サービス | ポート | 役割 |
|---|---|---|
| Collector | 8001 | M5StickCから振動データ(x,y,z)を受信しSQLiteに保存 |
| Analyzer | 8002 | 蓄積データに対してFFT+エンベロープ解析+Zスコア異常判定 |
| Notifier | 8003 | 異常検知時にSlack Webhookで通知 |

## セットアップ

### ローカル実行

```bash
pip install -r requirements.txt
cp .env.example .env  # 必要に応じて編集

# 各サービスを別ターミナルで起動
python services/collector/main.py   # :8001
python services/analyzer/main.py    # :8002
python services/notifier/main.py    # :8003
```

### Docker Compose

```bash
cp .env.example .env
docker-compose up --build
```

## API仕様 (Swagger UI)

起動後に以下のURLでSwagger UIを確認できます:

- Collector: http://localhost:8001/docs
- Analyzer:  http://localhost:8002/docs
- Notifier:  http://localhost:8003/docs

## curl例

### 1. 振動データ送信（1件）

```bash
curl -X POST http://localhost:8001/api/v1/vibration \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "m5stick_01",
    "timestamp": "2026-04-12T10:00:00",
    "x": 0.01,
    "y": -0.03,
    "z": 1.02
  }'
```

### 2. 振動データ一括送信

```bash
curl -X POST http://localhost:8001/api/v1/vibration/batch \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "m5stick_01",
    "samples": [
      {"device_id":"m5stick_01","timestamp":"2026-04-12T10:00:00","x":0.01,"y":-0.03,"z":1.02},
      {"device_id":"m5stick_01","timestamp":"2026-04-12T10:00:01","x":0.02,"y":-0.01,"z":0.98},
      {"device_id":"m5stick_01","timestamp":"2026-04-12T10:00:02","x":-0.01,"y":0.02,"z":1.05}
    ]
  }'
```

### 3. 異常検知実行

```bash
curl -X POST http://localhost:8002/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "m5stick_01"
  }'
```

### 4. 期間指定で異常検知

```bash
curl -X POST http://localhost:8002/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "m5stick_01",
    "start": "2026-04-12T10:00:00",
    "end": "2026-04-12T11:00:00"
  }'
```

### 5. デバイスステータス確認

```bash
curl http://localhost:8002/api/v1/status/m5stick_01
```

### 6. 手動Slack通知

```bash
curl -X POST http://localhost:8003/api/v1/notify \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "m5stick_01",
    "message": ":warning: テスト通知",
    "color": "warning"
  }'
```

### 7. ヘルスチェック

```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```

## テスト

```bash
cd predictive-maintenance-api
pytest tests/ -v
```

## 技術スタック

- Python 3.13 / FastAPI / uvicorn
- SQLite (WALモード)
- NumPy / SciPy (FFT・エンベロープ解析)
- httpx (サービス間通信)
- Docker / Docker Compose

## 解析ロジック

`analyze_vibration.py` の処理をAPI化:

1. **前処理**: 平均除去 + 5σクリッピング
2. **FFT**: ハニング窓適用 → ピーク周波数検出
3. **エンベロープ解析**: バンドパスフィルタ → ヒルベルト変換 → 包絡線FFT
4. **異常判定**: セグメントRMSのZスコアがしきい値(デフォルト3.0σ)を超えたら異常

## ライセンス

MIT
