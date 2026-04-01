"""
FEMTO/PRONOSTIA ベアリングデータ — 特徴量抽出
各スナップショットから統計特徴量＋エンベロープRMSを計算する

特徴量:
- RMS（二乗平均平方根）
- Kurtosis（尖度）
- Crest Factor（波高率）
- Envelope RMS（エンベロープ解析のRMS — 複合損傷検出に有効）
- Skewness（歪度）
- FFT Energy（周波数エネルギー）
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.signal import hilbert

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
REPO_DIR = DATA_DIR / "repo"
LEARNING_DIR = REPO_DIR / "Learning_set"


def load_snapshot(csv_path: Path) -> np.ndarray | None:
    """1スナップショット（CSV）を読み込む

    列構造: 時, 分, 秒, μ秒, 水平振動, 垂直振動（ヘッダーなし）
    """
    try:
        data = pd.read_csv(csv_path, header=None).values
        # 列5,6（0始まり4,5）が水平・垂直振動
        vibration = data[:, 4:6].astype(float)
        return vibration
    except Exception as e:
        logger.warning(f"読み込みスキップ: {csv_path.name} ({e})")
        return None


def compute_envelope_rms(signal: np.ndarray) -> float:
    """ヒルベルト変換によるエンベロープRMSを計算する

    複合損傷ではエンベロープ解析が衝撃成分の検出に有効
    """
    analytic = hilbert(signal)
    envelope = np.abs(analytic)
    return float(np.sqrt(np.mean(envelope ** 2)))


def compute_features(signal: np.ndarray) -> dict[str, float]:
    """1チャンネル信号から統計特徴量を抽出する"""
    rms = float(np.sqrt(np.mean(signal ** 2)))
    peak = float(np.max(np.abs(signal)))
    kurtosis = float(sp_stats.kurtosis(signal))
    skewness = float(sp_stats.skew(signal))
    crest_factor = float(peak / rms) if rms > 0 else 0.0
    envelope_rms = compute_envelope_rms(signal)

    # 周波数領域
    fft_vals = np.abs(np.fft.fft(signal))[:len(signal) // 2]
    fft_energy = float(np.sum(fft_vals ** 2))

    return {
        'rms': rms,
        'kurtosis': kurtosis,
        'crest_factor': crest_factor,
        'envelope_rms': envelope_rms,
        'skewness': skewness,
        'fft_energy': fft_energy,
    }


def extract_bearing_features(bearing_dir: Path) -> pd.DataFrame:
    """1ベアリングの全スナップショットから特徴量を抽出する"""
    csv_files = sorted(bearing_dir.glob("acc_*.csv"))
    if not csv_files:
        logger.warning(f"CSVなし: {bearing_dir}")
        return pd.DataFrame()

    records: list[dict] = []
    for idx, csv_path in enumerate(csv_files):
        data = load_snapshot(csv_path)
        if data is None:
            continue

        # 水平・垂直それぞれの特徴量
        h_feat = compute_features(data[:, 0])
        v_feat = compute_features(data[:, 1])

        record: dict[str, float | int | str] = {
            'snapshot_idx': idx,
            'filename': csv_path.name,
        }
        for key, val in h_feat.items():
            record[f'h_{key}'] = val
        for key, val in v_feat.items():
            record[f'v_{key}'] = val

        records.append(record)

    df = pd.DataFrame(records)
    logger.info(f"  {bearing_dir.name}: {len(df)}スナップショット抽出")
    return df


def extract_all_training() -> dict[str, pd.DataFrame]:
    """訓練データ全ベアリングの特徴量を抽出する"""
    all_data: dict[str, pd.DataFrame] = {}

    for bearing_dir in sorted(LEARNING_DIR.iterdir()):
        if not bearing_dir.is_dir() or 'Bearing' not in bearing_dir.name:
            continue
        df = extract_bearing_features(bearing_dir)
        if not df.empty:
            all_data[bearing_dir.name] = df

    return all_data


def save_features(
    all_data: dict[str, pd.DataFrame],
    output_dir: Path,
) -> None:
    """特徴量をCSVに保存する"""
    output_dir.mkdir(exist_ok=True)
    for bearing_name, df in all_data.items():
        csv_path = output_dir / f"features_{bearing_name}.csv"
        df.to_csv(csv_path, index=False)
    logger.info(f"特徴量CSV保存完了: {output_dir}")


def main() -> None:
    """特徴量抽出の全工程を実行する"""
    logger.info("=== FEMTO 特徴量抽出開始 ===")

    all_data = extract_all_training()
    if not all_data:
        logger.error("データなし。download_data.pyを先に実行してください。")
        return

    feature_dir = DATA_DIR / "features"
    save_features(all_data, feature_dir)

    logger.info("=== 特徴量抽出完了 ===")


if __name__ == "__main__":
    main()
