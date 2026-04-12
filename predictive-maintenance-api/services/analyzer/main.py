"""
Service 2: 異常検知API

蓄積した振動データに対してFFT+エンベロープ解析を実行し
異常スコアと判定結果を返す
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException

from services.analyzer.engine import analyze
from shared.config import ANALYZER_PORT, NOTIFIER_URL
from shared.database import (
    fetch_vibration,
    get_device_data_count,
    get_last_received,
    get_latest_analysis,
    init_db,
    save_analysis_result,
)
from shared.models import AnalyzeRequest, AnalyzeResponse, DeviceStatus

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
    logger.info("異常検知API 起動完了")
    yield


app = FastAPI(
    title="振動異常検知API",
    description="蓄積された振動データをFFT+エンベロープ解析し異常判定するサービス",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post(
    "/api/v1/analyze",
    response_model=AnalyzeResponse,
    summary="異常検知を実行",
    description="指定デバイス・期間の振動データを解析し異常判定する",
)
async def run_analysis(req: AnalyzeRequest) -> AnalyzeResponse:
    """異常検知を実行する

    - **device_id**: 解析対象デバイス
    - **start / end**: 解析期間（省略時は全データ）
    """
    # DBから振動データ取得
    rows = fetch_vibration(req.device_id, req.start, req.end)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"デバイス {req.device_id} のデータが見つかりません",
        )

    # Z軸データを配列化して解析
    z_values = np.array([r["z"] for r in rows])

    try:
        result = analyze(z_values)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    analyzed_at = datetime.now()
    result["device_id"] = req.device_id
    result["analyzed_at"] = analyzed_at.isoformat()

    # 結果をDB保存
    save_analysis_result(result)

    # 異常検出時はnotifierに通知依頼
    if result["is_anomaly"]:
        await _notify_anomaly(req.device_id, result)

    return AnalyzeResponse(
        device_id=req.device_id,
        is_anomaly=result["is_anomaly"],
        max_z_score=result["max_z_score"],
        mean_rms=result["mean_rms"],
        peak_frequency_hz=result["peak_frequency_hz"],
        envelope_peak_hz=result["envelope_peak_hz"],
        threshold=result["threshold"],
        sample_count=result["sample_count"],
        analyzed_at=analyzed_at,
    )


async def _notify_anomaly(device_id: str, result: dict) -> None:
    """notifierサービスに異常通知を送る"""
    msg = (
        f":warning: *異常検出*\n"
        f"デバイス: `{device_id}`\n"
        f"最大Zスコア: `{result['max_z_score']:.2f}` "
        f"(閾値: {result['threshold']})\n"
        f"RMS: `{result['mean_rms']:.4f} g` / "
        f"ピーク周波数: `{result['peak_frequency_hz']:.1f} Hz`"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{NOTIFIER_URL}/api/v1/notify",
                json={
                    "device_id": device_id,
                    "message": msg,
                    "color": "danger",
                },
            )
        logger.info("notifierへ通知送信完了")
    except Exception as e:
        # 通知失敗しても解析結果は返す
        logger.warning(f"notifier通知失敗（解析は正常完了）: {e}")


@app.get(
    "/api/v1/status/{device_id}",
    response_model=DeviceStatus,
    summary="デバイスの最新ステータス",
    description="最新の異常判定結果とデータ件数を返す",
)
async def get_status(device_id: str) -> DeviceStatus:
    """デバイスの最新ステータスを取得する"""
    latest = get_latest_analysis(device_id)
    count = get_device_data_count(device_id)
    last_recv = get_last_received(device_id)

    last_analysis = None
    if latest:
        last_analysis = AnalyzeResponse(
            device_id=device_id,
            is_anomaly=bool(latest["is_anomaly"]),
            max_z_score=latest["max_z_score"],
            mean_rms=latest["mean_rms"],
            peak_frequency_hz=latest["peak_frequency_hz"],
            envelope_peak_hz=latest["envelope_peak_hz"],
            threshold=latest["threshold"],
            sample_count=latest["sample_count"],
            analyzed_at=datetime.fromisoformat(latest["analyzed_at"]),
        )

    return DeviceStatus(
        device_id=device_id,
        last_analysis=last_analysis,
        data_count=count,
        last_received=(
            datetime.fromisoformat(last_recv) if last_recv else None
        ),
    )


@app.get("/health", summary="ヘルスチェック")
async def health() -> dict:
    """サービスの稼働状態を返す"""
    return {"status": "ok", "service": "analyzer"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=ANALYZER_PORT)
