# AI News Monitor

X（Twitter）API + RSS フィードから AI 関連の最新ニュースを自動収集し、Slack に通知するアプリケーション。

## 特徴

- ✅ **複数ソース対応**：X（Twitter）API v2 + RSS フィード
- ✅ **キーワード検索**：AI、LLM、Claude、RAG など複数キーワード対応
- ✅ **アカウント監視**：@AnthropicAI、@OpenAI など特定アカウントのタイムラインを取得
- ✅ **重複防止**：SQLite により同じニュースの重複投稿を防止
- ✅ **Slack統合**：Webhook で自動通知
- ✅ **スケジューリング**：APScheduler で朝・夜に自動実行（Phase 2）

## セットアップ

### 1. 必要な認証情報

#### X API v2

1. **X Developer Account を作成**
   - https://developer.twitter.com/

2. **Bearer Token を取得**
   - または API Key & Secret を取得

#### Slack Webhook

1. **Slack ワークスペースを作成 / アクセス**
   - https://slack.com/

2. **Incoming Webhooks を有効化**
   - https://api.slack.com/messaging/webhooks

3. **Webhook URL を取得**

### 2. インストール

```bash
# リポジトリをクローン
git clone https://github.com/your-username/ai-news-monitor.git
cd ai-news-monitor

# 仮想環境を作成（オプション）
python -m venv venv
source venv/bin/activate  # on Windows: venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 3. 環境変数を設定

```bash
# .env.example をコピー
cp .env.example .env

# .env を編集して認証情報を入力
# - X_BEARER_TOKEN
# - SLACK_WEBHOOK_URL
# その他のオプション設定
```

## 使用方法

### 手動実行（テスト）

```bash
# 通常実行：X API + RSS から情報取得 → Slack 通知
python main.py

# ドライラン：Slack 通知なしでテスト
python main.py --dry-run

# Slack テストメッセージを送信
python main.py --test-slack

# 設定をバリデート
python main.py --validate-config
```

### ログファイル

```
logs/ai_news_monitor.log
```

## プロジェクト構成

```
ai-news-monitor/
├── main.py                    # エントリーポイント
├── requirements.txt           # 依存パッケージ
├── .env.example              # 環境変数テンプレート
├── README.md                 # 本ファイル
│
├── shared/                   # 共通モジュール
│   ├── config.py             # 環境設定管理
│   ├── models.py             # Pydantic データモデル
│   ├── logger.py             # ロギング設定
│   └── database.py           # SQLite 操作
│
├── services/                 # ビジネスロジック
│   ├── collector/            # 情報収集サービス
│   │   ├── rss_scraper.py    # RSS フィード取得
│   │   └── x_scraper.py      # X API 連携
│   │
│   ├── notifier/             # 通知サービス
│   │   └── slack_sender.py   # Slack Webhook 送信
│   │
│   └── scheduler/            # スケジューリング（Phase 2）
│       └── jobs.py
│
├── tests/                    # テスト（Phase 2）
│   ├── test_rss_scraper.py
│   ├── test_x_scraper.py
│   └── test_notifier.py
│
└── data/                     # データディレクトリ
    └── ai_news.db           # SQLite データベース
```

## 実装フェーズ

### Phase 1: MVP（完成）

- ✅ X API キーワード検索
- ✅ RSS フィード取得
- ✅ Slack Webhook 通知
- ✅ SQLite 重複防止
- ✅ 手動実行スクリプト

### Phase 2: スケジューリング（進行中）

- ⏳ APScheduler で定期実行（朝8時・夜20時）
- ⏳ FastAPI エンドポイント化（オプション）
- ⏳ Docker 化

### Phase 3: 拡張機能（将来）

- 🎯 Claude API による自動要約
- 🎯 関連性判定（ユーザー関心度スコアリング）
- 🎯 Google Sheets への自動記録
- 🎯 Web UI ダッシュボード（Streamlit）

## トラブルシューティング

### X API エラー

**「X_BEARER_TOKEN is not set」**
```bash
# 環境変数が設定されていません
export X_BEARER_TOKEN=your_token_here
```

**「Rate limit exceeded」**
```
X API は 15 分あたり 300 リクエストの制限があります。
少し待ってから再度実行してください。
```

### Slack エラー

**「SLACK_WEBHOOK_URL is not configured」**
```bash
# 環境変数が設定されていません
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

**「Unauthorized」**
- Webhook URL が正しいか確認
- Slack ワークスペースの設定を確認

## テスト

```bash
# ユニットテスト実行
pytest

# カバレッジ計測
pytest --cov=services --cov=shared

# コード品質チェック
flake8 main.py services/ shared/
black main.py services/ shared/
mypy main.py services/ shared/
```

## 参考リンク

- [X API v2 Documentation](https://developer.twitter.com/en/docs/twitter-api)
- [Slack API - Webhooks](https://api.slack.com/messaging/webhooks)
- [feedparser Documentation](https://feedparser.readthedocs.io/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)

## ライセンス

MIT License

## 作成者

竹中純也（ugu00x）
- GitHub: https://github.com/ugu00x-cell
- Zenn: https://zenn.dev/

---

## 更新ログ

### 2026-08-15
- Phase 1 MVP 完成
  - X API キーワード検索実装
  - RSS フィード取得実装
  - Slack 通知実装
  - SQLite 永続化実装
  - 手動実行スクリプト完成
