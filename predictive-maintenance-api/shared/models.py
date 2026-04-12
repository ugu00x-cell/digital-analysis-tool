"""
共通Pydanticモデル

全サービスで共有するリクエスト/レスポンス型
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── データ収集 ──────────────────────────────────────────────

class VibrationData(BaseModel):
    """M5StickCから送信される振動データ1サンプル"""

    device_id: str = Field(..., json_schema_extra={"example": "m5stick_01"}, description="デバイスID")
    timestamp: datetime = Field(..., description="計測時刻（ISO 8601）")
    x: float = Field(..., description="X軸加速度 [g]")
    y: float = Field(..., description="Y軸加速度 [g]")
    z: float = Field(..., description="Z軸加速度 [g]")


class VibrationBatch(BaseModel):
    """振動データの一括送信用"""

    device_id: str = Field(..., json_schema_extra={"example": "m5stick_01"})
    samples: list[VibrationData] = Field(..., description="振動データ配列")


class CollectResponse(BaseModel):
    """データ収集APIのレスポンス"""

    status: str = Field(..., json_schema_extra={"example": "ok"})
    device_id: str
    saved_count: int = Field(..., description="保存件数")


# ── 異常検知 ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """異常検知リクエスト"""

    device_id: str = Field(..., json_schema_extra={"example": "m5stick_01"})
    start: datetime | None = Field(None, description="解析開始時刻")
    end: datetime | None = Field(None, description="解析終了時刻")


class AnalyzeResponse(BaseModel):
    """異常検知レスポンス"""

    device_id: str
    is_anomaly: bool = Field(..., description="異常判定")
    max_z_score: float = Field(..., description="最大Zスコア")
    mean_rms: float = Field(..., description="RMS平均値 [g]")
    peak_frequency_hz: float = Field(..., description="FFTピーク周波数 [Hz]")
    envelope_peak_hz: float = Field(..., description="エンベロープピーク周波数 [Hz]")
    threshold: float = Field(..., description="判定しきい値")
    sample_count: int = Field(..., description="解析サンプル数")
    analyzed_at: datetime = Field(..., description="解析実行時刻")


class DeviceStatus(BaseModel):
    """デバイスの最新ステータス"""

    device_id: str
    last_analysis: AnalyzeResponse | None = None
    data_count: int = Field(..., description="保存データ件数")
    last_received: datetime | None = Field(None, description="最終データ受信時刻")


# ── 通知 ──────────────────────────────────────────────────

class NotifyRequest(BaseModel):
    """Slack通知リクエスト"""

    device_id: str
    message: str = Field(..., description="通知メッセージ")
    color: str = Field("good", description="添付カラー (good/warning/danger)")


class NotifyResponse(BaseModel):
    """Slack通知レスポンス"""

    status: str = Field(..., json_schema_extra={"example": "sent"})
    message: str
