"""Claude API を使って初期不良テキストを分類するモジュール。"""
import logging
import os
from typing import Optional

from anthropic import Anthropic, APIError

from data import CATEGORIES, CATEGORY_DESCRIPTIONS

logger = logging.getLogger(__name__)

# モデルID（ユーザー指定）
MODEL_ID = "claude-sonnet-4-20250514"


def build_system_prompt() -> str:
    """分類タスク用のシステムプロンプトを生成する。

    Returns:
        カテゴリ一覧と説明を含むシステムプロンプト文字列
    """
    # カテゴリ名と説明を箇条書きで提示
    category_lines = [
        f"- {name}：{desc}"
        for name, desc in CATEGORY_DESCRIPTIONS.items()
    ]
    categories_block = "\n".join(category_lines)

    return (
        "あなたは製造業の品質管理の専門家です。\n"
        "与えられた初期不良の記述を、以下の5つのカテゴリのいずれか1つに分類してください。\n\n"
        f"{categories_block}\n\n"
        "出力は必ずカテゴリ名のみを返し、余計な説明や記号は一切含めないでください。\n"
        f"出力可能な文字列は次のいずれかです: {', '.join(CATEGORIES)}"
    )


def classify_defect(client: Anthropic, text: str) -> Optional[str]:
    """単一の不良テキストをClaude APIで分類する。

    Args:
        client: Anthropicクライアント
        text: 分類対象の不良記述テキスト

    Returns:
        分類結果のカテゴリ名。API失敗時や不正な応答時はNone
    """
    try:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=50,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": text}],
        )
    except APIError as e:
        # APIエラーは警告のみ出して呼び出し側に None を返す
        logger.warning("API呼び出しに失敗: %s（入力=%s）", e, text)
        return None

    # 応答テキストを取り出し、前後の空白・記号を除去
    if not response.content:
        logger.warning("空の応答を受信（入力=%s）", text)
        return None

    raw = response.content[0].text.strip()
    # カテゴリ名の揺らぎに対応：CATEGORIESのいずれかが含まれていれば採用
    for category in CATEGORIES:
        if category in raw:
            return category

    logger.warning("未知のカテゴリを応答: '%s'（入力=%s）", raw, text)
    return None


def get_client() -> Anthropic:
    """環境変数からAPIキーを読み込んでAnthropicクライアントを生成する。

    Returns:
        初期化済みのAnthropicクライアント

    Raises:
        RuntimeError: ANTHROPIC_API_KEY が設定されていない場合
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "環境変数 ANTHROPIC_API_KEY が設定されていません。"
            ".env ファイルまたはシェル環境で設定してください。"
        )
    return Anthropic(api_key=api_key)
