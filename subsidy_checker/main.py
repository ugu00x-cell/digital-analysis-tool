"""補助金調査自動化ツール メイン処理モジュール。"""

import logging
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from analyzer import extract_subsidy_info, judge_subsidy
from config import OUTPUT_COLUMNS
from scraper import (
    check_year_validity,
    extract_page_text,
    find_subsidy_links,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def load_csv(filepath: str) -> pd.DataFrame:
    """入力CSVを読み込む。

    Args:
        filepath: CSVファイルパス

    Returns:
        読み込んだDataFrame

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: 必須列が不足している場合
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {filepath}")

    # エンコーディング自動判定（Shift-JIS対応）
    for enc in ["utf-8", "cp932", "shift_jis"]:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSVの文字コードを判定できませんでした")

    required = ["都道府県", "市区町村", "市区町村HP URL"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"必須列が不足: {missing}")

    logger.info("CSV読み込み完了: %d 行", len(df))
    return df


def process_row(row: pd.Series) -> dict[str, str]:
    """1行分の処理を実行する。

    Args:
        row: CSVの1行（Series）

    Returns:
        追加列の辞書（7項目＋判定結果＋信頼度＋メモ）
    """
    municipality = f"{row.get('都道府県', '')} {row.get('市区町村', '')}"
    hp_url = str(row.get("市区町村HP URL", "")).strip()
    prev_url = str(row.get("昨年助成金URL", "")).strip()
    prev_count = row.get("昨年助成金数", 0)

    # 結果の初期値
    result = {col: "" for col in OUTPUT_COLUMNS}
    logger.info("処理開始: %s", municipality)

    # --- 昨年URLがある場合：有効性チェック ---
    if prev_url and prev_url != "nan" and prev_url != "":
        validity = check_year_validity(prev_url)
        if validity == "期限切れ":
            result["メモ"] = "昨年助成金は期限切れ。新規検索を実施"
            logger.info("%s: 昨年助成金は期限切れ", municipality)
        elif validity == "有効":
            # 有効ならそのページから情報抽出
            text = extract_page_text(prev_url)
            if text:
                info = extract_subsidy_info(text, prev_url)
                judgment, confidence, memo = judge_subsidy(info)
                result.update(info)
                result["判定結果"] = judgment
                result["信頼度"] = confidence
                result["メモ"] = f"昨年URL有効。{memo}"
                return result
        elif validity == "取得失敗":
            result["メモ"] = "昨年助成金URLの取得に失敗"
            logger.warning("%s: 昨年URL取得失敗", municipality)

    # --- 市区町村HPから新規検索 ---
    if not hp_url or hp_url == "nan":
        result["判定結果"] = "取得失敗"
        result["信頼度"] = "低"
        result["メモ"] = "市区町村HP URLが未設定"
        return result

    links = find_subsidy_links(hp_url)
    if not links:
        result["判定結果"] = "フォームなし"
        result["信頼度"] = "低"
        result["メモ"] = "助成金関連ページが見つからず"
        return result

    # 見つかったリンクから最適なものを選択
    best_result = _evaluate_links(links)
    if best_result:
        result.update(best_result)
    else:
        result["判定結果"] = "要確認"
        result["信頼度"] = "低"
        result["メモ"] = f"{len(links)}件のリンクを発見したが対象工事に該当せず"

    return result


def _evaluate_links(links: list[dict[str, str]]) -> Optional[dict[str, str]]:
    """発見したリンクを評価し、最も有望な助成金情報を返す。

    Args:
        links: find_subsidy_linksの結果

    Returns:
        最適な結果の辞書。該当なしの場合はNone
    """
    best: Optional[dict[str, str]] = None
    best_score = -1

    for link in links[:15]:  # 最大15件まで評価
        text = extract_page_text(link["url"])
        if text is None:
            continue

        info = extract_subsidy_info(text, link["url"])
        judgment, confidence, memo = judge_subsidy(info)

        # スコアリング：対象＞要確認＞対象外
        score = {"対象": 3, "要確認": 1, "対象外": 0}.get(judgment, 0)
        conf_bonus = {"高": 2, "中": 1, "低": 0}.get(confidence, 0)
        total_score = score + conf_bonus

        if total_score > best_score:
            best_score = total_score
            best = {**info, "判定結果": judgment, "信頼度": confidence, "メモ": memo}

    return best


def run(input_csv: str, output_csv: str) -> None:
    """メイン処理を実行する。

    Args:
        input_csv: 入力CSVパス
        output_csv: 出力CSVパス
    """
    df = load_csv(input_csv)

    # 出力列を追加
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    total = len(df)
    for idx, row in df.iterrows():
        logger.info("=== %d / %d ===", idx + 1, total)
        try:
            result = process_row(row)
            for col, val in result.items():
                df.at[idx, col] = val
        except Exception as e:
            logger.error("行 %d でエラー: %s", idx + 1, e)
            df.at[idx, "判定結果"] = "取得失敗"
            df.at[idx, "メモ"] = f"処理エラー: {str(e)[:50]}"

        # 途中経過を保存（中断対策）
        if (idx + 1) % 10 == 0:
            df.to_csv(output_csv, index=False, encoding="utf-8-sig")
            logger.info("途中保存完了: %d / %d", idx + 1, total)

    # 最終保存
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    _print_summary(df)
    logger.info("完了: %s に出力しました", output_csv)


def _print_summary(df: pd.DataFrame) -> None:
    """処理結果のサマリーをログに出力する。

    Args:
        df: 処理済みDataFrame
    """
    if "判定結果" not in df.columns:
        return
    counts = df["判定結果"].value_counts()
    logger.info("--- 処理結果サマリー ---")
    for status, count in counts.items():
        logger.info("  %s: %d 件", status, count)
    logger.info("  合計: %d 件", len(df))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使い方: python main.py <入力CSV> [出力CSV]")
        print("例: python main.py input.csv result.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else "result.csv"
    run(input_file, output_file)
