"""AI判定エンジン - OpenAI APIでフォーム要素を解析する

BeautifulSoupで判定できなかった要素をAIで補完する。
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger(__name__)

# AIへのシステムプロンプト
SYSTEM_PROMPT = """あなたはHTMLフォーム解析の専門家です。
フォームのHTML構造を分析し、各入力要素に何を入力すべきか判定してください。

以下のJSON形式で回答してください:
{
  "fields": [
    {
      "name": "要素のname属性",
      "type": "company|name|email|phone|subject|message|other",
      "description": "この要素の用途の説明"
    }
  ],
  "submit_selector": "送信ボタンのCSSセレクタ",
  "has_confirm_page": true/false
}

JSONのみを返してください。説明文は不要です。"""


def _get_client() -> OpenAI:
    """OpenAIクライアントを生成する

    Returns:
        OpenAI APIクライアント

    Raises:
        ValueError: APIキー未設定時
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEYが設定されていません。"
            ".envファイルに設定してください。"
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def analyze_form_with_ai(form_html: str) -> Optional[dict]:
    """OpenAI APIでフォームHTMLを解析する

    Args:
        form_html: form要素のHTML文字列

    Returns:
        解析結果のJSON辞書、失敗時はNone
    """
    client = _get_client()
    logger.info("AI判定開始（HTML: %d文字）", len(form_html))

    # HTMLが長すぎる場合は切り詰め（トークン節約）
    max_len = 8000
    if len(form_html) > max_len:
        form_html = form_html[:max_len] + "\n<!-- truncated -->"

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": form_html},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content or ""
        logger.info("AI応答取得（%d文字）", len(raw))
        return _parse_ai_response(raw)

    except Exception as e:
        logger.error("AI判定失敗: %s", e)
        return None


def _parse_ai_response(raw: str) -> Optional[dict]:
    """AI応答のテキストをJSONにパースする

    Args:
        raw: AIの生応答テキスト

    Returns:
        パース済み辞書、失敗時はNone
    """
    # コードブロック除去
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1:]
        if text.endswith("```"):
            text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("AI応答のJSONパース失敗: %s", text[:200])
        return None


def merge_mappings(
    bs4_mapping: dict, ai_result: Optional[dict]
) -> dict:
    """BS4の解析結果とAI判定結果をマージする

    Args:
        bs4_mapping: BeautifulSoupによる解析結果
        ai_result: AI判定結果（Noneの場合はBS4のみ使用）

    Returns:
        マージ済みのフィールドマッピング
    """
    merged = dict(bs4_mapping)

    if not ai_result or "fields" not in ai_result:
        return merged

    # BS4で未検出のフィールドをAI結果で補完
    for field in ai_result["fields"]:
        field_type = field.get("type", "other")
        if field_type != "other" and field_type not in merged:
            merged[field_type] = {
                "name": field.get("name", ""),
                "tag": "input",
                "type": "text",
                "source": "ai",
            }
            logger.info("AI補完: %s → %s", field_type, field["name"])

    # 送信ボタンのセレクタ情報を追加
    if "submit_selector" in ai_result:
        merged["_submit"] = ai_result["submit_selector"]
    if "has_confirm_page" in ai_result:
        merged["_confirm"] = ai_result["has_confirm_page"]

    return merged
