"""設定値・キーワード定義モジュール。"""

# リクエスト設定
REQUEST_TIMEOUT: int = 15
REQUEST_INTERVAL: float = 2.0  # 秒（レート制限）
MAX_RETRIES: int = 2

# ユーザーエージェント
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# 検索キーワード（市区町村HPから助成金ページを探す用）
SEARCH_KEYWORDS: list[str] = [
    "補助金", "助成金", "リフォーム", "塗装",
    "空き家", "結婚新生活", "三世代",
]

# 対象工事の判定キーワード
TARGET_WORK_KEYWORDS: list[str] = [
    "外壁", "塗装", "リフォーム", "改修", "修繕",
    "屋根", "防水", "断熱", "耐震",
]

# 除外キーワード（これだけの場合は除外）
EXCLUDE_KEYWORDS: list[str] = [
    "新築購入のみ", "店舗のみ", "法人のみ",
    "新築限定", "事業者向け",
]

# 有効年度
TARGET_YEAR: int = 2026

# 出力列（入力CSVに追加する列）
OUTPUT_COLUMNS: list[str] = [
    "助成金名", "金額補助率", "対象者", "対象工事",
    "申請期間", "問い合わせ先", "助成金URL",
    "判定結果", "信頼度", "メモ",
]
