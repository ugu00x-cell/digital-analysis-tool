"""
XJTU-SYベアリングデータ — 特徴量抽出
各スナップショット（CSV）から統計特徴量を計算し、時系列データフレームを生成する

特徴量:
- RMS（二乗平均平方根）
- Kurtosis（尖度）
- Crest Factor（波高率）
- Peak-to-Peak（実効値）
- Skewness（歪度）
- FFT Energy（周波数エネルギー）
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 定数
SAMPLING_RATE = 25600  # 25.6kHz
DATA_DIR = Path(__file__).parent / "data"


def load_snapshot(csv_path: Path) -> np.ndarray | None:
    """1スナップショット（CSV）を読み込む（2列: 水平, 垂直）

    ヘッダー: Horizontal_vibration_signals, Vertical_vibration_signals
    """
    try:
        # ヘッダーあり（Horizontal_vibration_signals, Vertical_vibration_signals）
        data = pd.read_csv(csv_path).values
        if data.shape[1] < 2:
            logger.warning(f"列数不足: {csv_path.name} ({data.shape})")
            return None
        return data
    except Exception as e:
        logger.warning(f"読み込みスキップ: {csv_path.name} ({e})")
        return None


def compute_features(signal: np.ndarray) -> dict[str, float]:
    """1チャンネル信号から統計特徴量を抽出する"""
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(np.abs(signal)))
    kurtosis = float(sp_stats.kurtosis(signal))
    skewness = float(sp_stats.skew(signal))
    crest_factor = float(peak / rms) if rms > 0 else 0.0
    peak_to_peak = float(np.max(signal) - np.min(signal))

    # 周波数領域の特徴量
    fft_vals = np.abs(np.fft.fft(signal))[:len(signal) // 2]
    fft_energy = float(np.sum(fft_vals ** 2))

    return {
        'rms': rms,
        'kurtosis': kurtosis,
        'crest_factor': crest_factor,
        'peak_to_peak': peak_to_peak,
        'skewness': skewness,
        'fft_energy': fft_energy,
    }


def extract_bearing_features(bearing_dir: Path) -> pd.DataFrame:
    """1ベアリングの全スナップショットから特徴量を抽出する"""
    # ファイル名が数値（1.csv, 2.csv, ...）なので数値順にソート
    csv_files = sorted(
        bearing_dir.glob("*.csv"),
        key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem
    )
    if not csv_files:
        logger.warning(f"CSVなし: {bearing_dir}")
        return pd.DataFrame()

    records: list[dict] = []
    for idx, csv_path in enumerate(csv_files):
        data = load_snapshot(csv_path)
        if data is None:
            continue

        # 水平・垂直それぞれの特徴量を計算
        h_features = compute_features(data[:, 0])
        v_features = compute_features(data[:, 1])

        record: dict[str, float | int | str] = {
            'snapshot_idx': idx,
            'filename': csv_path.name,
        }
        # 水平（horizontal）の特徴量
        for key, val in h_features.items():
            record[f'h_{key}'] = val
        # 垂直（vertical）の特徴量
        for key, val in v_features.items():
            record[f'v_{key}'] = val

        records.append(record)

    df = pd.DataFrame(records)
    logger.info(f"  {bearing_dir.name}: {len(df)}スナップショット抽出")
    return df


def extract_all_conditions(data_dir: Path) -> dict[str, dict[str, pd.DataFrame]]:
    """全Condition × 全ベアリングの特徴量を抽出する"""
    from download_data import find_condition_dirs, scan_bearing_structure

    conditions = find_condition_dirs(data_dir)
    if not conditions:
        logger.error("Conditionディレクトリが見つかりません")
        return {}

    all_data: dict[str, dict[str, pd.DataFrame]] = {}
    for cond_name, cond_path in sorted(conditions.items()):
        logger.info(f"=== {cond_name} 特徴量抽出 ===")
        bearing_dirs = scan_bearing_structure(cond_path)
        cond_data: dict[str, pd.DataFrame] = {}

        for bd in bearing_dirs:
            df = extract_bearing_features(bd)
            if not df.empty:
                cond_data[bd.name] = df

        all_data[cond_name] = cond_data

    return all_data


def save_features(
    all_data: dict[str, dict[str, pd.DataFrame]],
    output_dir: Path,
) -> None:
    """特徴量をCSVに保存する"""
    output_dir.mkdir(exist_ok=True)
    for cond_name, cond_data in all_data.items():
        for bearing_name, df in cond_data.items():
            csv_path = output_dir / f"features_{cond_name}_{bearing_name}.csv"
            df.to_csv(csv_path, index=False)
    logger.info(f"特徴量CSV保存完了: {output_dir}")


def main() -> None:
    """特徴量抽出の全工程を実行する"""
    logger.info("=== XJTU-SY 特徴量抽出開始 ===")

    all_data = extract_all_conditions(DATA_DIR)
    if not all_data:
        logger.error("データなし。download_data.pyを先に実行してください。")
        return

    # 特徴量CSV保存
    feature_dir = DATA_DIR / "features"
    save_features(all_data, feature_dir)

    logger.info("=== 特徴量抽出完了 ===")


if __name__ == "__main__":
    main()
