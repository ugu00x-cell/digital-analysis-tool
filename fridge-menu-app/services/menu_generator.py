"""Claude APIを使って冷蔵庫の余り物から献立を生成するサービス"""
import logging
from typing import Generator

import anthropic

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = """あなたは料理の専門家です。
ユーザーが持っている食材をもとに、美味しくて実現可能な献立を提案してください。

以下の形式で回答してください：
1. 料理名（例：親子丼、野菜炒め など）
2. 使用する食材
3. 簡単な調理手順（3〜5ステップ）
4. 調理時間の目安

複数の献立案（2〜3案）を提案し、難易度も添えてください。"""


def generate_menu_stream(ingredients: str) -> Generator[str, None, None]:
    """
    食材リストをもとに献立をストリーミングで生成する。

    Args:
        ingredients: ユーザーが入力した食材（カンマ区切りや自由記述）

    Yields:
        Claude APIからのテキストチャンク
    """
    if not ingredients or not ingredients.strip():
        raise ValueError("食材が入力されていません")

    logger.info(f"献立生成開始 | 食材: {ingredients[:100]}")

    client = anthropic.Anthropic()

    user_message = f"冷蔵庫にある食材：{ingredients}\n\nこれらの食材で作れる献立を提案してください。"

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=2000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                yield text

        logger.info("献立生成完了")

    except anthropic.APIError as e:
        logger.error(f"Claude API エラー: {e}")
        raise RuntimeError(f"献立の生成に失敗しました: {e}") from e
