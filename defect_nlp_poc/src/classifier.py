"""Claude APIで初期不良を分類して defects_classified.csv に出力する。

- 10件ずつバッチ処理してAPI制限を回避
- JSON出力を強制するプロンプト設計
- 失敗したバッチは記録してスキップ
"""
import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from anthropic import Anthropic, APIError
from dotenv import load_dotenv

from labels import format_labels_for_prompt, label_keys

# ログ設定（CLAUDE.md指定フォーマット）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# モデルID（ユーザー指定）
MODEL_ID = "claude-opus-4-6"

# バッチサイズ
BATCH_SIZE = 10

# パス設定
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = BASE_DIR / "data" / "defects_raw.csv"
OUTPUT_PATH = BASE_DIR / "data" / "defects_classified.csv"

# 出力列（入力列 + 分類結果列）
OUTPUT_FIELDS = [
    "id", "date", "product_category", "defect_description", "true_label",
    "predicted_label", "confidence", "sub_category", "estimated_cause", "countermeasure",
]


def build_system_prompt() -> str:
    """分類タスク用のシステムプロンプトを生成する。"""
    return (
        "あなたは製造業（工作機械）の品質管理スペシャリストです。\n"
        "与えられた初期不良の一覧を、下記の分類体系に従って1件ずつ分類してください。\n\n"
        f"【分類体系】\n{format_labels_for_prompt()}\n\n"
        "各入力に対して以下のJSONを返してください。\n"
        "- predicted_label: 上記キーのいずれか1つ\n"
        "- confidence: high / medium / low\n"
        "- sub_category: より細かい分類（例: 外輪摩耗 / 内輪摩耗 等）\n"
        "- estimated_cause: 推定原因を1行で\n"
        "- countermeasure: 対策案を1行で\n\n"
        "応答は必ず以下のJSON形式のみとし、前後に説明文を付けないでください:\n"
        '{"results": [{"id": 1, "predicted_label": "...", "confidence": "...", '
        '"sub_category": "...", "estimated_cause": "...", "countermeasure": "..."}, ...]}'
    )


def build_user_message(batch: list[dict]) -> str:
    """バッチ分の入力をユーザーメッセージに整形する。

    Args:
        batch: id と defect_description を持つ辞書のリスト

    Returns:
        JSON形式の入力リスト文字列
    """
    inputs = [{"id": int(row["id"]), "defect_description": row["defect_description"]} for row in batch]
    return "以下の不良内容を分類してください:\n" + json.dumps(inputs, ensure_ascii=False)


def extract_json(text: str) -> Optional[dict]:
    """LLM応答から最初のJSONオブジェクトを取り出す。

    Args:
        text: LLMの応答テキスト

    Returns:
        パース済みの辞書。抽出・パース失敗時はNone
    """
    # ```json ... ``` のコードブロックを優先的に拾う
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def classify_batch(client: Anthropic, batch: list[dict]) -> list[dict]:
    """10件以下のバッチをClaude APIで分類する。

    Args:
        client: Anthropicクライアント
        batch: id/defect_description を持つ辞書のリスト

    Returns:
        idをキーに紐付く分類結果（predicted_label等）の辞書リスト。
        失敗時は空リスト
    """
    try:
        response = client.messages.create(
            model=MODEL_ID,
            max_tokens=2000,
            system=build_system_prompt(),
            messages=[{"role": "user", "content": build_user_message(batch)}],
        )
    except APIError as e:
        logger.warning("API呼び出しに失敗: %s（batch先頭id=%s）", e, batch[0]["id"])
        return []

    if not response.content:
        logger.warning("空の応答（batch先頭id=%s）", batch[0]["id"])
        return []

    parsed = extract_json(response.content[0].text)
    if not parsed or "results" not in parsed:
        logger.warning("JSONパース失敗（batch先頭id=%s）", batch[0]["id"])
        return []

    return parsed["results"]


def merge_predictions(rows: list[dict], predictions: list[dict]) -> list[dict]:
    """入力行とLLM予測結果をidで結合する。

    Args:
        rows: 入力CSVの行データ
        predictions: LLMが返した予測結果

    Returns:
        予測列を追加した行データ。予測が無い行は空文字で埋める
    """
    valid_labels = set(label_keys())
    pred_by_id = {int(p.get("id", -1)): p for p in predictions}

    merged: list[dict] = []
    for row in rows:
        pred = pred_by_id.get(int(row["id"]), {})
        predicted_label = pred.get("predicted_label", "")
        # 未知ラベルを弾いて空に寄せる
        if predicted_label and predicted_label not in valid_labels:
            logger.warning("未知ラベル '%s' を空にフォールバック（id=%s）", predicted_label, row["id"])
            predicted_label = ""
        merged.append({
            **row,
            "predicted_label": predicted_label,
            "confidence": pred.get("confidence", ""),
            "sub_category": pred.get("sub_category", ""),
            "estimated_cause": pred.get("estimated_cause", ""),
            "countermeasure": pred.get("countermeasure", ""),
        })
    return merged


def read_rows(input_path: Path) -> list[dict]:
    """入力CSVを読み込む。

    Raises:
        FileNotFoundError: 入力ファイルが存在しない場合
    """
    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")
    with input_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict], output_path: Path) -> None:
    """分類結果CSVを書き出す。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def get_client() -> Anthropic:
    """環境変数からAPIキーを読んでクライアントを返す。

    Raises:
        RuntimeError: ANTHROPIC_API_KEYが未設定の場合
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEYが設定されていません。.envを確認してください。")
    return Anthropic(api_key=api_key)


def main() -> None:
    """入力CSVを読み込み、バッチ分類してCSV出力する。"""
    load_dotenv()
    rows = read_rows(INPUT_PATH)
    logger.info("入力%d件を読み込みました", len(rows))

    client = get_client()
    all_predictions: list[dict] = []
    # 10件ずつバッチ化
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        logger.info("バッチ %d-%d を分類中", start + 1, start + len(batch))
        all_predictions.extend(classify_batch(client, batch))

    merged = merge_predictions(rows, all_predictions)
    write_rows(merged, OUTPUT_PATH)
    logger.info("分類完了: %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
