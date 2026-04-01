"""
NASA IMS Bearing Dataset ダウンロード＆前処理
S3から4.+Bearings.zipを取得し、テスト2のデータをCSVに変換する

テスト2の概要:
- ベアリング4個の振動データ（20kHz、各1秒スナップショット）
- 984ファイル（約10分間隔で記録）
- Bearing1が外輪故障で停止
"""

import logging
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import py7zr
import rarfile

# WinRARのパスを設定
rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"

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
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DOWNLOAD_URL = "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip"
ZIP_FILENAME = "bearings.zip"
SAMPLING_RATE = 20000  # 20kHz
NUM_BEARINGS = 4


def download_dataset(url: str, save_path: Path) -> bool:
    """NASAベアリングデータセットをダウンロードする"""
    if save_path.exists():
        logger.info(f"既にダウンロード済み: {save_path.name}")
        return True
    try:
        logger.info(f"ダウンロード中（約200MB）: {url}")
        urllib.request.urlretrieve(url, str(save_path))
        logger.info(f"ダウンロード完了: {save_path.name}")
        return True
    except Exception as e:
        logger.error(f"ダウンロード失敗: {e}")
        return False


def extract_zip(zip_path: Path, extract_dir: Path) -> bool:
    """ZIPファイルを展開する"""
    try:
        logger.info(f"ZIP展開中: {zip_path.name}")
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            zf.extractall(str(extract_dir))
        logger.info("ZIP展開完了")
        return True
    except Exception as e:
        logger.error(f"ZIP展開失敗: {e}")
        return False


def extract_7z(seven_z_path: Path, extract_dir: Path) -> bool:
    """7zファイルを展開する"""
    try:
        logger.info(f"7z展開中: {seven_z_path.name}")
        with py7zr.SevenZipFile(str(seven_z_path), mode='r') as z:
            z.extractall(path=str(extract_dir))
        logger.info("7z展開完了")
        return True
    except Exception as e:
        logger.error(f"7z展開失敗: {e}")
        return False


def extract_rar(rar_path: Path, extract_dir: Path) -> bool:
    """RARファイルを展開する"""
    try:
        logger.info(f"RAR展開中: {rar_path.name}")
        with rarfile.RarFile(str(rar_path)) as rf:
            rf.extractall(str(extract_dir))
        logger.info(f"RAR展開完了: {rar_path.name}")
        return True
    except Exception as e:
        logger.error(f"RAR展開失敗: {e}")
        return False


def find_test2_dir(base_dir: Path) -> Path | None:
    """テスト2のディレクトリを探す（ZIP→7z→rar内のフォルダ名に対応）"""
    # まず7zファイルがあれば展開
    for seven_z in base_dir.rglob("*.7z"):
        ims_dir = seven_z.parent / "IMS"
        if not ims_dir.exists():
            extract_7z(seven_z, seven_z.parent)

    # RARファイルがあれば展開（2nd_test.rar）
    for rar_file in base_dir.rglob("2nd_test.rar"):
        test2_candidate = rar_file.parent / "2nd_test"
        if not test2_candidate.exists():
            extract_rar(rar_file, rar_file.parent)

    # テスト2ディレクトリの候補を探索
    candidates = [
        base_dir / "2nd_test",
        base_dir / "IMS" / "2nd_test",
        base_dir / "4. Bearings" / "2nd_test",
        base_dir / "4. Bearings" / "IMS" / "2nd_test",
    ]
    for c in candidates:
        if c.exists():
            logger.info(f"テスト2ディレクトリ発見: {c}")
            return c

    # 再帰的に探す
    for p in base_dir.rglob("2nd_test"):
        if p.is_dir():
            logger.info(f"テスト2ディレクトリ発見: {p}")
            return p

    logger.error("テスト2ディレクトリが見つかりません")
    return None


def parse_snapshot_file(filepath: Path) -> np.ndarray | None:
    """1つのスナップショットファイル（ASCII）を読み込む

    各行に4列（Bearing1〜4の加速度）がタブ区切りで格納されている
    """
    try:
        data = np.loadtxt(str(filepath), delimiter='\t')
        if data.ndim == 1:
            # 1列しかない場合はスキップ
            logger.warning(f"データ形式が想定外: {filepath.name}")
            return None
        return data
    except Exception as e:
        logger.warning(f"読み込みスキップ: {filepath.name} ({e})")
        return None


def convert_test2_to_csv(test2_dir: Path) -> pd.DataFrame | None:
    """テスト2の全スナップショットから特徴量サマリCSVを作成する"""
    logger.info("テスト2データの変換開始")

    # スナップショットファイルを時系列順にソート
    snapshot_files = sorted(test2_dir.glob("*"))
    snapshot_files = [f for f in snapshot_files if f.is_file()]

    if not snapshot_files:
        logger.error(f"スナップショットファイルが見つかりません: {test2_dir}")
        return None

    logger.info(f"スナップショット数: {len(snapshot_files)}")

    records: list[dict] = []
    for idx, fpath in enumerate(snapshot_files):
        data = parse_snapshot_file(fpath)
        if data is None:
            continue

        # 各ベアリングのRMSを記録（時系列追跡用）
        record = {
            'snapshot_idx': idx,
            'filename': fpath.name,
        }
        for bearing_id in range(min(data.shape[1], NUM_BEARINGS)):
            signal = data[:, bearing_id]
            record[f'bearing{bearing_id + 1}_rms'] = np.sqrt(np.mean(signal ** 2))

        records.append(record)

    summary_df = pd.DataFrame(records)
    summary_path = DATA_DIR / "test2_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    logger.info(f"サマリCSV保存: {summary_path.name} ({len(summary_df)}行)")

    return summary_df


def save_representative_snapshots(test2_dir: Path) -> None:
    """初期・中期・末期の代表スナップショットをCSVに保存する"""
    snapshot_files = sorted(
        [f for f in test2_dir.glob("*") if f.is_file()]
    )
    total = len(snapshot_files)
    if total == 0:
        return

    # 初期（5%地点）、中期（50%地点）、末期（95%地点）
    indices = {
        'early': int(total * 0.05),
        'mid': int(total * 0.50),
        'late': int(total * 0.95),
    }

    for phase, idx in indices.items():
        fpath = snapshot_files[idx]
        data = parse_snapshot_file(fpath)
        if data is None:
            continue

        # 時間軸を付与してCSV保存
        n_samples = data.shape[0]
        time_axis = np.arange(n_samples) / SAMPLING_RATE
        columns = ['time'] + [f'bearing{i+1}' for i in range(data.shape[1])]
        df = pd.DataFrame(
            np.column_stack([time_axis, data]),
            columns=columns
        )
        csv_path = DATA_DIR / f"snapshot_{phase}.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"{phase}スナップショット保存: {csv_path.name} (idx={idx}, file={fpath.name})")


def save_all_bearing1_signals(test2_dir: Path) -> None:
    """Bearing1（故障ベアリング）の全スナップショット信号をnpzで保存する"""
    snapshot_files = sorted(
        [f for f in test2_dir.glob("*") if f.is_file()]
    )

    signals: list[np.ndarray] = []
    filenames: list[str] = []
    for fpath in snapshot_files:
        data = parse_snapshot_file(fpath)
        if data is None or data.shape[1] < 1:
            continue
        signals.append(data[:, 0])  # Bearing1のみ
        filenames.append(fpath.name)

    if signals:
        npz_path = DATA_DIR / "bearing1_all.npz"
        np.savez_compressed(
            str(npz_path),
            signals=np.array(signals),
            filenames=np.array(filenames)
        )
        logger.info(f"Bearing1全信号保存: {npz_path.name} ({len(signals)}スナップショット)")


def main() -> None:
    """データのダウンロード・展開・変換を実行する"""
    logger.info("=== NASA IMS Bearing Dataset ダウンロード開始 ===")

    # ダウンロード
    zip_path = DATA_DIR / ZIP_FILENAME
    if not download_dataset(DOWNLOAD_URL, zip_path):
        return

    # ZIP展開
    extract_dir = DATA_DIR / "extracted"
    if not extract_dir.exists():
        if not extract_zip(zip_path, extract_dir):
            return
    else:
        logger.info("展開済みデータを使用")

    # テスト2ディレクトリを探す
    test2_dir = find_test2_dir(extract_dir)
    if test2_dir is None:
        return

    # サマリCSV作成
    convert_test2_to_csv(test2_dir)

    # 代表スナップショットをCSV保存（FFT解析用）
    save_representative_snapshots(test2_dir)

    # Bearing1の全信号を保存（異常検知用）
    save_all_bearing1_signals(test2_dir)

    logger.info("=== ダウンロード・変換完了 ===")


if __name__ == "__main__":
    main()
