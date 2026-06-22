"""冷蔵庫献立提案Webアプリ - Flaskエントリポイント"""
import logging
import os

from flask import Flask, Response, render_template, request, stream_with_context
from dotenv import load_dotenv

from services.menu_generator import generate_menu_stream

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/")
def index() -> str:
    """トップページを返す"""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate() -> Response:
    """
    食材を受け取り、献立をSSEストリームで返す。

    Returns:
        text/event-stream レスポンス
    """
    ingredients: str = request.form.get("ingredients", "").strip()
    logger.info(f"リクエスト受信 | 食材入力: {ingredients[:100] if ingredients else '(空)'}")

    if not ingredients:
        return Response("data: エラー: 食材を入力してください\n\n", mimetype="text/event-stream")

    def event_stream() -> Response:
        """SSEイベントストリームを生成するジェネレータ"""
        try:
            for chunk in generate_menu_stream(ingredients):
                # SSE形式: "data: <テキスト>\n\n"
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except (ValueError, RuntimeError) as e:
            logger.error(f"ストリーム生成エラー: {e}")
            yield f"data: エラー: {e}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)
