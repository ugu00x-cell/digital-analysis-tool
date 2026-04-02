"""
設定値まとめ
ダミー送信データ・レート制限・ステータス定義など
"""

# === レート制限 ===
MAX_PER_HOUR: int = 100          # 1時間あたりの処理上限
DEFAULT_DELAY: int = 5           # デフォルト待機秒数
DELAY_JITTER: float = 2.0        # 待機時間のランダム幅（±秒）
PAGE_TIMEOUT: int = 15000        # 1件あたりのタイムアウト（ミリ秒）
CONSECUTIVE_ERROR_LIMIT: int = 5  # 連続エラー時の一時停止閾値

# === ダミー送信データ ===
DUMMY_DATA: dict[str, str] = {
    "company": "株式会社テスト",
    "name": "テスト 太郎",
    "email": "test@example.com",
    "tel": "000-0000-0000",
    "message": "テストです。（自動テストによる送信）",
}

# === ステータス定義 ===
STATUS_SUCCESS: str = "SUCCESS"    # フォーム発見・全項目マッピング・送信成功
STATUS_PARTIAL: str = "PARTIAL"    # フォーム発見・一部項目のみマッピング
STATUS_NO_FORM: str = "NO_FORM"   # フォームページが見つからない
STATUS_CAPTCHA: str = "CAPTCHA"   # reCAPTCHA等を検出
STATUS_TIMEOUT: str = "TIMEOUT"   # タイムアウト
STATUS_ERROR: str = "ERROR"       # その他エラー

# === フォーム探索パス（トップページにリンクがない場合のフォールバック） ===
FALLBACK_PATHS: list[str] = [
    "/contact",
    "/inquiry",
    "/form",
    "/contact-us",
    "/contactus",
    "/toiawase",
]

# === コンタクトリンク検出キーワード ===
CONTACT_LINK_KEYWORDS: list[str] = [
    "お問い合わせ", "お問い合せ", "問い合わせ", "問合せ",
    "contact", "inquiry", "お見積", "相談",
]

# === CAPTCHA検出パターン ===
CAPTCHA_PATTERNS: list[str] = [
    "g-recaptcha",
    "h-captcha",
    "recaptcha",
    "hcaptcha",
    "cf-turnstile",
]
