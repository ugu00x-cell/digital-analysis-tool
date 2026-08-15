"""合成データ生成モジュール

製造現場の保全・点検・トラブル履歴を模した3つのExcelファイルを生成する。
表記は基本そろえつつ、症状や作業内容の言い回しに自然な揺れを残し、
LLMが吸収できる範囲で現場ドキュメントらしさを再現する。

実行例:
    python src/generate_data.py
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 乱数シード（再現性確保）
RANDOM_SEED = 42

# 出力先
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# 機械ID一覧（MC001〜MC010、ダッシュなし表記で統一）
MACHINE_IDS: list[str] = [f"MC{i:03d}" for i in range(1, 11)]

# 機械種別マッピング（ID→種別）
MACHINE_TYPES: dict[str, str] = {
    "MC001": "マシニングセンタ", "MC002": "マシニングセンタ",
    "MC003": "マシニングセンタ", "MC004": "マシニングセンタ",
    "MC005": "放電加工機",       "MC006": "放電加工機",
    "MC007": "放電加工機",
    "MC008": "研削盤",           "MC009": "研削盤",
    "MC010": "研削盤",
}

# 担当者・点検者（「さん」付け表記で統一）
OPERATORS: list[str] = ["田中さん", "佐藤さん", "鈴木さん", "高橋さん", "山本さん", "中村さん"]

# 保全作業の例（定期/予防/事後の混在）
MAINTENANCE_WORKS: list[dict[str, str]] = [
    {"work": "スピンドルベアリング交換。異音発生のため早期対応。",
     "parts": "スピンドルベアリング6206", "result": "正常復旧"},
    {"work": "クーラント液交換・フィルター清掃。定期保全。",
     "parts": "クーラントフィルター", "result": "正常"},
    {"work": "X軸ボールネジ点検。バックラッシュ0.02mm確認。",
     "parts": "記録なし", "result": "正常"},
    {"work": "Y軸ガイドレール給脂。月次定期保全。",
     "parts": "リチウムグリス", "result": "正常"},
    {"work": "Z軸サーボモータ交換。エンコーダエラー多発のため。",
     "parts": "サーボモータZ軸用", "result": "正常復旧"},
    {"work": "ATCツールホルダ交換。把持力低下のため。",
     "parts": "ツールホルダBT40", "result": "正常復旧"},
    {"work": "油圧ユニット作動油交換。年次保全。",
     "parts": "作動油ISO VG32 20L", "result": "正常"},
    {"work": "電極消耗確認・交換。放電加工後の標準作業。",
     "parts": "銅電極", "result": "正常"},
    {"work": "砥石ドレッシング。研削面粗さ悪化のため。",
     "parts": "ダイヤモンドドレッサ", "result": "正常復旧"},
    {"work": "主軸ベアリング異音調査。初期段階のため経過観察。",
     "parts": "記録なし", "result": "経過観察"},
    {"work": "原点復帰センサ清掃。アラーム頻発のため。",
     "parts": "記録なし", "result": "正常復旧"},
    {"work": "切削油配管詰まり除去。流量低下のため緊急対応。",
     "parts": "記録なし", "result": "正常復旧"},
]

# 点検項目と典型結果
INSPECTION_ITEMS: list[dict[str, str]] = [
    {"item": "油圧",       "ok": "圧力7.0MPa正常",         "ng": "圧力低下6.2MPa"},
    {"item": "冷却水",     "ok": "流量・温度正常",          "ng": "温度上昇38度"},
    {"item": "切削油",     "ok": "濃度・色味正常",          "ng": "濃度低下・濁り"},
    {"item": "X軸精度",    "ok": "バックラッシュ0.01mm",    "ng": "バックラッシュ0.04mm"},
    {"item": "Y軸精度",    "ok": "バックラッシュ0.01mm",    "ng": "わずかなガタつき"},
    {"item": "Z軸精度",    "ok": "バックラッシュ0.01mm",    "ng": "バックラッシュ0.03mm"},
    {"item": "安全装置",   "ok": "インターロック動作正常",  "ng": "扉スイッチ反応遅延"},
    {"item": "主軸",       "ok": "回転音・振動正常",        "ng": "わずかな異音あり"},
    {"item": "ATC",        "ok": "工具交換動作正常",        "ng": "把持力やや低下"},
]

# トラブル症状・原因・対処（症状の言い回しに自然な揺れを残す）
TROUBLE_PATTERNS: list[dict[str, str]] = [
    {"symptom": "加工中に異音発生・振動増大",
     "cause": "スピンドルベアリングの摩耗",
     "action": "ベアリング交換・主軸バランス調整",
     "prevention": "稼働時間1500hでの予防交換ルール化"},
    {"symptom": "主軸から異音、加工面荒れ",
     "cause": "ベアリング初期不良の可能性",
     "action": "ベアリング交換・振動測定で正常確認",
     "prevention": "受入時の振動測定実施"},
    {"symptom": "原点復帰エラーアラーム",
     "cause": "原点センサに切粉付着",
     "action": "センサ清掃・カバー追加",
     "prevention": "週次でセンサ周辺清掃"},
    {"symptom": "加工寸法がX軸方向に0.05mmずれる",
     "cause": "X軸ボールネジのバックラッシュ拡大",
     "action": "ボールネジ調整・補正値更新",
     "prevention": "月次精度測定の徹底"},
    {"symptom": "加工途中で主軸停止",
     "cause": "サーボアンプの過熱保護動作",
     "action": "アンプ冷却ファン交換・配線見直し",
     "prevention": "ファン年次交換ルール化"},
    {"symptom": "クーラント供給量が不安定",
     "cause": "ポンプフィルター詰まり",
     "action": "フィルター清掃・配管エア抜き",
     "prevention": "週次でフィルター点検"},
    {"symptom": "ATC工具交換時の落下",
     "cause": "ツールホルダ把持力低下",
     "action": "ツールホルダ交換・把持力測定",
     "prevention": "把持力点検を月次化"},
    {"symptom": "放電加工で電極消耗が異常に早い",
     "cause": "加工条件設定誤り(電流値過大)",
     "action": "条件再設定・標準条件表更新",
     "prevention": "条件変更時のダブルチェック"},
    {"symptom": "研削面に縞模様発生",
     "cause": "砥石の目詰まり",
     "action": "ドレッシング実施・条件見直し",
     "prevention": "稼働時間ごとのドレッシング計画化"},
    {"symptom": "Z軸が指令位置に到達しない",
     "cause": "Z軸サーボモータエンコーダ故障",
     "action": "エンコーダ交換・原点再設定",
     "prevention": "エンコーダ予備在庫の確保"},
]

ABNORMALITY_RATE = 0.15  # 点検で異常が出る確率


@dataclass
class GenerationConfig:
    """生成件数の設定。"""

    maintenance_count: int = 200
    inspection_count: int = 300
    trouble_count: int = 100


def _random_date(start: date, end: date, rng: random.Random) -> date:
    """指定範囲内のランダムな日付を返す。

    Args:
        start: 開始日（含む）
        end: 終了日（含む）
        rng: 乱数生成器

    Returns:
        ランダムな日付
    """
    delta_days = (end - start).days
    if delta_days < 0:
        raise ValueError("end は start 以降の日付である必要があります")
    return start + timedelta(days=rng.randint(0, delta_days))


def generate_maintenance_logs(count: int, rng: random.Random) -> pd.DataFrame:
    """保全記録データを生成する。

    Args:
        count: 生成件数
        rng: 乱数生成器

    Returns:
        保全記録のDataFrame
    """
    if count <= 0:
        raise ValueError("count は1以上を指定してください")

    rows: list[dict] = []
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    for _ in range(count):
        work = rng.choice(MAINTENANCE_WORKS)
        rows.append({
            "date": _random_date(start, end, rng).isoformat(),
            "machine_id": rng.choice(MACHINE_IDS),
            "operator": rng.choice(OPERATORS),
            "work_content": work["work"],
            "parts_replaced": work["parts"],
            "work_hours": f"{round(rng.uniform(0.5, 6.0), 1)}h",
            "result": work["result"],
        })
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    logger.info("保全記録を %d 件生成しました", len(df))
    return df


def generate_inspection_reports(count: int, rng: random.Random) -> pd.DataFrame:
    """点検日報データを生成する。

    Args:
        count: 生成件数
        rng: 乱数生成器

    Returns:
        点検日報のDataFrame
    """
    if count <= 0:
        raise ValueError("count は1以上を指定してください")

    rows: list[dict] = []
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    for _ in range(count):
        item = rng.choice(INSPECTION_ITEMS)
        is_abnormal = rng.random() < ABNORMALITY_RATE
        rows.append({
            "date": _random_date(start, end, rng).isoformat(),
            "machine_id": rng.choice(MACHINE_IDS),
            "inspector": rng.choice(OPERATORS),
            "check_item": item["item"],
            "result": "異常" if is_abnormal else "正常",
            "abnormality": item["ng"] if is_abnormal else "記録なし",
            "action_taken": "保全部門へ連絡・継続観察" if is_abnormal else "記録なし",
        })
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    logger.info("点検日報を %d 件生成しました", len(df))
    return df


def generate_trouble_history(count: int, rng: random.Random) -> pd.DataFrame:
    """トラブル履歴データを生成する。

    Args:
        count: 生成件数
        rng: 乱数生成器

    Returns:
        トラブル履歴のDataFrame
    """
    if count <= 0:
        raise ValueError("count は1以上を指定してください")

    rows: list[dict] = []
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    for _ in range(count):
        pattern = rng.choice(TROUBLE_PATTERNS)
        occurred = _random_date(start, end, rng)
        # occurred_at は "YYYY-MM-DD HH:MM" 形式
        hour = rng.randint(8, 19)
        minute = rng.choice([0, 15, 30, 45])
        rows.append({
            "occurred_at": f"{occurred.isoformat()} {hour:02d}:{minute:02d}",
            "machine_id": rng.choice(MACHINE_IDS),
            "symptom": pattern["symptom"],
            "cause": pattern["cause"],
            "action": pattern["action"],
            "downtime_hours": f"{round(rng.uniform(0.5, 12.0), 1)}h",
            "recurrence_prevention": pattern["prevention"],
        })
    df = pd.DataFrame(rows).sort_values("occurred_at").reset_index(drop=True)
    logger.info("トラブル履歴を %d 件生成しました", len(df))
    return df


def save_to_excel(df: pd.DataFrame, path: Path) -> None:
    """DataFrame をExcelファイルとして保存する。

    Args:
        df: 保存対象のDataFrame
        path: 出力先ファイルパス

    Raises:
        OSError: 保存に失敗した場合
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(path, index=False, engine="openpyxl")
        logger.info("保存完了: %s (%d 行)", path, len(df))
    except OSError as e:
        logger.error("Excel保存に失敗: %s - %s", path, e)
        raise


def main(config: GenerationConfig | None = None) -> None:
    """3種類の合成Excelファイルを生成する。

    Args:
        config: 生成件数の設定。Noneの場合は仕様書のデフォルト件数。
    """
    cfg = config or GenerationConfig()
    rng = random.Random(RANDOM_SEED)

    save_to_excel(
        generate_maintenance_logs(cfg.maintenance_count, rng),
        OUTPUT_DIR / "maintenance_logs.xlsx",
    )
    save_to_excel(
        generate_inspection_reports(cfg.inspection_count, rng),
        OUTPUT_DIR / "inspection_reports.xlsx",
    )
    save_to_excel(
        generate_trouble_history(cfg.trouble_count, rng),
        OUTPUT_DIR / "trouble_history.xlsx",
    )
    logger.info("合成データ生成 完了")


if __name__ == "__main__":
    main()
