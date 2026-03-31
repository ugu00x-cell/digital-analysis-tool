"""
CWRUベアリング振動データ ダウンロード＆CSV変換
公式サイトから.matファイルを取得し、Drive-End加速度をCSVに保存する
"""

import logging
import urllib.request
from pathlib import Path
import numpy as np
from scipy import io as sio

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

# データ保存先
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# CWRUデータセットURL（12kHz Drive-End）
# 正常・内輪損傷・外輪損傷の代表的なファイル
CWRU_FILES: dict[str, dict] = {
    "normal": {
        "url": "https://engineering.case.edu/sites/default/files/97.mat",
        "mat_key": "X097_DE_time",  # 正常 1797rpm
        "filename": "97.mat",
    },
    "inner_race": {
        "url": "https://engineering.case.edu/sites/default/files/105.mat",
        "mat_key": "X105_DE_time",  # 内輪損傷 0.007inch 1797rpm
        "filename": "105.mat",
    },
    "outer_race": {
        "url": "https://engineering.case.edu/sites/default/files/130.mat",
        "mat_key": "X130_DE_time",  # 外輪損傷 0.007inch 1797rpm
        "filename": "130.mat",
    },
}

# サンプリングレート
SAMPLING_RATE = 12000  # 12kHz


def download_mat_file(url: str, filepath: Path) -> bool:
    """MATファイルをダウンロードする"""
    if filepath.exists():
        logger.info(f"既にダウンロード済み: {filepath.name}")
        return True
    try:
        logger.info(f"ダウンロード中: {url}")
        urllib.request.urlretrieve(url, str(filepath))
        logger.info(f"保存完了: {filepath.name}")
        return True
    except Exception as e:
        logger.error(f"ダウンロード失敗: {e}")
        return False


def extract_signal(filepath: Path, mat_key: str) -> np.ndarray | None:
    """MATファイルからDrive-End加速度信号を抽出する"""
    try:
        mat_data = sio.loadmat(str(filepath))
        # キーが見つからない場合、DEを含むキーを探す
        if mat_key in mat_data:
            signal = mat_data[mat_key].flatten()
        else:
            de_keys = [k for k in mat_data.keys() if 'DE' in k]
            if de_keys:
                signal = mat_data[de_keys[0]].flatten()
                logger.info(f"代替キー使用: {de_keys[0]}")
            else:
                logger.error(f"DE信号が見つかりません: {list(mat_data.keys())}")
                return None
        logger.info(f"信号取得: {len(signal)} サンプル ({len(signal)/SAMPLING_RATE:.1f}秒)")
        return signal
    except Exception as e:
        logger.error(f"信号抽出失敗: {e}")
        return None


def save_as_csv(signal: np.ndarray, label: str, output_path: Path) -> None:
    """加速度信号をCSVに保存する（時間列付き）"""
    n = len(signal)
    time_axis = np.arange(n) / SAMPLING_RATE
    # CSVヘッダー: time, acceleration, label
    header = "time,acceleration,label"
    data = np.column_stack([time_axis, signal])
    # ラベル列はテキストなので別途処理
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + "\n")
        for t, acc in data:
            f.write(f"{t:.6f},{acc:.6f},{label}\n")
    logger.info(f"CSV保存: {output_path.name} ({n}行)")


def main() -> None:
    """全データのダウンロード・変換を実行する"""
    logger.info("=== CWRUデータ ダウンロード開始 ===")

    all_signals: dict[str, np.ndarray] = {}

    for label, info in CWRU_FILES.items():
        mat_path = DATA_DIR / info["filename"]

        # ダウンロード
        if not download_mat_file(info["url"], mat_path):
            continue

        # 信号抽出
        signal = extract_signal(mat_path, info["mat_key"])
        if signal is None:
            continue

        all_signals[label] = signal

        # 個別CSV保存
        csv_path = DATA_DIR / f"{label}.csv"
        save_as_csv(signal, label, csv_path)

    # 統合CSVも作成（各クラス先頭10秒分 = 120,000サンプル）
    if len(all_signals) == 3:
        combined_path = DATA_DIR / "combined.csv"
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("time,acceleration,label\n")
            for label, signal in all_signals.items():
                # 先頭10秒分を使用
                n_samples = min(len(signal), SAMPLING_RATE * 10)
                for i in range(n_samples):
                    t = i / SAMPLING_RATE
                    f.write(f"{t:.6f},{signal[i]:.6f},{label}\n")
        logger.info(f"統合CSV保存: {combined_path.name}")

    logger.info("=== ダウンロード完了 ===")


if __name__ == "__main__":
    main()
