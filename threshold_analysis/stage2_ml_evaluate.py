"""
Stage 2: 機械学習ベースのしきい値算出（評価モジュール）

異常スコアからRMSベースの3段階アラームしきい値に変換し評価する
"""

import logging

import numpy as np

from threshold_analysis.models.threshold_result import (
    EvaluationResult,
    ThresholdSet,
)
from threshold_analysis.stage2_ml_train import (
    AnomalyModel,
    get_anomaly_scores,
    run_stage2_train,
)
from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    extract_rms,
    get_feature_columns,
    load_dataset,
)
from threshold_analysis.utils.evaluation import evaluate_thresholds

logger = logging.getLogger(__name__)


def scores_to_rms_thresholds(
    scores: np.ndarray,
    rms_values: np.ndarray,
    percentiles: tuple[float, float, float] = (95.0, 99.0, 99.9),
) -> tuple[float, float, float]:
    """異常スコアのパーセンタイルに対応するRMS値を算出する

    スコアで異常度合いの境界を決め、そのRMS値をしきい値とする

    Args:
        scores: 全データの異常スコア配列（小さいほど異常）
        rms_values: 全データのRMS配列（scoresと同じ順序）
        percentiles: (caution, warning, danger)の正常スコアパーセンタイル

    Returns:
        (caution_rms, warning_rms, danger_rms)
    """
    # スコアを降順でソート（正常→異常の順）
    sorted_idx = np.argsort(scores)[::-1]
    sorted_rms = rms_values[sorted_idx]
    n = len(scores)

    thresholds = []
    for pct in percentiles:
        # パーセンタイル位置のRMS値を取得
        idx = min(int(n * pct / 100), n - 1)
        thresholds.append(float(sorted_rms[idx]))

    return tuple(thresholds)  # type: ignore


def scores_to_score_thresholds(
    normal_scores: np.ndarray,
    percentiles: tuple[float, float, float] = (5.0, 1.0, 0.1),
) -> tuple[float, float, float]:
    """正常データの異常スコア分布から直接しきい値を算出する

    低パーセンタイル = 正常データの下限付近 = 異常に近い領域

    Args:
        normal_scores: 正常データの異常スコア配列
        percentiles: (caution, warning, danger)の下側パーセンタイル

    Returns:
        (caution_score, warning_score, danger_score)
    """
    return tuple(
        float(np.percentile(normal_scores, p)) for p in percentiles
    )  # type: ignore


def evaluate_ml_model(
    method_name: str,
    model: AnomalyModel,
    scaler: "StandardScaler",  # noqa: F821
    dataset_name: str,
) -> tuple[ThresholdSet, EvaluationResult]:
    """MLモデルを評価してThresholdSetとEvaluationResultを返す

    Args:
        method_name: "if" or "ocsvm"
        model: 学習済みモデル
        scaler: 学習済みスケーラー
        dataset_name: データセット名

    Returns:
        (ThresholdSet, EvaluationResult)
    """
    normal_df, full_df = load_dataset(dataset_name)
    feature_cols = get_feature_columns(dataset_name)
    normal_rms = extract_rms(normal_df, dataset_name)
    full_rms = extract_rms(full_df, dataset_name)

    # 全データの異常スコアを算出
    full_features = full_df[feature_cols].values
    full_scores = get_anomaly_scores(model, scaler, full_features)

    # スコアベースでRMSしきい値に変換
    caution, warning, danger = scores_to_rms_thresholds(
        full_scores, full_rms,
    )

    # 正常データのスコアも取得（メタデータ用）
    normal_features = normal_df[feature_cols].values
    normal_scores = get_anomaly_scores(model, scaler, normal_features)

    ts = ThresholdSet(
        method=method_name,
        dataset=dataset_name,
        caution=caution,
        warning=warning,
        danger=danger,
        metadata={
            "score_mean_normal": round(float(np.mean(normal_scores)), 6),
            "score_std_normal": round(float(np.std(normal_scores)), 6),
            "score_min_normal": round(float(np.min(normal_scores)), 6),
        },
    )

    is_labeled = dataset_name == "cwru"
    ev = evaluate_thresholds(ts, normal_rms, full_rms, is_labeled)

    logger.info(
        f"[{method_name}] {dataset_name}: "
        f"caution={caution:.6f} warning={warning:.6f} danger={danger:.6f} "
        f"誤報率={ev.false_alarm_rate:.1f}% 検出率={ev.detection_rate_late:.1f}%"
    )

    return ts, ev


def run_stage2(
    dataset_name: str,
) -> list[tuple[ThresholdSet, EvaluationResult]]:
    """指定データセットでStage2を実行する

    Args:
        dataset_name: データセット名

    Returns:
        [(ThresholdSet, EvaluationResult)] のリスト
    """
    logger.info(f"=== Stage2: {dataset_name} ===")
    trained = run_stage2_train(dataset_name)
    results = []

    for method_name, (model, scaler) in trained.items():
        ts, ev = evaluate_ml_model(method_name, model, scaler, dataset_name)
        results.append((ts, ev))

    return results


def run_stage2_all() -> dict[str, list[tuple[ThresholdSet, EvaluationResult]]]:
    """4データセット全てにStage2を適用する

    Returns:
        {データセット名: [(ThresholdSet, EvaluationResult)]}
    """
    results = {}
    for ds in ALL_DATASETS:
        results[ds] = run_stage2(ds)
    return results


if __name__ == "__main__":
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

    from threshold_analysis.utils.evaluation import compare_methods

    all_results = run_stage2_all()
    all_evals = []
    for ds, results in all_results.items():
        for ts, ev in results:
            all_evals.append(ev)

    comparison_df = compare_methods(all_evals)
    print("\n" + comparison_df.to_string(index=False))
