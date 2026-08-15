"""
工程異常検知モジュール

2つの手法を組み合わせて異常を検出する：
  1. Isolation Forest : 多変量の異常スコア計算（ML手法）
  2. 3σ法            : 統計的しきい値チェック（製造現場でなじみのある手法）

両手法の結果を比較できるため、「MLモデルと現場ルールはここが違う」
という説明がクライアントへの提案時にしやすい。
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from logger_config import get_logger

logger = get_logger(__name__)

# 異常検知に使うセンサーカラム名
FEATURE_COLS: list[str] = ['temperature', 'pressure', 'vibration']


@dataclass
class DetectionResult:
    """検知結果をまとめて保持するデータクラス。"""
    df: pd.DataFrame                         # 予測結果カラムを追加した元データ
    if_anomaly_count: int = 0                # Isolation Forest が検知した異常件数
    sigma_anomaly_count: int = 0             # 3σ法が検知した異常件数
    both_anomaly_count: int = 0              # 両手法が一致して検知した件数
    precision_if: float | None = None        # Isolation Forest の適合率（ラベルあり時）
    recall_if: float | None = None           # Isolation Forest の再現率（ラベルあり時）
    precision_sigma: float | None = None     # 3σ法の適合率（ラベルあり時）
    recall_sigma: float | None = None        # 3σ法の再現率（ラベルあり時）
    thresholds: dict[str, dict] = field(default_factory=dict)  # 3σ法のしきい値


def fit_isolation_forest(
    df: pd.DataFrame,
    contamination: float = 0.05,
    random_state: int = 42
) -> tuple[IsolationForest, StandardScaler]:
    """Isolation Forest モデルを学習する。

    正常データ（is_anomaly == 0）だけを使って学習することで、
    「正常の形」を覚えさせる。

    Args:
        df: センサーデータ（is_anomaly カラムあり）
        contamination: 学習データに含まれる異常の割合の想定
        random_state: 乱数シード

    Returns:
        学習済みモデル と StandardScaler のタプル
    """
    # 正常データだけで学習（教師なし学習の前処理として）
    train_df = df[df['is_anomaly'] == 0][FEATURE_COLS] if 'is_anomaly' in df.columns else df[FEATURE_COLS]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train_df)

    model = IsolationForest(contamination=contamination, random_state=random_state, n_estimators=200)
    model.fit(X_train)

    logger.info(f'Isolation Forest 学習完了 — 学習件数: {len(X_train)}件 / contamination: {contamination}')
    return model, scaler


def predict_isolation_forest(
    df: pd.DataFrame,
    model: IsolationForest,
    scaler: StandardScaler
) -> pd.DataFrame:
    """Isolation Forest で異常スコアと予測ラベルを付与する。

    Args:
        df: センサーデータ
        model: 学習済みモデル
        scaler: 学習時と同じスケーラー

    Returns:
        if_score（異常スコア）と if_pred（0/1）を追加した DataFrame
    """
    df = df.copy()
    X = scaler.transform(df[FEATURE_COLS])

    # score_samples は負値で、小さいほど異常らしい → 反転して「異常スコア」にする
    df['if_score'] = -model.score_samples(X)
    # predict は -1（異常）/ 1（正常） → 0/1 に変換
    df['if_pred'] = (model.predict(X) == -1).astype(int)

    count = int(df['if_pred'].sum())
    logger.info(f'Isolation Forest 予測完了 — 検知件数: {count}件')
    return df


def calc_sigma_thresholds(df: pd.DataFrame) -> dict[str, dict]:
    """正常データの平均・標準偏差から 3σ しきい値を計算する。

    Args:
        df: センサーデータ（is_anomaly カラムあり）

    Returns:
        {カラム名: {mean, std, upper, lower}} の辞書
    """
    normal_df = df[df['is_anomaly'] == 0] if 'is_anomaly' in df.columns else df
    thresholds: dict[str, dict] = {}

    for col in FEATURE_COLS:
        mean = float(normal_df[col].mean())
        std  = float(normal_df[col].std())
        thresholds[col] = {
            'mean':  mean,
            'std':   std,
            'upper': mean + 3 * std,
            'lower': mean - 3 * std,
        }
        logger.info(f'3σしきい値 [{col}]: {thresholds[col]["lower"]:.3f} 〜 {thresholds[col]["upper"]:.3f}')

    return thresholds


def predict_sigma(
    df: pd.DataFrame,
    thresholds: dict[str, dict]
) -> pd.DataFrame:
    """3σ法で異常ラベルを付与する。

    いずれか1つのセンサーでもしきい値を超えたら異常とする。

    Args:
        df: センサーデータ
        thresholds: calc_sigma_thresholds の結果

    Returns:
        sigma_pred（0/1）を追加した DataFrame
    """
    df = df.copy()
    is_out = pd.Series(False, index=df.index)

    for col, t in thresholds.items():
        is_out |= (df[col] > t['upper']) | (df[col] < t['lower'])

    df['sigma_pred'] = is_out.astype(int)

    count = int(df['sigma_pred'].sum())
    logger.info(f'3σ法 予測完了 — 検知件数: {count}件')
    return df


def calc_metrics(
    y_true: pd.Series,
    y_pred: pd.Series
) -> tuple[float, float]:
    """適合率（Precision）と再現率（Recall）を計算する。

    Args:
        y_true: 正解ラベル
        y_pred: 予測ラベル

    Returns:
        (precision, recall) のタプル
    """
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def detect(df: pd.DataFrame, contamination: float = 0.05) -> DetectionResult:
    """2手法で異常検知を実行し、結果をまとめて返す。

    Args:
        df: センサーデータ（is_anomaly カラムは任意）
        contamination: Isolation Forest の汚染率パラメータ

    Returns:
        DetectionResult オブジェクト
    """
    has_label = 'is_anomaly' in df.columns

    # ── Isolation Forest ──
    model, scaler = fit_isolation_forest(df, contamination)
    df = predict_isolation_forest(df, model, scaler)

    # ── 3σ法 ──
    thresholds = calc_sigma_thresholds(df)
    df = predict_sigma(df, thresholds)

    # ── 両手法が一致した異常 ──
    df['both_pred'] = ((df['if_pred'] == 1) & (df['sigma_pred'] == 1)).astype(int)

    result = DetectionResult(
        df=df,
        if_anomaly_count=int(df['if_pred'].sum()),
        sigma_anomaly_count=int(df['sigma_pred'].sum()),
        both_anomaly_count=int(df['both_pred'].sum()),
        thresholds=thresholds,
    )

    # ラベルがあれば精度評価もする
    if has_label:
        result.precision_if, result.recall_if = calc_metrics(df['is_anomaly'], df['if_pred'])
        result.precision_sigma, result.recall_sigma = calc_metrics(df['is_anomaly'], df['sigma_pred'])
        logger.info(f'Isolation Forest — Precision: {result.precision_if:.3f} / Recall: {result.recall_if:.3f}')
        logger.info(f'3σ法           — Precision: {result.precision_sigma:.3f} / Recall: {result.recall_sigma:.3f}')

    return result
