"""
Service 1: データ収集API

M5StickC Plus2から振動データをJSON受信しSQLiteに保存する
"""

import logging
import sys
from pathlib import Path

# 共通モジュールのパスを追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException

from shared.config import COLLECTOR_PORT
from shared.database import (
    get_device_data_count,
    get_last_received,
    init_db,
    insert_vibration,
    insert_vibration_batch,
)
from shared.models import CollectResponse, VibrationBatch, VibrationData

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """サーバー起動時にDB初期化"""
    init_db()
    logger.info("データ収集API 起動完了")
    yield


app = FastAPI(
    title="振動データ収集API",
    description="M5StickC Plus2から振動データを受信し保存するサービス",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post(
    "/api/v1/vibration",
    response_model=CollectResponse,
    summary="振動データ1件を受信",
    description="M5StickCから送信された振動データ1サンプルを保存する",
)
async def receive_vibration(data: VibrationData) -> CollectResponse:
    """振動データ1件を受信して保存する

    - **device_id**: デバイス識別子
    - **timestamp**: 計測時刻（ISO 8601形式）
    - **x, y, z**: 3軸加速度 [g]
    """
    try:
        insert_vibration(
            data.device_id, data.timestamp,
            data.x, data.y, data.z,
        )
        logger.info(f"受信: {data.device_id} @ {data.timestamp}")
        return CollectResponse(
            status="ok", device_id=data.device_id, saved_count=1,
        )
    except Exception as e:
        logger.error(f"保存エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/v1/vibration/batch",
    response_model=CollectResponse,
    summary="振動データを一括受信",
    description="複数サンプルをまとめて保存する（M5StickCのバッファ送信用）",
)
async def receive_vibration_batch(
    batch: VibrationBatch,
) -> CollectResponse:
    """振動データを一括受信して保存する

    M5StickCが一定時間分のデータをバッファリングして
    まとめて送信するケースに対応する
    """
    try:
        records = [
            (s.device_id, s.timestamp, s.x, s.y, s.z)
            for s in batch.samples
        ]
        count = insert_vibration_batch(records)
        logger.info(f"一括受信: {batch.device_id} x {count}件")
        return CollectResponse(
            status="ok", device_id=batch.device_id, saved_count=count,
        )
    except Exception as e:
        logger.error(f"一括保存エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/devices/{device_id}/count",
    summary="デバイスのデータ件数を取得",
)
async def get_data_count(device_id: str) -> dict:
    """指定デバイスの保存データ件数と最終受信時刻を返す"""
    return {
        "device_id": device_id,
        "data_count": get_device_data_count(device_id),
        "last_received": get_last_received(device_id),
    }


@app.get("/health", summary="ヘルスチェック")
async def health() -> dict:
    """サービスの稼働状態を返す"""
    return {"status": "ok", "service": "collector"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=COLLECTOR_PORT)
