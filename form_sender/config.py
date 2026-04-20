"""設定値管理 - APIキー・送信パラメータ・DB接続"""

import os
from pathlib import Path

from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# =====================
# ディレクトリパス
# =====================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
LOGS_DIR = DATA_DIR / "logs"
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "results.db"

# =====================
# APIキー（Gemini）
# =====================
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")

# =====================
# 送信制御パラメータ
# =====================
# ウェイト範囲（秒）
WAIT_MIN: int = 30
WAIT_MAX: int = 90
# 1日の送信上限（デフォルト）
DAILY_LIMIT: int = 50
# Playwrightタイムアウト（ミリ秒）
PAGE_TIMEOUT: int = 30000
# フォーム送信後の待機時間（秒）
POST_SUBMIT_WAIT: int = 5

# =====================
# 送信者情報（デフォルト値）
# =====================
DEFAULT_SENDER = {
    "company": "株式会社サンプル",
    "name": "山田 太郎",
    "email": "taro@example.com",
    "phone": "03-1234-5678",
}

# =====================
# Gemini APIモデル
# =====================
GEMINI_MODEL: str = "gemini-2.5-flash"
