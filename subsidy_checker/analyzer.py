"""助成金情報抽出・判定ロジックモジュール。"""

import logging
import re
from typing import Optional

from config import EXCLUDE_KEYWORDS, TARGET_WORK_KEYWORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def extract_subsidy_info(text: str, url: str) -> dict[str, str]:
    """ページテキストから助成金の7項目を抽出する。

    Args:
        text: ページのテキスト内容
        url: ページのURL

    Returns:
        抽出された7項目の辞書
    """
    info: dict[str, str] = {
        "助成金名": _extract_title(text),
        "金額補助率": _extract_amount(text),
        "対象者": _extract_target_person(text),
        "対象工事": _extract_target_work(text),
        "申請期間": _extract_period(text),
        "問い合わせ先": _extract_contact(text),
        "助成金URL": url,
    }
    return info


def _extract_title(text: str) -> str:
    """助成金名を抽出する。先頭部分のタイトルらしい行を取得。"""
    lines = text.strip().split("\n")
    for line in lines[:10]:
        line = line.strip()
        # 助成金・補助金を含む行をタイトルとみなす
        if any(kw in line for kw in ["助成", "補助", "支援"]):
            if 5 <= len(line) <= 80:
                return line
    return "不明"


def _extract_amount(text: str) -> str:
    """金額・補助率を抽出する。"""
    patterns = [
        r"補助[率額][\s：:]*(.{5,50})",
        r"助成[率額][\s：:]*(.{5,50})",
        r"上限[\s：:]*(.{5,40})",
        r"([\d,]+万?円[まで以内/～]*[\d,]*万?円?)",
        r"(\d+[/／]\d+以内)",
        r"(対象経費の\d+分の\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:60]
    return "不明"


def _extract_target_person(text: str) -> str:
    """対象者を抽出する。"""
    patterns = [
        r"対象者[\s：:]*(.{5,80})",
        r"対象となる[方人][\s：:]*(.{5,80})",
        r"申請できる[方人][\s：:]*(.{5,80})",
        r"補助対象者[\s：:]*(.{5,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:80]
    return "不明"


def _extract_target_work(text: str) -> str:
    """対象工事を抽出する。"""
    patterns = [
        r"対象工事[\s：:]*(.{5,100})",
        r"対象となる工事[\s：:]*(.{5,100})",
        r"補助対象[\s：:]*(.{5,100})",
        r"対象事業[\s：:]*(.{5,100})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:100]
    return "不明"


def _extract_period(text: str) -> str:
    """申請期間を抽出する。"""
    patterns = [
        r"申請期[間限][\s：:]*(.{5,60})",
        r"受付期間[\s：:]*(.{5,60})",
        r"募集期間[\s：:]*(.{5,60})",
        r"(令和\d+年\d+月\d+日[～〜からまで]+.{5,40})",
        r"(\d{4}年\d{1,2}月\d{1,2}日[～〜からまで]+.{5,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:60]
    return "不明"


def _extract_contact(text: str) -> str:
    """問い合わせ先を抽出する。"""
    patterns = [
        r"問[いい]合わせ[先]*[\s：:]*(.{5,80})",
        r"お問[いい]合[わせ]+[\s：:]*(.{5,80})",
        r"担当[課部][\s：:]*(.{5,60})",
        r"連絡先[\s：:]*(.{5,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()[:80]
    return "不明"


def judge_subsidy(info: dict[str, str]) -> tuple[str, str, str]:
    """助成金が対象かどうかを判定する。

    Args:
        info: extract_subsidy_infoで取得した7項目

    Returns:
        (判定結果, 信頼度, メモ) のタプル
        判定結果: "対象" / "対象外" / "要確認"
        信頼度: "高" / "中" / "低"
    """
    target_work = info.get("対象工事", "不明")
    title = info.get("助成金名", "不明")
    combined_text = f"{title} {target_work}"

    # 除外判定
    for kw in EXCLUDE_KEYWORDS:
        if kw in combined_text:
            return "対象外", "高", f"除外キーワード「{kw}」に該当"

    # 対象工事キーワードの一致チェック
    matched_keywords = [
        kw for kw in TARGET_WORK_KEYWORDS if kw in combined_text
    ]

    if matched_keywords:
        # 賃貸目的の改修は対象に含める
        if "賃貸" in combined_text:
            return "対象", "中", f"賃貸改修。一致: {', '.join(matched_keywords)}"
        return "対象", "高", f"一致: {', '.join(matched_keywords)}"

    # 情報不足の場合
    unknown_count = sum(
        1 for v in info.values() if v == "不明"
    )
    if unknown_count >= 4:
        return "要確認", "低", "抽出情報が不足。手動確認を推奨"

    if target_work == "不明":
        return "要確認", "低", "対象工事の情報が取得できず"

    return "対象外", "中", "対象工事キーワードに一致せず"
