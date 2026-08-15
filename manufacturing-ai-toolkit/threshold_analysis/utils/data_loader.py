"""
4データセット（CWRU・NASA・XJTU-SY・FEMTO）のデータ読み込み共通モジュール

正常データと全データを統一的なインターフェースで提供する
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# プロジェクトルートからの相対パス
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CWRU_FEATURES = BASE_DIR / "bearing_analysis" / "data" / "features.csv"
NASA_FEATURES = BASE_DIR / "nasa_bearing" / "data" / "features.csv"
XJTU_DIR = BASE_DIR / "xjtu_sy_bearing" / "data" / "features"
FEMTO_DIR = BASE_DIR / "femto_bearing" / "data" / "features"

# 正常区間の割合（Run-to-failureデータセット用）
NORMAL_RATIO = 0.20

# データセットごとの特徴量カラム
CWRU_FEATURE_COLS = [
    "rms", "peak", "mean", "std", "kurtosis",
    "skewness", "crest_factor", "mean_freq", "fft_energy", "peak_freq",
]
NASA_FEATURE_COLS = CWRU_FEATURE_COLS  # 同一構造

XJTU_FEATURE_COLS = [
    "h_rms", "h_kurtosis", "h_crest_factor",
    "h_peak_to_peak", "h_skewness", "h_fft_energy",
    "v_rms", "v_kurtosis", "v_crest_factor",
    "v_peak_to_peak", "v_skewness", "v_fft_energy",
]

FEMTO_FEATURE_COLS = [
    "h_rms", "h_kurtosis", "h_crest_factor",
    "h_envelope_rms", "h_skewness", "h_fft_energy",
    "v_rms", "v_kurtosis", "v_crest_factor",
    "v_envelope_rms", "v_skewness", "v_fft_energy",
]


def get_feature_columns(dataset_name: str) -> list[str]:
    """データセット名から特徴量カラムリストを返す

    Args:
        dataset_name: "cwru", "nasa", "xjtu_sy", "femto"

    Returns:
        特徴量カラム名のリスト
    """
    mapping = {
        "cwru": CWRU_FEATURE_COLS,
        "nasa": NASA_FEATURE_COLS,
        "xjtu_sy": XJTU_FEATURE_COLS,
        "femto": FEMTO_FEATURE_COLS,
    }
    if dataset_name not in mapping:
        raise ValueError(f"未対応データセット: {dataset_name}")
    return mapping[dataset_name]


def get_rms_columns(dataset_name: str) -> list[str]:
    """データセット名からRMS列名リストを返す

    Args:
        dataset_name: データセット名

    Returns:
        RMS列名のリスト
    """
    if dataset_name in ("cwru", "nasa"):
        return ["rms"]
    return ["h_rms", "v_rms"]


def load_cwru() -> tuple[pd.DataFrame, pd.DataFrame]:
    """CWRUデータセットを読み込む（明示ラベルで正常/異常分離）

    Returns:
        (正常データDF, 全データDF)
    """
    df = pd.read_csv(CWRU_FEATURES)
    normal_df = df[df["label"] == 0].reset_index(drop=True)
    logger.info(f"CWRU: 全{len(df)}件, 正常{len(normal_df)}件")
    return normal_df, df


def load_nasa() -> tuple[pd.DataFrame, pd.DataFrame]:
    """NASAデータセットを読み込む（先頭20%を正常区間）

    Returns:
        (正常データDF, 全データDF)
    """
    df = pd.read_csv(NASA_FEATURES)
    df = df.sort_values("snapshot_idx").reset_index(drop=True)
    cutoff = int(len(df) * NORMAL_RATIO)
    normal_df = df.iloc[:cutoff].reset_index(drop=True)
    logger.info(f"NASA: 全{len(df)}件, 正常{cutoff}件")
    return normal_df, df


def _load_rtf_dir(
    feature_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run-to-failureデータセットのディレクトリを読み込む

    各ベアリングの先頭20%を正常データとして結合する

    Args:
        feature_dir: 特徴量CSVのディレクトリ

    Returns:
        (正常データDF, 全データDF)
    """
    all_normal = []
    all_full = []
    csv_files = sorted(feature_dir.glob("*.csv"))

    for csv_path in csv_files:
        df = pd.read_csv(csv_path)
        df = df.sort_values("snapshot_idx").reset_index(drop=True)
        # ソースファイル名を保持（ベアリング識別用）
        df["source_file"] = csv_path.stem
        cutoff = int(len(df) * NORMAL_RATIO)
        all_normal.append(df.iloc[:cutoff])
        all_full.append(df)
        logger.info(f"  {csv_path.name}: 全{len(df)}件, 正常{cutoff}件")

    normal_df = pd.concat(all_normal, ignore_index=True)
    full_df = pd.concat(all_full, ignore_index=True)
    return normal_df, full_df


def load_xjtu() -> tuple[pd.DataFrame, pd.DataFrame]:
    """XJTU-SYデータセットを読み込む

    Returns:
        (正常データDF, 全データDF)
    """
    logger.info("XJTU-SY:")
    normal_df, full_df = _load_rtf_dir(XJTU_DIR)
    logger.info(f"XJTU-SY合計: 全{len(full_df)}件, 正常{len(normal_df)}件")
    return normal_df, full_df


def load_femto() -> tuple[pd.DataFrame, pd.DataFrame]:
    """FEMTOデータセットを読み込む

    Returns:
        (正常データDF, 全データDF)
    """
    logger.info("FEMTO:")
    normal_df, full_df = _load_rtf_dir(FEMTO_DIR)
    logger.info(f"FEMTO合計: 全{len(full_df)}件, 正常{len(normal_df)}件")
    return normal_df, full_df


def load_dataset(
    dataset_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """指定データセットの正常データと全データを返す

    Args:
        dataset_name: "cwru", "nasa", "xjtu_sy", "femto"

    Returns:
        (正常データDF, 全データDF)
    """
    loaders = {
        "cwru": load_cwru,
        "nasa": load_nasa,
        "xjtu_sy": load_xjtu,
        "femto": load_femto,
    }
    if dataset_name not in loaders:
        raise ValueError(f"未対応データセット: {dataset_name}")
    return loaders[dataset_name]()


def extract_rms(df: pd.DataFrame, dataset_name: str) -> np.ndarray:
    """DataFrameからRMS値を抽出する（複数チャネルは平均化）

    Args:
        df: データフレーム
        dataset_name: データセット名

    Returns:
        RMS値のnumpy配列
    """
    rms_cols = get_rms_columns(dataset_name)
    return df[rms_cols].mean(axis=1).values


# 全データセット名のリスト
ALL_DATASETS = ["cwru", "nasa", "xjtu_sy", "femto"]
