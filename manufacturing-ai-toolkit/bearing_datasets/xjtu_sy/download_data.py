"""
XJTU-SYベアリングデータセット ダウンロード＆構造確認
Google Driveからデータを取得し、各Conditionのデータ構造を把握する

データ概要:
- 3条件 × 5本 = 15ベアリングのrun-to-failureデータ
- Condition1: 2100rpm / 12kN
- Condition2: 2250rpm / 11kN
- Condition3: 2400rpm / 10kN
- 25.6kHz、1分ごとに1.28秒収録（CSV: 水平振動, 垂直振動）
"""

import logging
import zipfile
from pathlib import Path

import gdown

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

# Google DriveのフォルダID
GDRIVE_FOLDER_ID = "1_ycmG46PARiykt82ShfnFfyQsaXv3_VK"


def download_from_gdrive(folder_id: str, output_dir: Path) -> bool:
    """Google Driveフォルダからデータをダウンロードする"""
    try:
        logger.info(f"Google Driveからダウンロード開始（フォルダID: {folder_id}）")
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        gdown.download_folder(url=url, output=str(output_dir), quiet=False)
        logger.info("ダウンロード完了")
        return True
    except Exception as e:
        logger.error(f"ダウンロード失敗: {e}")
        return False


def extract_all_zips(data_dir: Path) -> None:
    """ダウンロードしたZIPファイルを全て展開する"""
    zip_files = list(data_dir.rglob("*.zip"))
    if not zip_files:
        logger.info("ZIPファイルなし（展開済みまたはCSV直接配置）")
        return

    for zip_path in zip_files:
        try:
            logger.info(f"ZIP展開: {zip_path.name}")
            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(zip_path.parent))
            logger.info(f"展開完了: {zip_path.name}")
        except Exception as e:
            logger.error(f"展開失敗: {zip_path.name} ({e})")


def find_condition_dirs(data_dir: Path) -> dict[str, Path]:
    """Condition1〜3のディレクトリを探索する

    実際のフォルダ名: 35Hz12kN, 37.5Hz11kN, 40Hz10kN
    """
    # 実際のフォルダ名 → 論理名のマッピング
    folder_map: dict[str, str] = {
        '35Hz12kN': 'Condition1',      # 2100rpm / 12kN
        '37.5Hz11kN': 'Condition2',    # 2250rpm / 11kN
        '40Hz10kN': 'Condition3',      # 2400rpm / 10kN
    }

    conditions: dict[str, Path] = {}
    for folder_name, cond_name in folder_map.items():
        for p in data_dir.rglob(folder_name):
            if p.is_dir():
                conditions[cond_name] = p
                logger.info(f"  {cond_name} → {p.name}")
                break

    # フォールバック: Condition1, Condition2, Condition3 直接探索
    if not conditions:
        for cond_num in [1, 2, 3]:
            for p in data_dir.rglob(f"*ondition{cond_num}*"):
                if p.is_dir():
                    conditions[f"Condition{cond_num}"] = p
                    break

    return conditions


def scan_bearing_structure(condition_dir: Path) -> list[Path]:
    """Condition内のベアリングディレクトリ一覧を取得する

    ベアリング名: Bearing1_1〜1_5, Bearing2_1〜2_5, Bearing3_1〜3_5
    """
    bearing_dirs = sorted([
        d for d in condition_dir.iterdir()
        if d.is_dir() and "bearing" in d.name.lower()
    ])
    return bearing_dirs


def report_dataset_structure(data_dir: Path) -> None:
    """データセットの構造をレポートする"""
    conditions = find_condition_dirs(data_dir)

    if not conditions:
        logger.warning("Conditionディレクトリが見つかりません")
        # ディレクトリ構造をダンプして調査
        for p in sorted(data_dir.rglob("*"))[:30]:
            logger.info(f"  {p.relative_to(data_dir)}")
        return

    logger.info(f"=== データセット構造 ===")
    for cond_name, cond_path in sorted(conditions.items()):
        bearing_dirs = scan_bearing_structure(cond_path)
        logger.info(f"{cond_name}: {cond_path}")
        for bd in bearing_dirs:
            csv_count = len(list(bd.glob("*.csv")))
            logger.info(f"  {bd.name}: {csv_count}スナップショット")


def main() -> None:
    """データのダウンロード・展開・構造確認を実行する"""
    logger.info("=== XJTU-SY Bearing Dataset ダウンロード開始 ===")

    # ダウンロード
    if not any(DATA_DIR.rglob("*.csv")):
        if not download_from_gdrive(GDRIVE_FOLDER_ID, DATA_DIR):
            logger.error("ダウンロードに失敗しました")
            return
        # ZIP展開
        extract_all_zips(DATA_DIR)
    else:
        logger.info("CSVファイル検出済み — ダウンロードスキップ")

    # 構造レポート
    report_dataset_structure(DATA_DIR)

    logger.info("=== ダウンロード・構造確認完了 ===")


if __name__ == "__main__":
    main()
