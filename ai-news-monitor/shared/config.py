"""
環境設定管理モジュール

環境変数から設定を読み込み、アプリケーション全体で使用する定数を定義する。
.env ファイルまたは環境変数から読み込む。
"""

import os
from pathlib import Path

# プロジェクトのルートディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================
# X API 設定
# ============================================================================
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")

# X API v2 検索キーワード（複数組み合わせ対応）
X_KEYWORDS = [
    "#AI",
    "#LLM",
    "#Claude",
    "#Anthropic",
    "Claude API",
    "RAG",
    "agent",
    "prompt engineering",
    "data science",
]

# 監視対象アカウント
X_ACCOUNTS = [
    "@AnthropicAI",
    "@OpenAI",
    "@HuggingFace",
    "@LangChainAI",
]

# ============================================================================
# Slack 設定
# ============================================================================
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# ============================================================================
# Database 設定
# ============================================================================
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "data" / "ai_news.db"))

# ============================================================================
# アプリケーション設定
# ============================================================================
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")  # development / production

# ============================================================================
# スケジューリング設定
# ============================================================================
SCHEDULER_MORNING_HOUR = int(os.environ.get("SCHEDULER_MORNING_HOUR", "8"))
SCHEDULER_MORNING_MINUTE = int(os.environ.get("SCHEDULER_MORNING_MINUTE", "0"))

SCHEDULER_EVENING_HOUR = int(os.environ.get("SCHEDULER_EVENING_HOUR", "20"))
SCHEDULER_EVENING_MINUTE = int(os.environ.get("SCHEDULER_EVENING_MINUTE", "0"))

# ============================================================================
# RSS フィード設定
# ============================================================================
FEED_URLS = [
    "https://feeds.bloomberg.com/technology/news.rss",  # Bloomberg Tech
    "https://techcrunch.com/feed/",  # TechCrunch
    "https://www.hackernews.io/rss",  # Hacker News
]

# ============================================================================
# API レート制限設定
# ============================================================================
X_REQUEST_DELAY_SEC = float(os.environ.get("X_REQUEST_DELAY_SEC", "1.0"))  # リクエスト間の遅延（秒）
SLACK_TIMEOUT_SEC = int(os.environ.get("SLACK_TIMEOUT_SEC", "5"))  # Slack Webhook タイムアウト

# ============================================================================
# Validation
# ============================================================================
def validate_config() -> None:
    """重要な設定が存在するかチェック"""
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL が設定されていません")

    # X API の設定（いずれか1つあればOK）
    if not (X_BEARER_TOKEN or (X_API_KEY and X_API_SECRET)):
        raise ValueError("X API の認証情報が設定されていません")


if __name__ == "__main__":
    print("=== Configuration ===")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Database Path: {DB_PATH}")
    print(f"Slack Webhook: {'設定済み' if SLACK_WEBHOOK_URL else '未設定'}")
    print(f"X Keywords: {len(X_KEYWORDS)} 個")
    print(f"X Accounts: {len(X_ACCOUNTS)} 個")
    print(f"Feed URLs: {len(FEED_URLS)} 個")
