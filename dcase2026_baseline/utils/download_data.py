"""
DCASE 2026 Task 2 Bearing データダウンロードスクリプト

Zenodoから dev_bearingEmu.zip をダウンロードし、
./dev_Bearing/ に展開する

データ容量: 約608MB
公式URL: https://zenodo.org/records/19336329
"""

import hashlib
import logging
import shutil
import urllib.request
import zipfile
from pathlib import Path

from tqdm import tqdm

logger = logging.getLogger(__name__)

# DCASE 2026 公式ダウンロードURL
DOWNLOAD_URL = (
    "https://zenodo.org/records/19336329/"
    "files/dev_bearingEmu.zip?download=1"
)
EXPECTED_MD5 = "82c2d04c5f48d09842152c34ef273667"
ZIP_FILENAME = "dev_bearingEmu.zip"

# プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "dcase2026_baseline" / "downloads"
EXTRACT_DIR = PROJECT_ROOT / "dev_Bearing"


class _TqdmProgress(tqdm):
    """urllib用のtqdmプログレスバー"""

    def update_to(
        self, block_num: int = 1,
        block_size: int = 1, total_size: int | None = None,
    ) -> None:
        if total_size is not None:
            self.total = total_size
        self.update(block_num * block_size - self.n)


def download_zip(
    url: str = DOWNLOAD_URL,
    dest: Path = DOWNLOAD_DIR / ZIP_FILENAME,
) -> Path:
    """ZIPファイルをダウンロードする

    Args:
        url: ダウンロード元URL
        dest: 保存先パス

    Returns:
        ダウンロード済みファイルのパス
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        logger.info(f"既存ファイル発見: {dest} (スキップ)")
        return dest

    logger.info(f"ダウンロード開始: {url}")
    logger.info(f"保存先: {dest}")

    with _TqdmProgress(
        unit="B", unit_scale=True, miniters=1,
        desc=ZIP_FILENAME,
    ) as pbar:
        urllib.request.urlretrieve(
            url, filename=str(dest),
            reporthook=pbar.update_to,
        )

    size_mb = dest.stat().st_size / 1024 / 1024
    logger.info(f"ダウンロード完了: {size_mb:.1f} MB")
    return dest


def verify_md5(
    file_path: Path, expected: str = EXPECTED_MD5,
) -> bool:
    """ファイルのMD5チェックサムを検証する

    Args:
        file_path: 検証対象ファイル
        expected: 期待するMD5ハッシュ

    Returns:
        ハッシュが一致すればTrue
    """
    logger.info("MD5チェックサム検証中...")
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    actual = hasher.hexdigest()

    if actual == expected:
        logger.info(f"MD5検証OK: {actual}")
        return True

    logger.error(
        f"MD5不一致！ 期待={expected} 実際={actual}"
    )
    return False


def extract_zip(
    zip_path: Path, extract_to: Path = EXTRACT_DIR,
) -> Path:
    """ZIPファイルを展開する

    DCASE 2026のZIPは dev_bearingEmu/ として展開されるが、
    config.pyとの整合性のため dev_Bearing/ にリネームする

    Args:
        zip_path: ZIPファイルパス
        extract_to: 展開先ディレクトリ

    Returns:
        展開されたディレクトリのパス
    """
    if extract_to.exists() and any(extract_to.iterdir()):
        logger.info(f"展開済み: {extract_to} (スキップ)")
        return extract_to

    logger.info(f"ZIP展開中: {zip_path} -> {extract_to.parent}")
    extract_to.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        for member in tqdm(members, desc="展開"):
            zf.extract(member, path=extract_to.parent)

    # dev_bearingEmu/ → dev_Bearing/ にリネーム
    emu_dir = extract_to.parent / "dev_bearingEmu"
    if emu_dir.exists() and not extract_to.exists():
        logger.info(f"リネーム: {emu_dir.name} -> {extract_to.name}")
        shutil.move(str(emu_dir), str(extract_to))

    logger.info(f"展開完了: {extract_to}")
    return extract_to


def show_structure(data_dir: Path = EXTRACT_DIR) -> None:
    """展開後のディレクトリ構造を表示する"""
    if not data_dir.exists():
        logger.warning(f"ディレクトリなし: {data_dir}")
        return

    logger.info(f"=== {data_dir} の構造 ===")
    for entry in sorted(data_dir.iterdir()):
        if entry.is_dir():
            wav_count = len(list(entry.rglob("*.wav")))
            logger.info(f"  {entry.name}/ ({wav_count}件のwav)")
        else:
            logger.info(f"  {entry.name}")


def download_and_extract() -> Path:
    """ダウンロード→検証→展開 を一括実行する

    Returns:
        展開先ディレクトリ
    """
    zip_path = download_zip()

    if not verify_md5(zip_path):
        raise ValueError(
            "MD5チェックサム不一致。"
            "ファイルを削除して再ダウンロードしてください。"
        )

    data_dir = extract_zip(zip_path)
    show_structure(data_dir)
    return data_dir


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    download_and_extract()
