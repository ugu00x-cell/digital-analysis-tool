"""
ログ・レポート出力
処理結果をCSVに記録し、サマリーを表示する
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import (
    STATUS_SUCCESS, STATUS_PARTIAL, STATUS_NO_FORM,
    STATUS_CAPTCHA, STATUS_TIMEOUT, STATUS_ERROR,
)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# 結果CSVのカラム定義
RESULT_COLUMNS: list[str] = [
    "企業名", "URL", "HTTPステータス", "フォームURL", "ステータス",
    "失敗理由", "マッピング結果", "フォーム種別", "CAPTCHA有無",
    "処理時間(秒)", "処理日時",
]


def generate_result_filename() -> str:
    """タイムスタンプ付きの結果ファイル名を生成する"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"results_{ts}.csv"


def save_results(records: list[dict], filepath: str) -> None:
    """処理結果をCSVに保存する"""
    df = pd.DataFrame(records, columns=RESULT_COLUMNS)
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    log.info(f"結果CSV保存: {filepath} ({len(records)}件)")


def load_processed_urls(results_dir: Path) -> set[str]:
    """過去の結果CSVから処理済みURLを読み込む（--resume用）"""
    processed: set[str] = set()
    csv_files = sorted(results_dir.glob("results_*.csv"))
    if not csv_files:
        log.info("過去の結果CSVなし — 最初から処理します")
        return processed

    latest = csv_files[-1]
    log.info(f"再開用CSV読み込み: {latest.name}")
    try:
        df = pd.read_csv(latest, encoding='utf-8-sig')
        if "URL" in df.columns:
            processed = set(df["URL"].dropna().astype(str))
        log.info(f"処理済みURL: {len(processed)}件")
    except Exception as e:
        log.warning(f"結果CSV読み込み失敗: {e}")

    return processed


def print_summary(records: list[dict], elapsed_sec: float) -> None:
    """コンソールにサマリーを表示する"""
    total = len(records)
    if total == 0:
        log.info("処理件数: 0社")
        return

    # ステータス別集計
    counts: dict[str, int] = {}
    for status in [STATUS_SUCCESS, STATUS_PARTIAL, STATUS_NO_FORM,
                   STATUS_CAPTCHA, STATUS_TIMEOUT, STATUS_ERROR]:
        counts[status] = sum(1 for r in records if r.get("ステータス") == status)

    success_rate = (counts[STATUS_SUCCESS] + counts[STATUS_PARTIAL]) / total * 100

    minutes = int(elapsed_sec // 60)
    seconds = int(elapsed_sec % 60)

    summary = f"""
===== 実行結果サマリー =====
処理件数    : {total}社
SUCCESS     : {counts[STATUS_SUCCESS]}社 ({counts[STATUS_SUCCESS]/total*100:.0f}%)
PARTIAL     : {counts[STATUS_PARTIAL]}社 ({counts[STATUS_PARTIAL]/total*100:.0f}%)
NO_FORM     : {counts[STATUS_NO_FORM]}社 ({counts[STATUS_NO_FORM]/total*100:.0f}%)
CAPTCHA     : {counts[STATUS_CAPTCHA]}社 ({counts[STATUS_CAPTCHA]/total*100:.0f}%)
TIMEOUT     : {counts[STATUS_TIMEOUT]}社 ({counts[STATUS_TIMEOUT]/total*100:.0f}%)
ERROR       : {counts[STATUS_ERROR]}社 ({counts[STATUS_ERROR]/total*100:.0f}%)
推定成功率  : {success_rate:.0f}% (SUCCESS+PARTIAL)
合計処理時間: {minutes}分{seconds}秒
============================"""
    # loggingで出力（print禁止のため）
    for line in summary.strip().split('\n'):
        log.info(line)


def save_screening_csvs(records: list[dict]) -> None:
    """スクリーニング結果を4つのCSVに振り分けて出力する"""
    candidate = [r for r in records if r.get("ステータス") in (STATUS_SUCCESS, STATUS_PARTIAL)]
    captcha = [r for r in records if r.get("ステータス") == STATUS_CAPTCHA]
    no_form = [r for r in records if r.get("ステータス") == STATUS_NO_FORM]
    errors = [r for r in records if r.get("ステータス") in (STATUS_TIMEOUT, STATUS_ERROR)]

    for filename, data, label in [
        ("auto_candidate.csv", candidate, "送信候補"),
        ("captcha_list.csv", captcha, "CAPTCHA検出"),
        ("no_form_list.csv", no_form, "フォームなし"),
        ("error_list.csv", errors, "エラー"),
    ]:
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        log.info(f"振り分けCSV保存: {filename} ({len(data)}件: {label})")


def print_screening_summary(records: list[dict]) -> None:
    """スクリーニング結果サマリーを表示する"""
    total = len(records)
    if total == 0:
        return

    n_candidate = sum(1 for r in records if r.get("ステータス") in (STATUS_SUCCESS, STATUS_PARTIAL))
    n_captcha = sum(1 for r in records if r.get("ステータス") == STATUS_CAPTCHA)
    n_no_form = sum(1 for r in records if r.get("ステータス") == STATUS_NO_FORM)
    n_error = sum(1 for r in records if r.get("ステータス") in (STATUS_TIMEOUT, STATUS_ERROR))

    est_rate = n_candidate / total * 100 if total > 0 else 0

    summary = f"""
===== スクリーニング結果 =====
全体          : {total}社
送信候補      : {n_candidate}社 ({n_candidate/total*100:.0f}%)
CAPTCHA除外   : {n_captcha}社 ({n_captcha/total*100:.0f}%)
NO_FORM除外   : {n_no_form}社 ({n_no_form/total*100:.0f}%)
ERROR除外     : {n_error}社 ({n_error/total*100:.0f}%)

除外後の推定成功率: {est_rate:.0f}%
==============================

出力ファイル:
  auto_candidate.csv  → 送信候補 ({n_candidate}社)
  captcha_list.csv    → CAPTCHA除外 ({n_captcha}社)
  no_form_list.csv    → フォームなし除外 ({n_no_form}社)
  error_list.csv      → エラー除外 ({n_error}社)"""

    for line in summary.strip().split('\n'):
        log.info(line)
