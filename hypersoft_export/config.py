"""設定値管理 - ハイパーソフト管理画面のURL・出力先ディレクトリ"""

from pathlib import Path

# =====================
# ディレクトリパス
# =====================
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "data" / "downloaded"
LOG_PATH = BASE_DIR / "app.log"

# =====================
# ハイパーソフト管理画面
# =====================
LOGIN_URL = "https://by9.salondenet.jp/"
EXPORT_URL = "https://by9.salondenet.jp/snpos/KaikeiChk_Recipt.aspx"

# 開始日・終了日の入力欄ID（要検証・実機で微調整）
DATE_START_ID = "ContentPlaceHolder1_cboDate_S"
DATE_END_ID = "ContentPlaceHolder1_cboDate_E"

# エクセル出力ボタンの表示テキスト
EXPORT_BUTTON_TEXT = "エクセル"

# =====================
# 期間分割の制約
# =====================
MAX_DAYS_PER_CHUNK = 31
