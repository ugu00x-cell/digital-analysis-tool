"""
FEMTO/PRONOSTIA ベアリングデータセット ダウンロード＆構造確認
GitHubリポジトリからクローンし、データ構造をレポートする

データ概要:
- 17本のベアリングrun-to-failure（訓練6本＋テスト11本）
- Condition1: 1800rpm / 4kN
- Condition2: 1650rpm / 4.2kN
- Condition3: 1500rpm / 5kN
- 25.6kHz、10秒ごとに0.1秒収録（2560サンプル/スナップショット）
- CSV: 時,分,秒,μ秒,水平振動,垂直振動（ヘッダーなし）
"""

import logging
import subprocess
from pathlib import Path

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
REPO_DIR = DATA_DIR / "repo"
REPO_URL = "https://github.com/wkzs111/phm-ieee-2012-data-challenge-dataset.git"

# データセット内のフォルダ構造
LEARNING_DIR = REPO_DIR / "Learning_set"
FULL_TEST_DIR = REPO_DIR / "Full_Test_Set"


def clone_repository(repo_url: str, dest: Path) -> bool:
    """GitHubリポジトリをクローンする"""
    if dest.exists():
        logger.info(f"リポジトリ取得済み: {dest}")
        return True
    try:
        logger.info(f"リポジトリクローン中: {repo_url}")
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest)],
            check=True, capture_output=True, text=True
        )
        logger.info("クローン完了")
        return True
    except Exception as e:
        logger.error(f"クローン失敗: {e}")
        return False


def scan_bearings(base_dir: Path) -> dict[str, list[Path]]:
    """ベアリングディレクトリを条件別にスキャンする"""
    conditions: dict[str, list[Path]] = {
        'Condition1': [],
        'Condition2': [],
        'Condition3': [],
    }

    if not base_dir.exists():
        logger.warning(f"ディレクトリなし: {base_dir}")
        return conditions

    for d in sorted(base_dir.iterdir()):
        if not d.is_dir() or 'Bearing' not in d.name:
            continue
        # Bearing1_x → Condition1, Bearing2_x → Condition2, etc.
        if d.name.startswith('Bearing1'):
            conditions['Condition1'].append(d)
        elif d.name.startswith('Bearing2'):
            conditions['Condition2'].append(d)
        elif d.name.startswith('Bearing3'):
            conditions['Condition3'].append(d)

    return conditions


def count_snapshots(bearing_dir: Path) -> int:
    """ベアリングディレクトリ内の振動スナップショット数をカウントする"""
    return len(list(bearing_dir.glob("acc_*.csv")))


def report_structure() -> None:
    """データセットの構造をレポートする"""
    logger.info("=== データセット構造 ===")

    for label, base_dir in [("Training", LEARNING_DIR), ("Full_Test", FULL_TEST_DIR)]:
        conditions = scan_bearings(base_dir)
        logger.info(f"\n{label} ({base_dir.name}):")

        for cond_name, bearing_dirs in sorted(conditions.items()):
            if not bearing_dirs:
                continue
            logger.info(f"  {cond_name}:")
            for bd in bearing_dirs:
                n = count_snapshots(bd)
                logger.info(f"    {bd.name}: {n}スナップショット")


def main() -> None:
    """データ取得と構造確認を実行する"""
    logger.info("=== FEMTO/PRONOSTIA ダウンロード開始 ===")

    if not clone_repository(REPO_URL, REPO_DIR):
        return

    report_structure()

    logger.info("=== ダウンロード・構造確認完了 ===")


if __name__ == "__main__":
    main()
