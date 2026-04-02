"""
フィールドマッピング
フォーム要素のname・placeholder・labelから入力フィールドを推定し、
推定できない場合はOpenAI APIで判定する
"""

import logging
import os

log = logging.getLogger(__name__)

# フィールド推定ルール（キーワード → フィールド種別）
# 優先度の高いキーワードを先頭に配置
FIELD_RULES: dict[str, list[str]] = {
    "company": [
        "company", "corp", "corporation", "kaisha",
        "会社", "企業", "法人", "社名", "御社名", "貴社名", "法人名",
        "organization", "org", "団体", "所属",
    ],
    "name": [
        "your_name", "fullname", "full_name", "shimei",
        "氏名", "お名前", "担当", "ご担当", "ご担当者",
        "担当者名", "代表者", "ご氏名",
        "sei", "mei", "kana", "furigana", "yomi",
        "姓", "名", "フリガナ", "ふりがな",
        "name",  # 汎用的なので最後に配置（company_nameを先にマッチさせるため）
    ],
    "email": [
        "email", "e-mail", "mail_address", "contact_mail",
        "mail", "メール", "eメール", "メールアドレス",
        "ご連絡先メール", "mailaddress",
    ],
    "tel": [
        "tel", "tel1", "tel2", "phone", "fax",
        "daihyo", "denwa",
        "電話", "電話番号", "携帯", "ご連絡先",
        "連絡先電話",
    ],
    "message": [
        "message", "content", "body", "textarea",
        "inquiry", "toiawase", "naiyo", "shitsumon",
        "内容", "本文", "問い合わせ", "問合せ",
        "お問い合わせ", "お問い合わせ内容",
        "ご質問", "ご相談", "ご要望", "詳細",
        "comment", "備考", "メッセージ",
    ],
}


def map_fields(fields: list[dict[str, str]]) -> dict[str, dict]:
    """フォームフィールドをフィールド種別にマッピングする

    Returns:
        {フィールド種別: {field情報}} のdict
    """
    mapping: dict[str, dict] = {}

    # 1回目: 完全一致・部分一致の優先マッチ
    for field in fields:
        field_type = _match_by_keywords(field)
        if field_type and field_type not in mapping:
            mapping[field_type] = field

    # textareaはmessageとして扱う（未マッピングの場合）
    if "message" not in mapping:
        for field in fields:
            if field['tag'] == 'textarea':
                mapping["message"] = field
                break

    # 2回目: type属性ベースの推論（emailフィールドなど）
    _infer_from_input_type(fields, mapping)

    return mapping


def _match_by_keywords(field: dict[str, str]) -> str | None:
    """name・placeholder・label・idのキーワードからフィールド種別を推定する"""
    # 検索対象テキストを結合（小文字化）
    search_text = " ".join([
        field.get('name', ''),
        field.get('placeholder', ''),
        field.get('label', ''),
        field.get('id', ''),
    ]).lower()

    # company を先にチェック（"company_name" を name より先にマッチさせる）
    priority_order = ["company", "email", "tel", "message", "name"]
    for field_type in priority_order:
        keywords = FIELD_RULES[field_type]
        for kw in keywords:
            if kw in search_text:
                return field_type

    return None


def _infer_from_input_type(
    fields: list[dict[str, str]],
    mapping: dict[str, dict],
) -> None:
    """HTML input type属性からフィールド種別を推論する"""
    type_map = {
        'email': 'email',
        'tel': 'tel',
    }
    for field in fields:
        input_type = field.get('type', '')
        if input_type in type_map:
            mapped_type = type_map[input_type]
            if mapped_type not in mapping:
                mapping[mapped_type] = field


def enrich_with_openai(
    unmapped_fields: list[dict[str, str]],
) -> dict[str, dict]:
    """OpenAI APIで未マッピングフィールドを判定する"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.info("  OPENAI_API_KEY未設定 — AI判定スキップ")
        return {}

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except ImportError:
        log.warning("  openaiライブラリ未インストール — AI判定スキップ")
        return {}

    return _call_openai(client, unmapped_fields)


def _call_openai(client, unmapped_fields: list[dict[str, str]]) -> dict[str, dict]:
    """OpenAI APIを呼び出してフィールド種別を推定する"""
    field_descriptions = []
    for f in unmapped_fields:
        desc = (
            f"<{f['tag']} type=\"{f['type']}\" "
            f"name=\"{f['name']}\" "
            f"placeholder=\"{f['placeholder']}\" "
            f"id=\"{f['id']}\" "
            f"label=\"{f['label']}\" />"
        )
        field_descriptions.append(desc)

    prompt = (
        "以下のHTMLフォーム要素に入力すべき項目を判定してください。\n"
        "選択肢: 会社名/担当者名/メールアドレス/電話番号/本文/その他\n"
        "各要素について選択肢から1つ回答してください。\n"
        "回答形式: 「番号: company/name/email/tel/message/other」\n\n"
        "HTMLフォーム要素:\n"
        + "\n".join(f"{i}: {d}" for i, d in enumerate(field_descriptions))
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,
        )
        result_text = response.choices[0].message.content or ""
        log.info(f"  OpenAI判定結果: {result_text.strip()}")
        return _parse_openai_response(result_text, unmapped_fields)
    except Exception as e:
        log.warning(f"  OpenAI API呼び出し失敗: {e}")
        return {}


def _parse_openai_response(
    response_text: str,
    unmapped_fields: list[dict[str, str]],
) -> dict[str, dict]:
    """OpenAI APIの応答をパースしてマッピングに変換する"""
    mapping: dict[str, dict] = {}
    valid_types = {"company", "name", "email", "tel", "message"}

    # 日本語→英語の変換マップ
    ja_to_en = {
        "会社名": "company", "担当者名": "name",
        "メールアドレス": "email", "電話番号": "tel",
        "本文": "message", "その他": "other",
    }

    for line in response_text.strip().split('\n'):
        # 「0: company」「0: 会社名」両方に対応
        parts = line.split(':', 1)
        if len(parts) < 2:
            continue
        try:
            idx = int(parts[0].strip())
            raw_type = parts[1].strip().lower()
            # 日本語の場合は変換
            field_type = ja_to_en.get(parts[1].strip(), raw_type)
            if field_type in valid_types and idx < len(unmapped_fields):
                if field_type not in mapping:
                    mapping[field_type] = unmapped_fields[idx]
        except (ValueError, IndexError):
            continue

    return mapping


def get_full_mapping(fields: list[dict[str, str]]) -> dict[str, dict]:
    """キーワードマッチ＋OpenAI APIで完全なマッピングを構築する"""
    # キーワードマッチ（強化版）
    mapping = map_fields(fields)
    mapped_names = {v.get('name') for v in mapping.values()}

    # 未マッピングのフィールドを抽出
    unmapped = [f for f in fields if f.get('name') not in mapped_names]

    # 必須項目が欠けている場合のみOpenAI APIを使用
    required = {"company", "name", "email", "message"}
    missing = required - set(mapping.keys())

    if unmapped and missing:
        ai_mapping = enrich_with_openai(unmapped)
        for key, value in ai_mapping.items():
            if key not in mapping:
                mapping[key] = value

    return mapping
