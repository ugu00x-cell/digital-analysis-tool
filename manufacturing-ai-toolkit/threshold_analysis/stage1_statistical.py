"""
Stage 1: 統計ベースの動的しきい値算出

3手法を実装:
- 平均+Nσ: 正規分布仮定のパラメトリック手法
- パーセンタイル: 分布非依存のノンパラメトリック手法
- MAD(中央絶対偏差): 外れ値に頑健なロバスト手法
"""

import logging

import numpy as np

from threshold_analysis.models.threshold_result import ThresholdSet
from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    extract_rms,
    load_dataset,
)

logger = logging.getLogger(__name__)


def calc_sigma_thresholds(
    normal_rms: np.ndarray,
    dataset_name: str,
    sigma_levels: tuple[float, float, float] = (2.0, 3.0, 4.0),
) -> ThresholdSet:
    """平均+Nσでしきい値を算出する

    正規分布仮定で、2σ(95.4%), 3σ(99.7%), 4σ(99.99%)をカバー

    Args:
        normal_rms: 正常区間のRMS配列
        dataset_name: データセット名
        sigma_levels: (caution, warning, danger)のσ倍数

    Returns:
        ThresholdSet
    """
    mean = float(np.mean(normal_rms))
    std = float(np.std(normal_rms))

    thresholds = ThresholdSet(
        method="sigma",
        dataset=dataset_name,
        caution=mean + sigma_levels[0] * std,
        warning=mean + sigma_levels[1] * std,
        danger=mean + sigma_levels[2] * std,
        metadata={
            "sigma_levels": list(sigma_levels),
            "normal_mean": round(mean, 6),
            "normal_std": round(std, 6),
        },
    )
    logger.info(
        f"[sigma] {dataset_name}: "
        f"caution={thresholds.caution:.6f} "
        f"warning={thresholds.warning:.6f} "
        f"danger={thresholds.danger:.6f}"
    )
    return thresholds


def calc_percentile_thresholds(
    normal_rms: np.ndarray,
    dataset_name: str,
    percentiles: tuple[float, float, float] = (95.0, 99.0, 99.9),
) -> ThresholdSet:
    """パーセンタイルベースのしきい値を算出する

    分布形状を仮定しないノンパラメトリック手法

    Args:
        normal_rms: 正常区間のRMS配列
        dataset_name: データセット名
        percentiles: (caution, warning, danger)のパーセンタイル

    Returns:
        ThresholdSet
    """
    values = [float(np.percentile(normal_rms, p)) for p in percentiles]

    thresholds = ThresholdSet(
        method="percentile",
        dataset=dataset_name,
        caution=values[0],
        warning=values[1],
        danger=values[2],
        metadata={"percentiles": list(percentiles)},
    )
    logger.info(
        f"[percentile] {dataset_name}: "
        f"caution={thresholds.caution:.6f} "
        f"warning={thresholds.warning:.6f} "
        f"danger={thresholds.danger:.6f}"
    )
    return thresholds


def calc_mad_thresholds(
    normal_rms: np.ndarray,
    dataset_name: str,
    mad_levels: tuple[float, float, float] = (3.0, 5.0, 7.0),
) -> ThresholdSet:
    """MAD(中央絶対偏差)ベースのしきい値を算出する

    外れ値に頑健なロバスト手法。高CV(変動係数)のデータセット向け。
    MAD = median(|Xi - median(X)|)
    しきい値 = median + k * MAD * 1.4826（正規分布換算係数）

    Args:
        normal_rms: 正常区間のRMS配列
        dataset_name: データセット名
        mad_levels: (caution, warning, danger)のMAD倍数

    Returns:
        ThresholdSet
    """
    median = float(np.median(normal_rms))
    # MADの計算
    mad = float(np.median(np.abs(normal_rms - median)))
    # 正規分布換算係数（MAD * 1.4826 ≒ σ相当）
    mad_scaled = mad * 1.4826

    thresholds = ThresholdSet(
        method="mad",
        dataset=dataset_name,
        caution=median + mad_levels[0] * mad_scaled,
        warning=median + mad_levels[1] * mad_scaled,
        danger=median + mad_levels[2] * mad_scaled,
        metadata={
            "mad_levels": list(mad_levels),
            "median": round(median, 6),
            "mad": round(mad, 6),
            "mad_scaled": round(mad_scaled, 6),
        },
    )
    logger.info(
        f"[MAD] {dataset_name}: "
        f"caution={thresholds.caution:.6f} "
        f"warning={thresholds.warning:.6f} "
        f"danger={thresholds.danger:.6f}"
    )
    return thresholds


def calc_fixed_ratio_thresholds(
    normal_rms: np.ndarray,
    dataset_name: str,
    ratios: tuple[float, float, float] = (1.2, 1.5, 2.0),
) -> ThresholdSet:
    """既存の固定倍率しきい値（比較用ベースライン）

    Args:
        normal_rms: 正常区間のRMS配列
        dataset_name: データセット名
        ratios: (caution, warning, danger)の倍率

    Returns:
        ThresholdSet
    """
    mean = float(np.mean(normal_rms))
    return ThresholdSet(
        method="fixed_ratio",
        dataset=dataset_name,
        caution=mean * ratios[0],
        warning=mean * ratios[1],
        danger=mean * ratios[2],
        metadata={"ratios": list(ratios)},
    )


def run_stage1(dataset_name: str) -> list[ThresholdSet]:
    """Stage1の全手法をデータセットに適用する

    Args:
        dataset_name: データセット名

    Returns:
        ThresholdSetのリスト（固定倍率 + sigma + percentile + MAD）
    """
    logger.info(f"=== Stage1: {dataset_name} ===")
    normal_df, _ = load_dataset(dataset_name)
    normal_rms = extract_rms(normal_df, dataset_name)

    return [
        calc_fixed_ratio_thresholds(normal_rms, dataset_name),
        calc_sigma_thresholds(normal_rms, dataset_name),
        calc_percentile_thresholds(normal_rms, dataset_name),
        calc_mad_thresholds(normal_rms, dataset_name),
    ]


def run_stage1_all() -> dict[str, list[ThresholdSet]]:
    """4データセット全てにStage1を適用する

    Returns:
        {データセット名: ThresholdSetリスト}
    """
    results = {}
    for ds in ALL_DATASETS:
        results[ds] = run_stage1(ds)
    return results


if __name__ == "__main__":
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(
                "threshold_analysis/app.log", encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )

    from threshold_analysis.utils.data_loader import extract_rms, load_dataset
    from threshold_analysis.utils.evaluation import (
        compare_methods,
        evaluate_thresholds,
        select_recommended,
    )

    all_thresholds = run_stage1_all()
    all_evals = []

    for ds, ts_list in all_thresholds.items():
        normal_df, full_df = load_dataset(ds)
        normal_rms = extract_rms(normal_df, ds)
        full_rms = extract_rms(full_df, ds)
        is_labeled = ds == "cwru"

        for ts in ts_list:
            ev = evaluate_thresholds(ts, normal_rms, full_rms, is_labeled)
            all_evals.append(ev)

    # 比較テーブル表示
    comparison_df = compare_methods(all_evals)
    print("\n" + comparison_df.to_string(index=False))
