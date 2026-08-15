"""
Stage 3: LSTM-AutoEncoder 評価モジュール

再構成誤差の分布からRMSベースの3段階しきい値を算出し評価する
"""

import logging

import numpy as np
import torch
from sklearn.preprocessing import StandardScaler

from threshold_analysis.models.threshold_result import (
    EvaluationResult,
    ThresholdSet,
)
from threshold_analysis.stage3_lstm_ae_model import (
    LSTMAutoEncoder,
    calc_reconstruction_error,
    create_sequences,
)
from threshold_analysis.stage3_lstm_ae_train import run_stage3_train
from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    extract_rms,
    get_feature_columns,
    load_dataset,
)
from threshold_analysis.utils.evaluation import evaluate_thresholds

logger = logging.getLogger(__name__)


def errors_to_rms_thresholds(
    errors: np.ndarray,
    rms_values: np.ndarray,
    percentiles: tuple[float, float, float] = (95.0, 99.0, 99.9),
) -> tuple[float, float, float]:
    """再構成誤差のパーセンタイルに対応するRMS値を算出する

    誤差が大きい（異常度が高い）サンプルのRMS値をしきい値とする

    Args:
        errors: 再構成誤差配列
        rms_values: 対応するRMS配列（errorsと同じ長さ）
        percentiles: (caution, warning, danger)のパーセンタイル

    Returns:
        (caution_rms, warning_rms, danger_rms)
    """
    # 再構成誤差で昇順ソート（誤差小→大 = 正常→異常）
    sorted_idx = np.argsort(errors)
    sorted_rms = rms_values[sorted_idx]
    n = len(errors)

    thresholds = []
    for pct in percentiles:
        idx = min(int(n * pct / 100), n - 1)
        thresholds.append(float(sorted_rms[idx]))

    return tuple(thresholds)  # type: ignore


def evaluate_lstm_ae(
    model: LSTMAutoEncoder,
    scaler: StandardScaler,
    dataset_name: str,
    seq_length: int,
) -> tuple[ThresholdSet, EvaluationResult]:
    """LSTM-AEを評価してThresholdSetとEvaluationResultを返す

    Args:
        model: 学習済みLSTM-AEモデル
        scaler: 学習済みスケーラー
        dataset_name: データセット名
        seq_length: シーケンス長

    Returns:
        (ThresholdSet, EvaluationResult)
    """
    normal_df, full_df = load_dataset(dataset_name)
    feature_cols = get_feature_columns(dataset_name)
    normal_rms = extract_rms(normal_df, dataset_name)
    full_rms = extract_rms(full_df, dataset_name)

    # 全データの再構成誤差を算出
    full_features = full_df[feature_cols].values
    full_scaled = scaler.transform(full_features)
    full_sequences = create_sequences(full_scaled, seq_length)
    full_seq_tensor = torch.FloatTensor(full_sequences)
    full_errors = calc_reconstruction_error(model, full_seq_tensor)

    # シーケンス化でデータが短くなるので、対応するRMSを切り出す
    # シーケンスiはfeatures[i:i+seq_length]に対応→代表値はi+seq_length-1
    offset = seq_length - 1
    aligned_rms = full_rms[offset:offset + len(full_errors)]

    # 正常データの再構成誤差（メタデータ用）
    normal_features_arr = normal_df[feature_cols].values
    normal_scaled = scaler.transform(normal_features_arr)
    normal_sequences = create_sequences(normal_scaled, seq_length)
    normal_seq_tensor = torch.FloatTensor(normal_sequences)
    normal_errors = calc_reconstruction_error(model, normal_seq_tensor)

    # 再構成誤差→RMSしきい値に変換
    caution, warning, danger = errors_to_rms_thresholds(
        full_errors, aligned_rms,
    )

    ts = ThresholdSet(
        method="lstm_ae",
        dataset=dataset_name,
        caution=caution,
        warning=warning,
        danger=danger,
        metadata={
            "seq_length": seq_length,
            "error_mean_normal": round(float(np.mean(normal_errors)), 6),
            "error_std_normal": round(float(np.std(normal_errors)), 6),
            "error_95pct_normal": round(
                float(np.percentile(normal_errors, 95)), 6,
            ),
        },
    )

    # RMSベースで評価（既存手法と同じ基準で比較）
    is_labeled = dataset_name == "cwru"
    ev = evaluate_thresholds(ts, normal_rms, full_rms, is_labeled)

    logger.info(
        f"[lstm_ae] {dataset_name}: "
        f"caution={caution:.6f} warning={warning:.6f} danger={danger:.6f} "
        f"誤報率={ev.false_alarm_rate:.1f}% 検出率={ev.detection_rate_late:.1f}%"
    )

    return ts, ev


def run_stage3(
    dataset_name: str,
) -> tuple[ThresholdSet, EvaluationResult]:
    """指定データセットでStage3を実行する

    Args:
        dataset_name: データセット名

    Returns:
        (ThresholdSet, EvaluationResult)
    """
    logger.info(f"=== Stage3: {dataset_name} ===")
    model, scaler, seq_length = run_stage3_train(dataset_name)
    return evaluate_lstm_ae(model, scaler, dataset_name, seq_length)


def run_stage3_all() -> dict[str, tuple[ThresholdSet, EvaluationResult]]:
    """4データセット全てにStage3を適用する

    Returns:
        {データセット名: (ThresholdSet, EvaluationResult)}
    """
    results = {}
    for ds in ALL_DATASETS:
        results[ds] = run_stage3(ds)
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

    all_results = run_stage3_all()
    all_evals = [ev for _, (_, ev) in all_results.items()]

    comparison_df = compare_methods(all_evals)
    print("\n" + comparison_df.to_string(index=False))
