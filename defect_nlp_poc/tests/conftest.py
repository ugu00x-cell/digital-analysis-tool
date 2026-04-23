"""pytest共通設定：src/ をパスに追加してモジュール解決できるようにする。"""
import sys
from pathlib import Path

# このファイルから見て ../src を import path に追加
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
