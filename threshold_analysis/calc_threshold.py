"""
ベアリング異常検知 段階的アラームしきい値算出スクリプト

4データセット（CWRU・NASA・XJTU-SY・FEMTO）の正常データから
注意・警告・危険の3段階しきい値を算出する
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('threshold_analysis/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# パス定義
BASE_DIR = Path(".")
CWRU_FEATURES = BASE_DIR / "bearing_analysis" / "data" / "features.csv"
NASA_FEATURES = BASE_DIR / "nasa_bearing" / "data" / "features.csv"
XJTU_DIR = BASE_DIR / "xjtu_sy_bearing" / "data" / "features"
FEMTO_DIR = BASE_DIR / "femto_bearing" / "data" / "features"

# 正常区間の割合（Run-to-failureデータセット用）
NORMAL_RATIO = 0.20

# しきい値倍率
THRESHOLD_RATIOS = {
    "caution": 1.20,   # 注意: 120%
    "warning": 1.50,   # 警告: 150%
    "danger": 2.00,    # 危険: 200%
}


@dataclass
class RmsStats:
    """RMS統計量を格納するデータクラス"""
    mean: float
    std: float
    max: float
    median: float
    percentile_95: float
    percentile_99: float
    sample_count: int


def load_cwru_normal_rms() -> np.ndarray:
    """CWRUデータセットから正常ラベルのRMSを取得する"""
    df = pd.read_csv(CWRU_FEATURES)
    normal_rms = df[df["label"] == 0]["rms"].values
    logger.info(f"CWRU: 正常データ {len(normal_rms)}件を読み込み")
    return normal_rms


def load_nasa_normal_rms() -> np.ndarray:
    """NASAデータセットから先頭20%を正常区間として取得する"""
    df = pd.read_csv(NASA_FEATURES)
    # snapshot_idxでソートして先頭20%を正常とみなす
    df = df.sort_values("snapshot_idx").reset_index(drop=True)
    cutoff = int(len(df) * NORMAL_RATIO)
    normal_rms = df.iloc[:cutoff]["rms"].values
    logger.info(f"NASA: 全{len(df)}件中、先頭{cutoff}件を正常区間として使用")
    return normal_rms


def load_rtf_normal_rms(feature_dir: Path, rms_columns: list[str]) -> np.ndarray:
    """Run-to-failureデータセットから各ベアリングの先頭20%を正常区間として取得する

    Args:
        feature_dir: 特徴量CSVが格納されたディレクトリ
        rms_columns: RMS列名のリスト（例: ["h_rms", "v_rms"]）

    Returns:
        正常区間のRMS値（複数チャネルを平均化）
    """
    all_normal_rms = []
    csv_files = sorted(feature_dir.glob("*.csv"))

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        df = df.sort_values("snapshot_idx").reset_index(drop=True)
        cutoff = int(len(df) * NORMAL_RATIO)

        # 複数チャネルのRMS平均を使用
        normal_df = df.iloc[:cutoff]
        avg_rms = normal_df[rms_columns].mean(axis=1).values
        all_normal_rms.append(avg_rms)
        logger.info(
            f"  {csv_path.name}: 全{len(df)}件中、先頭{cutoff}件を正常区間"
        )

    combined = np.concatenate(all_normal_rms)
    return combined


def calc_rms_stats(rms_values: np.ndarray) -> RmsStats:
    """RMS配列から統計量を算出する

    Args:
        rms_values: RMS値の配列

    Returns:
        RMS統計量
    """
    return RmsStats(
        mean=float(np.mean(rms_values)),
        std=float(np.std(rms_values)),
        max=float(np.max(rms_values)),
        median=float(np.median(rms_values)),
        percentile_95=float(np.percentile(rms_values, 95)),
        percentile_99=float(np.percentile(rms_values, 99)),
        sample_count=len(rms_values),
    )


def calc_thresholds(stats: RmsStats) -> dict:
    """統計量からしきい値を算出する

    Args:
        stats: RMS統計量

    Returns:
        しきい値辞書
    """
    baseline = stats.mean
    thresholds = {
        "baseline_mean": baseline,
        "baseline_std": stats.std,
    }
    for level, ratio in THRESHOLD_RATIOS.items():
        thresholds[level] = baseline * ratio

    return thresholds


def validate_thresholds(
    stats: RmsStats,
    thresholds: dict,
    dataset_name: str,
) -> dict:
    """しきい値の妥当性を検証する

    正常データの分布に対して各しきい値がどの位置にあるかを評価する

    Args:
        stats: RMS統計量
        thresholds: しきい値辞書
        dataset_name: データセット名

    Returns:
        検証結果辞書
    """
    mean = stats.mean
    std = stats.std

    validation = {}
    for level in ["caution", "warning", "danger"]:
        threshold_val = thresholds[level]
        # 正常平均から何σ離れているか
        sigma_distance = (threshold_val - mean) / std if std > 0 else float('inf')
        # 正常最大値との比較
        exceeds_normal_max = threshold_val > stats.max
        # 99パーセンタイルとの比較
        above_p99 = threshold_val > stats.percentile_99

        validation[level] = {
            "threshold_value": round(threshold_val, 6),
            "ratio_to_mean": THRESHOLD_RATIOS[level],
            "sigma_from_mean": round(sigma_distance, 2),
            "exceeds_normal_max": exceeds_normal_max,
            "above_99th_percentile": above_p99,
        }

        logger.info(
            f"  {dataset_name} [{level}]: "
            f"値={threshold_val:.6f}, "
            f"{sigma_distance:.1f}σ, "
            f"正常最大超過={exceeds_normal_max}"
        )

    return validation


def main() -> None:
    """メイン処理: 4データセットのしきい値算出と検証"""
    logger.info("=" * 60)
    logger.info("段階的アラームしきい値算出 開始")
    logger.info("=" * 60)

    results = {}

    # --- CWRU ---
    logger.info("--- CWRU ベアリングデータセット ---")
    cwru_rms = load_cwru_normal_rms()
    cwru_stats = calc_rms_stats(cwru_rms)
    cwru_thresholds = calc_thresholds(cwru_stats)
    cwru_validation = validate_thresholds(cwru_stats, cwru_thresholds, "CWRU")
    results["cwru"] = {
        "stats": asdict(cwru_stats),
        "thresholds": cwru_thresholds,
        "validation": cwru_validation,
        "normal_definition": "label==normal（明示ラベル）",
    }

    # --- NASA ---
    logger.info("--- NASA IMS ベアリングデータセット ---")
    nasa_rms = load_nasa_normal_rms()
    nasa_stats = calc_rms_stats(nasa_rms)
    nasa_thresholds = calc_thresholds(nasa_stats)
    nasa_validation = validate_thresholds(nasa_stats, nasa_thresholds, "NASA")
    results["nasa"] = {
        "stats": asdict(nasa_stats),
        "thresholds": nasa_thresholds,
        "validation": nasa_validation,
        "normal_definition": "先頭20%（Run-to-failure）",
    }

    # --- XJTU-SY ---
    logger.info("--- XJTU-SY ベアリングデータセット ---")
    xjtu_rms = load_rtf_normal_rms(XJTU_DIR, ["h_rms", "v_rms"])
    xjtu_stats = calc_rms_stats(xjtu_rms)
    xjtu_thresholds = calc_thresholds(xjtu_stats)
    xjtu_validation = validate_thresholds(xjtu_stats, xjtu_thresholds, "XJTU-SY")
    results["xjtu_sy"] = {
        "stats": asdict(xjtu_stats),
        "thresholds": xjtu_thresholds,
        "validation": xjtu_validation,
        "normal_definition": "各ベアリング先頭20%（Run-to-failure、H/V平均）",
    }

    # --- FEMTO ---
    logger.info("--- FEMTO ベアリングデータセット ---")
    femto_rms = load_rtf_normal_rms(FEMTO_DIR, ["h_rms", "v_rms"])
    femto_stats = calc_rms_stats(femto_rms)
    femto_thresholds = calc_thresholds(femto_stats)
    femto_validation = validate_thresholds(femto_stats, femto_thresholds, "FEMTO")
    results["femto"] = {
        "stats": asdict(femto_stats),
        "thresholds": femto_thresholds,
        "validation": femto_validation,
        "normal_definition": "各ベアリング先頭20%（Run-to-failure、H/V平均）",
    }

    # --- しきい値設定ファイル出力 ---
    threshold_config = {}
    for ds_name, ds_result in results.items():
        threshold_config[ds_name] = {
            "baseline_mean": round(ds_result["thresholds"]["baseline_mean"], 6),
            "baseline_std": round(ds_result["thresholds"]["baseline_std"], 6),
            "caution": round(ds_result["thresholds"]["caution"], 6),
            "warning": round(ds_result["thresholds"]["warning"], 6),
            "danger": round(ds_result["thresholds"]["danger"], 6),
            "unit": "RMS (acceleration)",
            "normal_definition": ds_result["normal_definition"],
        }

    config_path = Path("threshold_analysis") / "threshold_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(threshold_config, f, indent=2, ensure_ascii=False)
    logger.info(f"しきい値設定ファイルを出力: {config_path}")

    # --- 統計サマリー表示 ---
    print("\n" + "=" * 70)
    print("【RMS統計量サマリー】")
    print("=" * 70)
    for ds_name, ds_result in results.items():
        s = ds_result["stats"]
        t = ds_result["thresholds"]
        print(f"\n■ {ds_name.upper()}")
        print(f"  正常定義: {ds_result['normal_definition']}")
        print(f"  サンプル数: {s['sample_count']}")
        print(f"  平均: {s['mean']:.6f}")
        print(f"  標準偏差: {s['std']:.6f}")
        print(f"  中央値: {s['median']:.6f}")
        print(f"  最大値: {s['max']:.6f}")
        print(f"  95%ile: {s['percentile_95']:.6f}")
        print(f"  99%ile: {s['percentile_99']:.6f}")
        print(f"  変動係数(CV): {s['std']/s['mean']*100:.1f}%")
        print(f"  --- しきい値 ---")
        print(f"  注意(120%): {t['caution']:.6f}")
        print(f"  警告(150%): {t['warning']:.6f}")
        print(f"  危険(200%): {t['danger']:.6f}")

    # --- 妥当性検証サマリー ---
    print("\n" + "=" * 70)
    print("【しきい値妥当性検証】")
    print("=" * 70)
    for ds_name, ds_result in results.items():
        v = ds_result["validation"]
        s = ds_result["stats"]
        print(f"\n■ {ds_name.upper()}")
        for level in ["caution", "warning", "danger"]:
            vl = v[level]
            status = "○" if vl["exceeds_normal_max"] else "△要注意"
            print(
                f"  {level:8s}: "
                f"{vl['sigma_from_mean']:+.1f}σ | "
                f"正常最大超過: {status} | "
                f"99%ile超過: {'○' if vl['above_99th_percentile'] else '×'}"
            )

        # CV（変動係数）に基づく総合評価
        cv = s["std"] / s["mean"] * 100
        if cv > 30:
            print(f"  [!] 変動係数が大きい({cv:.1f}%) -> 固定倍率より統計ベースのしきい値を推奨")
        elif cv > 15:
            print(f"  [?] 変動係数がやや大きい({cv:.1f}%) -> 注意しきい値の微調整を検討")
        else:
            print(f"  [OK] 変動係数が安定({cv:.1f}%) -> 倍率ベースのしきい値が妥当")

    logger.info("段階的アラームしきい値算出 完了")


if __name__ == "__main__":
    main()
