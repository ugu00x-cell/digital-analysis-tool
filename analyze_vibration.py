# -*- coding: utf-8 -*-
"""
振動データ解析パイプライン + Slack通知

改善内容:
  1. Slack WebhookURLを環境変数から読み込み
  2. CSVファイルをコマンドライン引数で指定可能
  3. エラー発生時もSlackにエラー通知を送信
  4. ログ出力をloggingモジュールに統一
"""

import argparse
import glob
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal

# ── ログ設定 ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── 定数 ──────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.expanduser("~"), "vibration_data")
FS = 500
SEGMENT_SEC = 1.0
SEGMENT_LEN = int(FS * SEGMENT_SEC)
THRESHOLD = 3.0


# ════════════════════════════════════════════════════════════
# Slack通知
# ════════════════════════════════════════════════════════════


def _get_webhook_url() -> str:
    """環境変数からSlack WebhookURLを取得する。

    Returns:
        str: WebhookURL（未設定の場合は空文字）
    """
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        logger.warning(
            "環境変数 SLACK_WEBHOOK_URL が未設定です。"
            "Slack通知はスキップされます。"
        )
    return url


def send_slack(text: str, color: str = "good") -> None:
    """Slackにメッセージを送信する。

    Args:
        text: 送信するメッセージ本文
        color: 添付カラー（good=緑 / warning=黄 / danger=赤）
    """
    webhook_url = _get_webhook_url()
    if not webhook_url:
        return

    payload = {
        "attachments": [
            {
                "color": color,
                "text": text,
                "mrkdwn_in": ["text"],
            }
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack通知を送信しました")
    except Exception as e:
        logger.error(f"Slack送信失敗: {e}")


def send_slack_error(error_msg: str) -> None:
    """エラー発生時にSlackへエラー通知を送る。

    Args:
        error_msg: エラーメッセージ
    """
    text = (
        f":rotating_light: *解析エラー*\n"
        f"```{error_msg}```"
    )
    send_slack(text, color="danger")


# ════════════════════════════════════════════════════════════
# CSV読み込み
# ════════════════════════════════════════════════════════════


def load_csv(file_path: str) -> tuple:
    """指定されたCSVファイルを読み込む。

    Args:
        file_path: CSVファイルの絶対パス

    Returns:
        tuple: (DataFrame, ファイル名)

    Raises:
        FileNotFoundError: ファイルが存在しない場合
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"CSVファイルが見つかりません: {file_path}"
        )
    logger.info(f"読み込み: {os.path.basename(file_path)}")
    df = pd.read_csv(file_path)
    df["timestamp_s"] = df["timestamp_us"] / 1e6
    logger.info(
        f"  行数: {len(df)} / 時間: {len(df) / FS:.1f}秒"
    )
    return df, os.path.basename(file_path)


def load_latest_csv(data_dir: str) -> tuple:
    """指定ディレクトリから最新のCSVファイルを読み込む。

    Args:
        data_dir: CSVファイルが格納されたディレクトリ

    Returns:
        tuple: (DataFrame, ファイル名)

    Raises:
        FileNotFoundError: CSVファイルが1つもない場合
    """
    files = sorted(
        glob.glob(os.path.join(data_dir, "vibration_*.csv"))
    )
    if not files:
        raise FileNotFoundError(
            f"CSVが見つかりません: {data_dir}"
        )
    return load_csv(files[-1])


# ════════════════════════════════════════════════════════════
# 解析関数
# ════════════════════════════════════════════════════════════


def preprocess(df: pd.DataFrame, axis: str = "az") -> np.ndarray:
    """前処理: 平均除去＋クリッピング。

    Args:
        df: 振動データのDataFrame
        axis: 解析対象の軸名

    Returns:
        np.ndarray: 前処理済みデータ
    """
    x = df[axis].values.astype(np.float64)
    x = x - np.mean(x)
    std = np.std(x)
    x = np.clip(x, -5 * std, 5 * std)
    return x


def compute_fft(
    x: np.ndarray, fs: int
) -> tuple:
    """FFTスペクトルを計算する。

    Args:
        x: 時系列データ
        fs: サンプリング周波数

    Returns:
        tuple: (周波数配列, 振幅配列)
    """
    n = len(x)
    win = np.hanning(n)
    freq = np.fft.rfftfreq(n, d=1 / fs)
    amp = np.abs(np.fft.rfft(x * win)) * 2 / n
    return freq, amp


def envelope_analysis(
    x: np.ndarray,
    fs: int,
    band_low: float = 50.0,
    band_high: float = None,
) -> tuple:
    """エンベロープ解析を実行する。

    Args:
        x: 時系列データ
        fs: サンプリング周波数
        band_low: バンドパスフィルタ下限周波数
        band_high: バンドパスフィルタ上限周波数

    Returns:
        tuple: (エンベロープ信号, 周波数配列, 振幅配列)
    """
    if band_high is None:
        band_high = fs / 2 * 0.9
    sos = signal.butter(
        4, [band_low, band_high],
        btype="bandpass", fs=fs, output="sos",
    )
    xf = signal.sosfilt(sos, x)
    env = np.abs(signal.hilbert(xf))
    env = env - np.mean(env)
    freq, amp = compute_fft(env, fs)
    return env, freq, amp


def compute_scores(
    x: np.ndarray, segment_len: int
) -> dict:
    """セグメントごとのRMS・ピーク・Zスコアを計算する。

    Args:
        x: 時系列データ
        segment_len: セグメント長（サンプル数）

    Returns:
        dict: rms, peak, cf, z_score, mean_rms, std_rms

    Raises:
        ValueError: データが短すぎる場合
    """
    n_segments = len(x) // segment_len
    if n_segments == 0:
        raise ValueError(
            f"データが短すぎます。"
            f"{segment_len}サンプル以上必要です。"
        )
    rms_list, peak_list, cf_list = [], [], []
    for i in range(n_segments):
        seg = x[i * segment_len : (i + 1) * segment_len]
        rms = np.sqrt(np.mean(seg**2))
        peak = np.max(np.abs(seg))
        rms_list.append(rms)
        peak_list.append(peak)
        cf_list.append(peak / (rms + 1e-10))
    rms_arr = np.array(rms_list)
    mean_rms = np.mean(rms_arr)
    std_rms = np.std(rms_arr)
    return {
        "rms": rms_arr,
        "peak": np.array(peak_list),
        "cf": np.array(cf_list),
        "z_score": (rms_arr - mean_rms) / (std_rms + 1e-10),
        "mean_rms": mean_rms,
        "std_rms": std_rms,
    }


def plot_results(
    df, x, scores, freq_fft, amp_fft,
    env_freq, env_amp, save_dir: str,
) -> None:
    """解析結果をプロットして保存する。

    Args:
        df: 元データ
        x: 前処理済みデータ
        scores: スコア辞書
        freq_fft: FFT周波数
        amp_fft: FFT振幅
        env_freq: エンベロープ周波数
        env_amp: エンベロープ振幅
        save_dir: 保存先ディレクトリ
    """
    fig, axes = plt.subplots(4, 1, figsize=(14, 16))
    fig.suptitle("振動データ解析結果", fontsize=14)
    t = np.arange(len(x)) / FS

    # 時系列波形
    axes[0].plot(t, x, linewidth=0.5, color="steelblue")
    axes[0].set(
        xlabel="時間 [s]", ylabel="加速度 [g]",
        title="時系列波形（az軸）",
    )
    axes[0].grid(True, alpha=0.3)

    # FFTスペクトル
    axes[1].plot(
        freq_fft, amp_fft, linewidth=0.8, color="darkorange"
    )
    axes[1].set(
        xlabel="周波数 [Hz]", ylabel="振幅 [g]",
        title="FFTスペクトル", xlim=(0, FS / 2),
    )
    axes[1].grid(True, alpha=0.3)

    # エンベロープスペクトル
    axes[2].plot(
        env_freq, env_amp, linewidth=0.8, color="green"
    )
    axes[2].set(
        xlabel="周波数 [Hz]", ylabel="振幅 [g]",
        title="エンベロープスペクトル", xlim=(0, FS / 4),
    )
    axes[2].grid(True, alpha=0.3)

    # Zスコア
    seg_t = np.arange(len(scores["rms"])) * SEGMENT_SEC
    axes[3].plot(
        seg_t, scores["z_score"],
        marker="o", color="crimson", linewidth=1.5,
    )
    axes[3].axhline(
        THRESHOLD, color="red", linestyle="--",
        label=f"閾値 +{THRESHOLD}σ",
    )
    axes[3].axhline(
        -THRESHOLD, color="red", linestyle="--",
    )
    axes[3].axhline(0, color="gray", linestyle="-", alpha=0.5)
    axes[3].set(
        xlabel="時間 [s]", ylabel="Zスコア",
        title="RMS異常スコア",
    )
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(save_dir, "analysis_result.png")
    plt.savefig(out_path, dpi=150)
    logger.info(f"プロット保存: {out_path}")
    plt.show()


# ════════════════════════════════════════════════════════════
# 引数パーサー
# ════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Returns:
        argparse.Namespace: 解析済み引数
    """
    parser = argparse.ArgumentParser(
        description="振動データ解析パイプライン"
    )
    parser.add_argument(
        "csv_file",
        nargs="?",
        default=None,
        help=(
            "解析対象のCSVファイルパス "
            "(未指定時はDATA_DIRの最新ファイル)"
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=DATA_DIR,
        help=f"CSVファイル格納ディレクトリ (default: {DATA_DIR})",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="プロット表示を無効にする",
    )
    return parser.parse_args()


# ════════════════════════════════════════════════════════════
# メイン
# ════════════════════════════════════════════════════════════


def main() -> None:
    """メイン処理。解析→判定→Slack通知を実行する。"""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("振動データ解析パイプライン 開始")
    logger.info("=" * 60)

    try:
        # ── CSV読み込み ──────────────────────────────────────
        if args.csv_file:
            df, filename = load_csv(args.csv_file)
        else:
            df, filename = load_latest_csv(args.data_dir)

        # ── 前処理 ──────────────────────────────────────────
        x = preprocess(df, axis="az")
        rms_total = np.sqrt(np.mean(x**2))
        logger.info(
            f"前処理完了: サンプル数={len(x)} / "
            f"RMS={rms_total:.4f} g"
        )

        # ── FFT ─────────────────────────────────────────────
        freq_fft, amp_fft = compute_fft(x, FS)
        peak_freq = freq_fft[np.argmax(amp_fft)]
        logger.info(f"FFTピーク周波数: {peak_freq:.1f} Hz")

        # ── エンベロープ解析 ────────────────────────────────
        env, env_freq, env_amp = envelope_analysis(x, FS)
        env_peak_freq = env_freq[np.argmax(env_amp)]
        logger.info(
            f"エンベロープピーク周波数: {env_peak_freq:.1f} Hz"
        )

        # ── スコア計算 ──────────────────────────────────────
        scores = compute_scores(x, SEGMENT_LEN)
        anomaly = np.any(
            np.abs(scores["z_score"]) > THRESHOLD
        )
        max_z = float(np.max(np.abs(scores["z_score"])))
        logger.info(
            f"RMS平均: {scores['mean_rms']:.4f} g / "
            f"最大Zスコア: {max_z:.2f}"
        )
        logger.info(
            f"判定: {'異常検出' if anomaly else '正常'}"
        )

        # ── Slack通知 ───────────────────────────────────────
        if anomaly:
            msg = (
                f":warning: *異常検出*\n"
                f"ファイル: `{filename}`\n"
                f"最大Zスコア: `{max_z:.2f}` "
                f"(閾値: {THRESHOLD})\n"
                f"RMS: `{rms_total:.4f} g` / "
                f"ピーク周波数: `{peak_freq:.1f} Hz`"
            )
            send_slack(msg, color="danger")
        else:
            msg = (
                f":white_check_mark: *正常*\n"
                f"ファイル: `{filename}`\n"
                f"最大Zスコア: `{max_z:.2f}` "
                f"(閾値: {THRESHOLD})\n"
                f"RMS: `{rms_total:.4f} g` / "
                f"ピーク周波数: `{peak_freq:.1f} Hz`"
            )
            send_slack(msg, color="good")

        # ── プロット ────────────────────────────────────────
        if not args.no_plot:
            save_dir = (
                os.path.dirname(args.csv_file)
                if args.csv_file
                else args.data_dir
            )
            plot_results(
                df, x, scores, freq_fft, amp_fft,
                env_freq, env_amp, save_dir,
            )

    except Exception as e:
        logger.error(f"解析エラー: {e}")
        send_slack_error(str(e))
        raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("中断されました")
    except Exception:
        # main() 内で既にログ出力・Slack通知済み
        sys.exit(1)
