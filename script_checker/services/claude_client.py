"""Claude API クライアント - 台本チェック・修正用"""

import json
import logging
import os

import anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Claude APIの設定
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


def _get_client() -> anthropic.Anthropic:
    """Anthropicクライアントを生成する

    Returns:
        Anthropic APIクライアント

    Raises:
        ValueError: APIキーが未設定の場合
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY が設定されていません。"
            ".envファイルまたは環境変数に設定してください。"
        )
    return anthropic.Anthropic(api_key=api_key)


def call_claude(system_prompt: str, user_prompt: str) -> str:
    """Claude APIを呼び出してテキスト応答を取得する

    Args:
        system_prompt: システムプロンプト（役割指示）
        user_prompt: ユーザープロンプト（台本テキスト等）

    Returns:
        Claudeの応答テキスト

    Raises:
        anthropic.APIError: API呼び出し失敗時
    """
    client = _get_client()
    logger.info("Claude API呼び出し開始（モデル: %s）", MODEL)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # テキストブロックから応答を取得
        result = response.content[0].text
        logger.info(
            "Claude API応答取得（%d文字, tokens: %d/%d）",
            len(result),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return result

    except anthropic.APIError as e:
        logger.error("Claude API呼び出し失敗: %s", e)
        raise


def call_claude_json(system_prompt: str, user_prompt: str) -> dict:
    """Claude APIを呼び出してJSON形式の応答を取得する

    Args:
        system_prompt: システムプロンプト
        user_prompt: ユーザープロンプト

    Returns:
        パースされたJSONオブジェクト

    Raises:
        json.JSONDecodeError: JSON解析失敗時
        anthropic.APIError: API呼び出し失敗時
    """
    # JSONで返すよう指示を追加
    json_instruction = (
        "\n\n【重要】応答は必ず有効なJSONのみで返してください。"
        "マークダウンのコードブロック(```)は使わないでください。"
    )
    raw = call_claude(
        system_prompt + json_instruction, user_prompt
    )

    # コードブロックが含まれていたら除去
    cleaned = _strip_code_fence(raw)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("JSON解析失敗。応答の先頭200文字: %s", raw[:200])
        raise


def _strip_code_fence(text: str) -> str:
    """マークダウンのコードブロック記法を除去する

    Args:
        text: 生のClaude応答テキスト

    Returns:
        コードブロック記法を除去したテキスト
    """
    text = text.strip()
    if text.startswith("```"):
        # 最初の行（```json等）を除去
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        # 末尾の```を除去
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()
