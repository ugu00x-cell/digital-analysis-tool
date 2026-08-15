"""AI判定フォールバック - Google Gemini APIでフォーム要素を解析する

BS4パターンマッチで判定できなかった要素をAIで補完する。
"""

import json
import logging
from typing import Optional

import google.generativeai as genai
import streamlit as st

logger = logging.getLogger(__name__)

# Geminiモデル名
GEMINI_MODEL = "gemini-2.5-flash"

# AIへの判定プロンプト
SYSTEM_PROMPT = """あなたはHTMLフォーム解析の専門家です。
これは「お問い合わせフォーム（コンタクトフォーム）」かどうかを最初に判定し、
コンタクトフォームの場合のみ各入力要素の用途を判定してください。

【重要: コンタクトフォーム vs 検索フォームの判別】
以下の特徴があるフォームは「検索フォーム」なので is_contact_form を false にしてください:
- フォームのaction/class/id に "search" が含まれる
- 入力欄が1〜2個だけ（検索キーワード + 送信ボタン）
- textareaがない
- 要素のname/placeholder/aria-label に "search", "検索", "keyword", "query", "q" が含まれる
- role="search"

コンタクトフォームの特徴:
- textarea（メッセージ欄）がある
- email/tel/name等の複数の入力欄がある
- action/class/id に "contact", "inquiry", "mail", "form" が含まれる
- 必須項目が複数ある

【検索フォームの場合】
検索フォームと判定したら、fieldsは空配列にして is_contact_form: false を返してください。
その入力欄を message や name として誤判定してはいけません。

【フィールドタイプ判定ルール】
- company: 会社名・企業名・法人名
- last_name: 姓（名と分かれている場合）
- first_name: 名（姓と分かれている場合）
- name: 氏名（分割されていない場合）
- last_kana/first_kana: フリガナ（分割）
- kana: フリガナ（分割なし）
- email: メールアドレス
- phone: 電話番号
- postal: 郵便番号
- address: 住所
- subject: 件名・タイトル・用件
- message: 本文・お問い合わせ内容（textareaが該当することが多い）
- other: 上記に該当しない（選択肢・同意チェックボックス等）

以下のJSON形式で回答してください:
{
  "is_contact_form": true/false,
  "fields": [
    {
      "name": "要素のname属性",
      "type": "company|last_name|first_name|last_kana|first_kana|name|kana|email|phone|postal|address|subject|message|other",
      "description": "この要素の用途"
    }
  ],
  "submit_selector": "送信ボタンのCSSセレクタ",
  "has_confirm_page": true/false
}

JSONのみを返してください。説明文は不要です。"""


def _get_api_key() -> str:
    """APIキーを取得する（session_state優先、.env フォールバック）"""
    import os
    key = st.session_state.get("gemini_api_key", "")
    if not key:
        key = os.environ.get("GEMINI_API_KEY", "")
    return key


def analyze_form_with_ai(form_html: str) -> Optional[dict]:
    """Gemini APIでフォームHTMLを解析する

    Args:
        form_html: form要素のHTML文字列

    Returns:
        解析結果辞書、失敗時はNone
    """
    api_key = _get_api_key()
    if not api_key:
        logger.info("Gemini APIキー未設定のためAI判定スキップ")
        return None

    # Gemini APIの初期化
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    logger.info("Gemini AI判定開始（HTML: %d文字）", len(form_html))

    # トークン節約: 長すぎるHTMLは切り詰め
    max_len = 8000
    if len(form_html) > max_len:
        form_html = form_html[:max_len] + "\n<!-- truncated -->"

    try:
        resp = model.generate_content(
            form_html,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )
        raw = resp.text or ""
        logger.info("Gemini応答取得（%d文字）", len(raw))
        result = _parse_response(raw)

        # 検索フォームと判定された場合はNoneを返す（誤判定防止）
        if result and result.get("is_contact_form") is False:
            logger.info("AI判定: 検索フォームのため解析結果を破棄")
            return None

        return result

    except Exception as e:
        logger.error("Gemini AI判定失敗: %s", e)
        return None


def _parse_response(raw: str) -> Optional[dict]:
    """AI応答テキストをJSONにパースする"""
    text = raw.strip()
    # コードブロック除去
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
        logger.warning("JSONパース失敗: %s", text[:200])
        return None


def merge_mappings(
    bs4_map: dict, ai_result: Optional[dict]
) -> dict:
    """BS4解析結果とAI判定をマージする

    Args:
        bs4_map: BS4による解析結果
        ai_result: AI判定結果（Noneならbs4_mapそのまま）

    Returns:
        マージ済みマッピング
    """
    merged = dict(bs4_map)

    if not ai_result or "fields" not in ai_result:
        return merged

    # BS4で未検出のフィールドをAI結果で補完
    for field in ai_result["fields"]:
        ftype = field.get("type", "other")
        if ftype != "other" and ftype not in merged:
            merged[ftype] = {
                "name": field.get("name", ""),
                "tag": "input",
                "type": "text",
                "source": "ai",
            }
            logger.info("AI補完: %s → %s", ftype, field["name"])

    # 送信ボタン・確認画面情報
    if "submit_selector" in ai_result:
        merged["_submit"] = ai_result["submit_selector"]
    if "has_confirm_page" in ai_result:
        merged["_confirm"] = ai_result["has_confirm_page"]

    return merged
