"""紙点検票OCRモックモジュール

紙の点検票をOCRした想定のテキストを模倣し、ノイズ込みで生成 → 前処理 → Document化
までを行う。実際のOCRエンジン（Tesseract/Azure等）への差し替えポイントを
明示するため、`ocr_extract_text` 関数を分離している。

処理内容:
    - ランダムな誤字を5%の確率で混入
    - 行の結合・分割を再現
    - excel_parser.py と同じ出力形式（List[Document]）に正規化

実行例:
    from src.ocr_mock import generate_paper_documents
    docs = generate_paper_documents(seed=0)
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass

from langchain_core.documents import Document

from src.excel_parser import fill_missing, load_synonyms, normalize_text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DEFAULT_TYPO_RATE = 0.05  # 誤字混入率（仕様書の5%）

# OCR誤認識でありがちな誤字マッピング（実OCRの傾向を簡易再現）
TYPO_TABLE: dict[str, str] = {
    "ベ": "へ", "゛": "", "ー": "一",
    "0": "O", "1": "l",
    "正": "圧", "常": "當",
    "軸": "輸", "油": "由",
}


@dataclass(frozen=True)
class PaperInspection:
    """紙点検票1枚分のグラウンドトゥルース。"""

    date: str
    machine_id: str
    inspector: str
    check_item: str
    result: str
    abnormality: str
    action_taken: str


# 紙点検票のサンプル（合成）。実運用ではPDF/画像から読み込む想定。
PAPER_RECORDS: list[PaperInspection] = [
    PaperInspection("2024-02-03", "MC003", "田中さん", "主軸",
                    "異常", "わずかな異音あり", "保全部門へ連絡"),
    PaperInspection("2024-02-15", "MC005", "佐藤さん", "油圧",
                    "異常", "圧力低下6.2MPa", "ポンプ点検依頼"),
    PaperInspection("2024-03-08", "MC001", "鈴木さん", "X軸精度",
                    "正常", "記録なし", "記録なし"),
    PaperInspection("2024-03-22", "MC008", "高橋さん", "切削油",
                    "異常", "濃度低下・濁り", "切削油交換"),
    PaperInspection("2024-04-10", "MC010", "山本さん", "Z軸精度",
                    "異常", "バックラッシュ0.04mm", "ボールネジ調整"),
    PaperInspection("2024-04-25", "MC002", "中村さん", "主軸",
                    "正常", "記録なし", "記録なし"),
    PaperInspection("2024-05-12", "MC007", "田中さん", "ATC",
                    "異常", "把持力やや低下", "把持力測定実施"),
    PaperInspection("2024-05-30", "MC006", "佐藤さん", "冷却水",
                    "異常", "温度上昇38度", "ファン清掃"),
    PaperInspection("2024-06-14", "MC004", "鈴木さん", "Y軸精度",
                    "正常", "記録なし", "記録なし"),
    PaperInspection("2024-06-28", "MC009", "高橋さん", "安全装置",
                    "異常", "扉スイッチ反応遅延", "スイッチ交換"),
]


def _serialize_paper(record: PaperInspection) -> str:
    """紙点検票をOCR前のクリーンなテキストに整形する（モック用）。

    Args:
        record: 紙点検票1枚分のデータ

    Returns:
        改行区切りのクリーンなテキスト
    """
    return (
        f"点検票\n"
        f"日付: {record.date}\n"
        f"設備: {record.machine_id}\n"
        f"点検者: {record.inspector}\n"
        f"点検項目: {record.check_item}\n"
        f"結果: {record.result}\n"
        f"異常: {record.abnormality}\n"
        f"処置: {record.action_taken}"
    )


def inject_typos(text: str, rate: float, rng: random.Random) -> str:
    """テキストにランダムな誤字を確率的に混入する。

    Args:
        text: 入力テキスト
        rate: 1文字あたりの誤字混入確率（0.0〜1.0）
        rng: 乱数生成器

    Returns:
        誤字混入後のテキスト

    Raises:
        ValueError: rate が範囲外の場合
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"rate は 0.0〜1.0 で指定してください: {rate}")
    chars: list[str] = []
    for ch in text:
        if rng.random() < rate and ch in TYPO_TABLE:
            chars.append(TYPO_TABLE[ch])
        else:
            chars.append(ch)
    return "".join(chars)


def disturb_linebreaks(text: str, rng: random.Random) -> str:
    """行の結合・分割をランダムに再現する。

    Args:
        text: 入力テキスト（改行区切り）
        rng: 乱数生成器

    Returns:
        行ズレ再現後のテキスト
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        roll = rng.random()
        if roll < 0.15 and i + 1 < len(lines):  # 15%で次行と結合
            out.append(line + lines[i + 1])
            i += 2
            continue
        if roll < 0.25 and len(line) > 6:  # 10%で途中で分割
            mid = len(line) // 2
            out.append(line[:mid])
            out.append(line[mid:])
        else:
            out.append(line)
        i += 1
    return "\n".join(out)


def ocr_extract_text(record: PaperInspection, rng: random.Random,
                     typo_rate: float = DEFAULT_TYPO_RATE) -> str:
    """OCRエンジンの出力を模倣する。

    実運用時はこの関数を Tesseract/Azure Document Intelligence 等に差し替える。

    Args:
        record: 紙点検票データ
        rng: 乱数生成器
        typo_rate: 誤字混入率

    Returns:
        ノイズ込みの「OCR出力テキスト」
    """
    clean = _serialize_paper(record)
    noisy = inject_typos(clean, typo_rate, rng)
    return disturb_linebreaks(noisy, rng)


def _rejoin_lines(noisy_text: str) -> dict[str, str]:
    """ノイズ入りテキストから「キー: 値」ペアを抽出する。

    行が分割・結合されていても、既知キー（日付/設備/点検者など）を起点に
    値を切り出すロバストなパターンマッチで吸収する。

    Args:
        noisy_text: 行ズレ再現済みのOCR出力テキスト

    Returns:
        {キー: 値} の辞書
    """
    flat = noisy_text.replace("\n", " ")
    keys = ["日付", "設備", "点検者", "点検項目", "結果", "異常", "処置"]
    pattern = "|".join(keys)
    fields: dict[str, str] = {}
    matches = list(re.finditer(rf"({pattern}):\s*", flat))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(flat)
        fields[m.group(1)] = flat[start:end].strip()
    return fields


def _to_document(fields: dict[str, str], synonyms: dict[str, list[str]]) -> Document:
    """抽出済みフィールドを excel_parser と同形式の Document に変換する。

    Args:
        fields: _rejoin_lines が返した辞書
        synonyms: 表記ゆれ辞書

    Returns:
        Document（page_content + metadata）
    """
    date_v = fill_missing(fields.get("日付"))
    machine = fill_missing(fields.get("設備"))
    text = (
        f"【紙点検票OCR】{date_v} "
        f"/ 設備：{machine} "
        f"/ 点検者：{fill_missing(fields.get('点検者'))}\n"
        f"点検項目：{fill_missing(fields.get('点検項目'))} "
        f"/ 結果：{fill_missing(fields.get('結果'))}\n"
        f"異常内容：{fill_missing(fields.get('異常'))} "
        f"/ 処置：{fill_missing(fields.get('処置'))}"
    )
    return Document(
        page_content=normalize_text(text, synonyms),
        metadata={"source": "紙点検票OCR", "machine_id": machine, "date": date_v},
    )


def generate_paper_documents(
    records: list[PaperInspection] | None = None,
    seed: int = 0,
    typo_rate: float = DEFAULT_TYPO_RATE,
) -> list[Document]:
    """紙点検票群をOCRモック経由で Document リストに変換する。

    Args:
        records: 紙点検票データ。None の場合は PAPER_RECORDS を使用。
        seed: 乱数シード（再現性確保）
        typo_rate: 誤字混入率

    Returns:
        Document のリスト（excel_parser.py と同形式）
    """
    rng = random.Random(seed)
    synonyms = load_synonyms()
    src = records if records is not None else PAPER_RECORDS
    docs: list[Document] = []
    for record in src:
        noisy = ocr_extract_text(record, rng, typo_rate)
        fields = _rejoin_lines(noisy)
        docs.append(_to_document(fields, synonyms))
    logger.info("紙点検票OCRモック: %d 件を Document に変換", len(docs))
    return docs


if __name__ == "__main__":
    documents = generate_paper_documents(seed=0)
    for d in documents[:2]:
        logger.info("---\n%s\nmeta=%s", d.page_content, d.metadata)
