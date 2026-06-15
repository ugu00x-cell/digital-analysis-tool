"""
納品物zipを生成するスクリプト。
ソースコード一式と送信結果CSVをまとめる。
"""

import glob
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

# ベースディレクトリ
BASE = Path(r"C:\Users\ugu00\my-secretary\form_sender")
OUTPUT_DIR = Path(r"C:\Users\ugu00\Documents")

# 納品zipに含めるファイル・ディレクトリ（相対パス）
INCLUDE_FILES = [
    "app.py",
    "config.py",
    "requirements.txt",
    "GUIDE.md",
    ".env.example",
    "起動.bat",
    "起動.command",
    "初期セットアップ.bat",
    "初期セットアップ.command",
]

INCLUDE_DIRS = [
    "utils",
    "pages",
    "engine",
]

# __pycache__ などを除外するフィルタ
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}


def should_include(path: Path) -> bool:
    """ファイルを含めるか判定する。"""
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return False
    return path.suffix not in EXCLUDE_SUFFIXES


def add_dir_to_zip(zf: zipfile.ZipFile, src_dir: Path, zip_prefix: str) -> int:
    """ディレクトリを再帰的にzipに追加する。"""
    count = 0
    for root, dirs, files in os.walk(src_dir):
        # __pycache__ 等を除外
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for filename in files:
            filepath = Path(root) / filename
            if not should_include(filepath):
                continue
            arcname = zip_prefix + "/" + filepath.relative_to(src_dir).as_posix()
            zf.write(filepath, arcname)
            count += 1
    return count


def get_latest_summary_csv() -> Path | None:
    """最新のsummary CSVを返す。"""
    files = sorted(glob.glob(str(BASE / "db" / "summary_final_*.csv")))
    return Path(files[-1]) if files else None


def build_zip() -> Path:
    """納品zipを生成する。"""
    timestamp = datetime.now().strftime("%Y%m%d")
    zip_name = f"form_sender_納品_{timestamp}.zip"
    zip_path = OUTPUT_DIR / zip_name

    total = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # ツール本体ファイル
        for rel in INCLUDE_FILES:
            src = BASE / rel
            if src.exists():
                zf.write(src, f"form_sender/{rel}")
                total += 1
                print(f"  追加: form_sender/{rel}")
            else:
                print(f"  スキップ（存在しない）: {rel}")

        # ディレクトリ
        for d in INCLUDE_DIRS:
            src_dir = BASE / d
            if src_dir.exists():
                n = add_dir_to_zip(zf, src_dir, f"form_sender/{d}")
                total += n
                print(f"  追加: form_sender/{d}/ ({n}ファイル)")

        # db/ と data/ は起動時に自動作成されるため zip には含めない
        # （上書きインストール時にクライアントのデータを消さないようにするため）

        # 送信結果CSV（別フォルダ）
        summary_csv = get_latest_summary_csv()
        if summary_csv:
            zf.write(summary_csv, f"送信結果/送信結果_100社_{timestamp}.csv")
            total += 1
            print(f"  追加: 送信結果/送信結果_100社_{timestamp}.csv")
        else:
            print("  警告: サマリーCSVが見つかりません")

    print(f"\n完了: {zip_path}")
    print(f"合計 {total} ファイル")
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"サイズ: {size_mb:.1f} MB")
    return zip_path


if __name__ == "__main__":
    build_zip()
