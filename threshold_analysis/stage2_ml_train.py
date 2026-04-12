"""
Stage 2: 機械学習ベースのしきい値算出（学習モジュール）

IsolationForest と One-Class SVM を正常データのみで学習する
"""

import logging

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    get_feature_columns,
    load_dataset,
)

logger = logging.getLogger(__name__)

# MLモデルの型エイリアス
AnomalyModel = IsolationForest | OneClassSVM


def train_isolation_forest(
    normal_features: np.ndarray,
    contamination: float = 0.01,
    n_estimators: int = 200,
    random_state: int = 42,
) -> tuple[IsolationForest, StandardScaler]:
    """正常データのみでIsolationForestを学習する

    Args:
        normal_features: 正常データの特徴量配列 (n_samples, n_features)
        contamination: 正常データ中の想定汚染率
        n_estimators: 決定木の数
        random_state: 乱数シード

    Returns:
        (学習済みモデル, 学習済みスケーラー)
    """
    scaler = StandardScaler()
    scaled = scaler.fit_transform(normal_features)

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    )
    model.fit(scaled)

    logger.info(
        f"[IF] 学習完了: {normal_features.shape[0]}サンプル, "
        f"{normal_features.shape[1]}特徴量"
    )
    return model, scaler


def train_ocsvm(
    normal_features: np.ndarray,
    kernel: str = "rbf",
    nu: float = 0.01,
    gamma: str = "scale",
) -> tuple[OneClassSVM, StandardScaler]:
    """正常データのみでOne-Class SVMを学習する

    Args:
        normal_features: 正常データの特徴量配列 (n_samples, n_features)
        kernel: カーネル関数
        nu: 異常率の上界パラメータ
        gamma: カーネル係数

    Returns:
        (学習済みモデル, 学習済みスケーラー)
    """
    scaler = StandardScaler()
    scaled = scaler.fit_transform(normal_features)

    model = OneClassSVM(kernel=kernel, nu=nu, gamma=gamma)
    model.fit(scaled)

    logger.info(
        f"[OCSVM] 学習完了: {normal_features.shape[0]}サンプル, "
        f"{normal_features.shape[1]}特徴量"
    )
    return model, scaler


def get_anomaly_scores(
    model: AnomalyModel,
    scaler: StandardScaler,
    features: np.ndarray,
) -> np.ndarray:
    """学習済みモデルで異常スコアを算出する

    IsolationForest: score_samples() → 負値ほど異常
    OneClassSVM: decision_function() → 負値ほど異常
    どちらも「小さい値ほど異常」に統一する

    Args:
        model: 学習済み異常検知モデル
        scaler: 学習済みスケーラー
        features: スコア算出対象の特徴量配列

    Returns:
        異常スコア配列（小さいほど異常）
    """
    scaled = scaler.transform(features)

    if isinstance(model, IsolationForest):
        # score_samples: 負値ほど異常
        scores = model.score_samples(scaled)
    else:
        # decision_function: 負値ほど異常
        scores = model.decision_function(scaled)

    return scores


def run_stage2_train(
    dataset_name: str,
) -> dict[str, tuple[AnomalyModel, StandardScaler]]:
    """指定データセットでIF・OCSVMを学習する

    Args:
        dataset_name: データセット名

    Returns:
        {"if": (model, scaler), "ocsvm": (model, scaler)}
    """
    logger.info(f"=== Stage2 Train: {dataset_name} ===")
    normal_df, _ = load_dataset(dataset_name)
    feature_cols = get_feature_columns(dataset_name)
    normal_features = normal_df[feature_cols].values

    if_model, if_scaler = train_isolation_forest(normal_features)
    ocsvm_model, ocsvm_scaler = train_ocsvm(normal_features)

    return {
        "if": (if_model, if_scaler),
        "ocsvm": (ocsvm_model, ocsvm_scaler),
    }


def run_stage2_train_all() -> dict[str, dict[str, tuple]]:
    """4データセット全てでモデルを学習する

    Returns:
        {データセット名: {"if": (model, scaler), "ocsvm": (model, scaler)}}
    """
    results = {}
    for ds in ALL_DATASETS:
        results[ds] = run_stage2_train(ds)
    return results
