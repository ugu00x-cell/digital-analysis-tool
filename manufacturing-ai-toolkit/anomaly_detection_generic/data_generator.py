"""
製造ラインのセンサーデータ生成モジュール

温度・圧力・振動の3センサーを持つ工程データを模倣する。
正常データに対して3種類の異常パターンを人工的に混入する：
  - スパイク異常  : 瞬間的な急上昇
  - ドリフト異常  : 値が徐々にずれていく
  - 固着異常      : センサーが同じ値に張り付く
"""

import logging
import numpy as np
import pandas as pd
from pathlib import Path
from logger_config import get_logger

logger = get_logger(__name__)


# 各センサーの正常時パラメータ（製造現場をイメージ）
SENSOR_CONFIG: dict[str, dict] = {
    'temperature': {'mean': 80.0,  'std': 2.0,  'unit': '℃'},
    'pressure':    {'mean': 5.0,   'std': 0.3,  'unit': 'MPa'},
    'vibration':   {'mean': 0.5,   'std': 0.05, 'unit': 'mm/s'},
}


def generate_normal_data(n_samples: int, seed: int = 42) -> pd.DataFrame:
    """正常時のセンサーデータを生成する。

    Args:
        n_samples: 生成するサンプル数
        seed: 乱数シード（再現性のため）

    Returns:
        timestamp + 各センサー値の DataFrame
    """
    rng = np.random.default_rng(seed)

    timestamps = pd.date_range(start='2024-01-01', periods=n_samples, freq='1min')

    data: dict[str, np.ndarray] = {'timestamp': timestamps}
    for name, cfg in SENSOR_CONFIG.items():
        # 正規分布ノイズ + ゆるやかな周期変動（昼夜温度差など）
        noise   = rng.normal(0, cfg['std'], n_samples)
        cycle   = cfg['std'] * 0.5 * np.sin(2 * np.pi * np.arange(n_samples) / 480)
        data[name] = cfg['mean'] + noise + cycle

    logger.info(f'正常データ生成完了: {n_samples}件')
    return pd.DataFrame(data)


def inject_spike_anomaly(
    df: pd.DataFrame,
    col: str,
    indices: list[int],
    magnitude: float = 5.0
) -> pd.DataFrame:
    """スパイク異常を注入する（瞬間的な急上昇）。

    Args:
        df: 元データ
        col: 異常を注入するカラム名
        indices: 異常を発生させる行インデックスのリスト
        magnitude: 標準偏差の何倍のスパイクを起こすか

    Returns:
        異常注入後の DataFrame
    """
    df = df.copy()
    std = SENSOR_CONFIG[col]['std']
    df.loc[indices, col] += std * magnitude
    logger.info(f'スパイク異常注入: {col} / {len(indices)}箇所')
    return df


def inject_drift_anomaly(
    df: pd.DataFrame,
    col: str,
    start_idx: int,
    end_idx: int,
    drift_total: float = 10.0
) -> pd.DataFrame:
    """ドリフト異常を注入する（値が徐々にずれる）。

    Args:
        df: 元データ
        col: 異常を注入するカラム名
        start_idx: ドリフト開始インデックス
        end_idx: ドリフト終了インデックス
        drift_total: トータルでずれる量

    Returns:
        異常注入後の DataFrame
    """
    df = df.copy()
    length = end_idx - start_idx
    # 線形にドリフトさせる
    drift = np.linspace(0, drift_total, length)
    df.loc[start_idx:end_idx - 1, col] += drift
    logger.info(f'ドリフト異常注入: {col} / インデックス {start_idx}〜{end_idx}')
    return df


def inject_stuck_anomaly(
    df: pd.DataFrame,
    col: str,
    start_idx: int,
    end_idx: int
) -> pd.DataFrame:
    """固着異常を注入する（センサーが同じ値に張り付く）。

    Args:
        df: 元データ
        col: 異常を注入するカラム名
        start_idx: 固着開始インデックス
        end_idx: 固着終了インデックス

    Returns:
        異常注入後の DataFrame
    """
    df = df.copy()
    stuck_value = float(df.loc[start_idx, col])  # 開始時点の値で固定
    df.loc[start_idx:end_idx, col] = stuck_value
    logger.info(f'固着異常注入: {col} / インデックス {start_idx}〜{end_idx} → {stuck_value:.3f}')
    return df


def add_anomaly_label(
    df: pd.DataFrame,
    anomaly_indices: list[int]
) -> pd.DataFrame:
    """正解ラベルを付与する（評価用）。

    Args:
        df: 元データ
        anomaly_indices: 異常とマークするインデックス

    Returns:
        is_anomaly カラムを追加した DataFrame
    """
    df = df.copy()
    df['is_anomaly'] = 0
    df.loc[anomaly_indices, 'is_anomaly'] = 1
    return df


def generate_sample_dataset(
    n_samples: int = 1440,
    output_path: str | None = None,
    seed: int = 42
) -> pd.DataFrame:
    """異常混入済みのサンプルデータセットを生成・保存する。

    1440件 = 1分間隔で24時間分のイメージ。

    Args:
        n_samples: 生成するサンプル数
        output_path: CSV 保存先（None なら保存しない）
        seed: 乱数シード

    Returns:
        異常ラベル付きの DataFrame
    """
    df = generate_normal_data(n_samples, seed)

    # ── 異常を3パターン注入 ──
    # スパイク：温度センサーが数点だけ急上昇
    spike_idx = [200, 201, 650, 651, 1100]
    df = inject_spike_anomaly(df, 'temperature', spike_idx, magnitude=6.0)

    # ドリフト：圧力センサーが300〜400点目にかけて徐々に上昇
    df = inject_drift_anomaly(df, 'pressure', start_idx=700, end_idx=800, drift_total=2.0)

    # 固着：振動センサーが900〜950点目で動かなくなる
    df = inject_stuck_anomaly(df, 'vibration', start_idx=900, end_idx=950)

    # 正解ラベル付与
    drift_range  = list(range(700, 800))
    stuck_range  = list(range(900, 951))
    all_anomalies = spike_idx + drift_range + stuck_range
    df = add_anomaly_label(df, all_anomalies)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f'データセット保存: {output_path}')

    logger.info(f'データセット完成 — 正常: {(df.is_anomaly == 0).sum()}件 / 異常: {(df.is_anomaly == 1).sum()}件')
    return df
