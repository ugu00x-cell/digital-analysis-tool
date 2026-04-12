"""
しきい値評価・手法比較の共通ロジック

全ステージで統一的な評価指標を算出する
"""

import logging

import numpy as np
import pandas as pd

from threshold_analysis.models.threshold_result import (
    EvaluationResult,
    ThresholdSet,
)

logger = logging.getLogger(__name__)

# 後半区間の定義（Run-to-failureデータセット用）
LATE_RATIO = 0.20  # 後半20%を劣化区間とみなす


def evaluate_thresholds(
    threshold_set: ThresholdSet,
    normal_rms: np.ndarray,
    full_rms: np.ndarray,
    is_labeled: bool = False,
) -> EvaluationResult:
    """しきい値セットを正常データと全データに対して評価する

    Args:
        threshold_set: 評価対象のしきい値セット
        normal_rms: 正常区間のRMS配列
        full_rms: 全区間のRMS配列
        is_labeled: Trueの場合、full_rmsの後半を異常データとして扱う
                    （CWRUは正常/異常が混在するので、normalとfullから推定）

    Returns:
        評価結果
    """
    mean = float(np.mean(normal_rms))
    std = float(np.std(normal_rms))

    # 誤報率: 正常データ中でcautionを超える割合
    false_alarm_rate = _calc_exceed_rate(normal_rms, threshold_set.caution)

    # σ距離
    sigma_c = _calc_sigma_distance(threshold_set.caution, mean, std)
    sigma_w = _calc_sigma_distance(threshold_set.warning, mean, std)
    sigma_d = _calc_sigma_distance(threshold_set.danger, mean, std)

    # 検出率と初回検出地点
    if is_labeled:
        # CWRU: full_rmsから正常データを除いた部分が異常データ
        anomaly_rms = full_rms[len(normal_rms):]
        detection_rate = _calc_exceed_rate(anomaly_rms, threshold_set.caution)
        first_pct = -1.0  # ラベル付きデータでは寿命%の概念なし
    else:
        # RTF: 後半20%を劣化区間として検出率を評価
        late_start = int(len(full_rms) * (1.0 - LATE_RATIO))
        late_rms = full_rms[late_start:]
        detection_rate = _calc_exceed_rate(late_rms, threshold_set.caution)
        first_pct = _calc_first_detection_pct(full_rms, threshold_set.caution)

    return EvaluationResult(
        method=threshold_set.method,
        dataset=threshold_set.dataset,
        false_alarm_rate=round(false_alarm_rate, 2),
        detection_rate_late=round(detection_rate, 2),
        sigma_caution=round(sigma_c, 2),
        sigma_warning=round(sigma_w, 2),
        sigma_danger=round(sigma_d, 2),
        first_detection_pct=round(first_pct, 1),
    )


def _calc_exceed_rate(rms: np.ndarray, threshold: float) -> float:
    """RMS配列中でしきい値を超えるデータの割合(%)を算出する"""
    if len(rms) == 0:
        return 0.0
    return float(np.sum(rms > threshold) / len(rms) * 100)


def _calc_sigma_distance(
    threshold: float, mean: float, std: float,
) -> float:
    """しきい値が平均から何σ離れているかを算出する"""
    if std <= 0:
        return float("inf")
    return (threshold - mean) / std


def _calc_first_detection_pct(
    full_rms: np.ndarray, threshold: float,
) -> float:
    """全タイムラインで初めてしきい値を超える地点の寿命%(0-100)を算出する"""
    exceeded = np.where(full_rms > threshold)[0]
    if len(exceeded) == 0:
        return 100.0  # 一度も超えない
    return float(exceeded[0] / len(full_rms) * 100)


def compare_methods(
    results: list[EvaluationResult],
) -> pd.DataFrame:
    """全手法の評価結果を横並び比較DataFrameにする

    Args:
        results: EvaluationResultのリスト

    Returns:
        比較テーブル（DataFarme）
    """
    rows = []
    for r in results:
        rows.append({
            "dataset": r.dataset,
            "method": r.method,
            "sigma_caution": r.sigma_caution,
            "sigma_warning": r.sigma_warning,
            "sigma_danger": r.sigma_danger,
            "false_alarm_%": r.false_alarm_rate,
            "detection_%": r.detection_rate_late,
            "first_detect_%": r.first_detection_pct,
        })
    df = pd.DataFrame(rows)
    # データセット→手法の順でソート
    df = df.sort_values(["dataset", "method"]).reset_index(drop=True)
    return df


def select_recommended(
    results: list[EvaluationResult],
) -> str:
    """最適手法を選定する

    基準: 誤報率5%未満 → 検出率最大 → σ距離最大

    Args:
        results: 同一データセットのEvaluationResultリスト

    Returns:
        推奨手法名
    """
    # 誤報率5%未満のものをフィルタ
    candidates = [r for r in results if r.false_alarm_rate < 5.0]
    if not candidates:
        # 全て5%超なら誤報率最小のものを選ぶ
        candidates = sorted(results, key=lambda r: r.false_alarm_rate)
        return candidates[0].method

    # 検出率最大 → σ距離最大で選択
    best = max(
        candidates,
        key=lambda r: (r.detection_rate_late, r.sigma_caution),
    )
    return best.method
