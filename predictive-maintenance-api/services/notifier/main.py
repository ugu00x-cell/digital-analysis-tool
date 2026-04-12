"""
Service 3: Slack通知API

異常検知結果をSlack Webhook経由で通知する
analyze_vibration.pyのSlack通知処理を流用
"""

import json
import logging
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException

from shared.config import NOTIFIER_PORT, SLACK_WEBHOOK_URL
from shared.models import NotifyRequest, NotifyResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Slack通知API",
    description="異常検知結果をSlack Webhookで通知するサービス",
    version="1.0.0",
)


def _send_slack(
    text: str,
    color: str = "good",
    webhook_url: str = "",
) -> bool:
    """Slackにメッセージを送信する

    Args:
        text: 送信するメッセージ本文
        color: 添付カラー (good/warning/danger)
        webhook_url: Webhook URL

    Returns:
        送信成功ならTrue
    """
    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL未設定 - 通知スキップ")
        return False

    payload = {
        "attachments": [
            {
                "color": color,
                "text": text,
                "mrkdwn_in": ["text"],
            }
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack通知 送信成功")
        return True
    except Exception as e:
        logger.error(f"Slack送信失敗: {e}")
        raise


@app.post(
    "/api/v1/notify",
    response_model=NotifyResponse,
    summary="Slack通知を送信",
    description="指定メッセージをSlack Webhookで送信する",
)
async def notify(req: NotifyRequest) -> NotifyResponse:
    """Slack通知を送信する

    - **device_id**: 通知元デバイス
    - **message**: 通知メッセージ（Slack mrkdwn形式対応）
    - **color**: 添付バーの色 (good=緑 / warning=黄 / danger=赤)
    """
    if not SLACK_WEBHOOK_URL:
        logger.warning(
            f"Webhook未設定のため通知をログ出力のみ: "
            f"{req.device_id} - {req.message}"
        )
        return NotifyResponse(
            status="skipped",
            message="SLACK_WEBHOOK_URL未設定のためスキップ",
        )

    try:
        _send_slack(req.message, req.color, SLACK_WEBHOOK_URL)
        return NotifyResponse(status="sent", message="Slack通知完了")
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Slack送信失敗: {e}",
        )


@app.get("/health", summary="ヘルスチェック")
async def health() -> dict:
    """サービスの稼働状態とWebhook設定状態を返す"""
    return {
        "status": "ok",
        "service": "notifier",
        "webhook_configured": bool(SLACK_WEBHOOK_URL),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=NOTIFIER_PORT)
