"""
振動データ解析エンジン

analyze_vibration.pyの解析ロジックをAPI用に再構成
FFT・エンベロープ解析・Zスコア異常検知を提供する
"""

import logging

import numpy as np
from scipy import signal

from shared.config import ANOMALY_THRESHOLD, SAMPLING_RATE, SEGMENT_LEN

logger = logging.getLogger(__name__)


def preprocess(values: np.ndarray) -> np.ndarray:
    """前処理: 平均除去 + 5σクリッピング

    Args:
        values: 加速度の生データ配列

    Returns:
        前処理済みデータ
    """
    x = values.astype(np.float64)
    x = x - np.mean(x)
    std = np.std(x)
    if std > 0:
        x = np.clip(x, -5 * std, 5 * std)
    return x


def compute_fft(
    x: np.ndarray, fs: int = SAMPLING_RATE,
) -> tuple[np.ndarray, np.ndarray]:
    """FFTスペクトルを計算する

    Args:
        x: 時系列データ
        fs: サンプリング周波数

    Returns:
        (周波数配列, 振幅配列)
    """
    n = len(x)
    win = np.hanning(n)
    freq = np.fft.rfftfreq(n, d=1 / fs)
    amp = np.abs(np.fft.rfft(x * win)) * 2 / n
    return freq, amp


def envelope_analysis(
    x: np.ndarray,
    fs: int = SAMPLING_RATE,
    band_low: float = 50.0,
    band_high: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """エンベロープ解析を実行する

    Args:
        x: 時系列データ
        fs: サンプリング周波数
        band_low: バンドパスフィルタ下限周波数
        band_high: バンドパスフィルタ上限周波数

    Returns:
        (エンベロープ周波数配列, エンベロープ振幅配列)
    """
    if band_high is None:
        band_high = fs / 2 * 0.9
    # ナイキスト周波数チェック
    nyq = fs / 2
    if band_low >= nyq or band_high >= nyq:
        logger.warning("フィルタ周波数がナイキスト周波数を超えています")
        return np.array([0.0]), np.array([0.0])

    sos = signal.butter(
        4, [band_low, band_high],
        btype="bandpass", fs=fs, output="sos",
    )
    xf = signal.sosfilt(sos, x)
    env = np.abs(signal.hilbert(xf))
    env = env - np.mean(env)
    freq, amp = compute_fft(env, fs)
    return freq, amp


def compute_scores(
    x: np.ndarray, segment_len: int = SEGMENT_LEN,
) -> dict:
    """セグメントごとのRMS・Zスコアを計算する

    Args:
        x: 時系列データ
        segment_len: セグメント長（サンプル数）

    Returns:
        rms, peak, z_score, mean_rms, std_rms を含む辞書

    Raises:
        ValueError: データが短すぎる場合
    """
    n_segments = len(x) // segment_len
    if n_segments == 0:
        raise ValueError(
            f"データ不足: {len(x)}サンプル "
            f"(最低{segment_len}サンプル必要)"
        )

    rms_list = []
    peak_list = []
    for i in range(n_segments):
        seg = x[i * segment_len: (i + 1) * segment_len]
        rms = np.sqrt(np.mean(seg ** 2))
        peak = np.max(np.abs(seg))
        rms_list.append(rms)
        peak_list.append(peak)

    rms_arr = np.array(rms_list)
    mean_rms = float(np.mean(rms_arr))
    std_rms = float(np.std(rms_arr))
    z_scores = (rms_arr - mean_rms) / (std_rms + 1e-10)

    return {
        "rms": rms_arr,
        "peak": np.array(peak_list),
        "z_score": z_scores,
        "mean_rms": mean_rms,
        "std_rms": std_rms,
    }


def analyze(
    z_values: np.ndarray,
    threshold: float = ANOMALY_THRESHOLD,
) -> dict:
    """振動データのZ軸を解析して異常判定する

    Args:
        z_values: Z軸加速度の配列
        threshold: 異常判定しきい値（Zスコア）

    Returns:
        解析結果辞書
    """
    # 前処理
    x = preprocess(z_values)

    # FFT
    freq_fft, amp_fft = compute_fft(x)
    peak_freq = float(freq_fft[np.argmax(amp_fft)])

    # エンベロープ解析
    env_freq, env_amp = envelope_analysis(x)
    env_peak = float(env_freq[np.argmax(env_amp)])

    # スコア計算
    scores = compute_scores(x)
    max_z = float(np.max(np.abs(scores["z_score"])))
    is_anomaly = max_z > threshold

    logger.info(
        f"解析完了: samples={len(z_values)}, "
        f"RMS={scores['mean_rms']:.4f}, "
        f"max_z={max_z:.2f}, anomaly={is_anomaly}"
    )

    return {
        "is_anomaly": is_anomaly,
        "max_z_score": round(max_z, 4),
        "mean_rms": round(scores["mean_rms"], 6),
        "peak_frequency_hz": round(peak_freq, 2),
        "envelope_peak_hz": round(env_peak, 2),
        "threshold": threshold,
        "sample_count": len(z_values),
    }
