# AI News Monitor - デプロイ & トラブルシューティングガイド

## 目次

1. [認証情報の取得](#認証情報の取得)
2. [ローカルセットアップ](#ローカルセットアップ)
3. [動作確認](#動作確認)
4. [本番デプロイ](#本番デプロイ)
5. [トラブルシューティング](#トラブルシューティング)
6. [運用・メンテナンス](#運用メンテナンス)

---

## 認証情報の取得

### 1. X API v2 Bearer Token 取得

#### 前提条件
- X Developer Account が必要
- API Access Level: **Elevated** 以上推奨

#### 取得手順

1. **X Developer Portal にログイン**
   - https://developer.twitter.com/en/portal/dashboard

2. **Keys and Tokens セクションで Bearer Token を生成**
   ```
   Projects & Apps > App > Keys & Tokens > Bearer Token
   ```

3. **Bearer Token をコピー**
   ```
   AAAABxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

#### API v2 検索制限
- **無料プラン**：100 tweets/month
- **基本プラン（Elevated）**：300 requests/15分
- **本番プラン**：450 requests/15分

⚠️ **注意**：API v2 の最近のツイート検索は有料プラン要否が変更されている可能性があります。
→ https://developer.twitter.com/en/docs/twitter-api/tweets/search-integrate/integrate-recent-search

### 2. Slack Webhook URL 取得

#### 前提条件
- Slack ワークスペースへのアクセス権（Admin or 権限あるユーザー）

#### 取得手順

1. **Slack API ページにアクセス**
   - https://api.slack.com/apps

2. **アプリを作成**
   ```
   Create an App > From scratch
   ```

3. **アプリ名・ワークスペースを選択**
   ```
   App Name: ai-news-monitor
   Workspace: (your workspace)
   ```

4. **Incoming Webhooks を有効化**
   ```
   Features > Incoming Webhooks > On
   ```

5. **新しい Webhook URL を作成**
   ```
   Add New Webhook to Workspace
   ```

6. **通知先チャンネルを選択**
   ```
   Channel: #ai-news (または任意のチャンネル)
   ```

7. **Webhook URL をコピー**
   ```
   https://hooks.slack.com/services/{TEAM_ID}/{CHANNEL_ID}/{TOKEN}
   ```
   
   例：`https://hooks.slack.com/services/T00000000/B00000000/xxxxxxxx...`

---

## ローカルセットアップ

### 環境構築

```bash
# 1. リポジトリをクローン
git clone https://github.com/ugu00x-cell/digital-analysis-tool.git
cd digital-analysis-tool/ai-news-monitor

# 2. Python 仮想環境を作成
python -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. .env ファイルを作成
cp .env.example .env
```

### .env に認証情報を設定

```bash
# .env を開いて以下を入力

# X API
X_BEARER_TOKEN=AAAABxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXX

# その他（オプション）
LOG_LEVEL=INFO
ENVIRONMENT=development
SCHEDULER_MORNING_HOUR=8
SCHEDULER_MORNING_MINUTE=0
SCHEDULER_EVENING_HOUR=20
SCHEDULER_EVENING_MINUTE=0
```

⚠️ **.env ファイルは .gitignore に含まれているので、絶対にコミットしないように！**

---

## 動作確認

### 1. 設定をバリデート

```bash
python main.py --validate-config
```

期待出力：
```
[INFO] Validating configuration...
[INFO] Configuration is valid!
```

エラーが出た場合は、.env を確認してください。

### 2. Slack テストメッセージを送信

```bash
python main.py --test-slack
```

期待出力：
```
[INFO] Sending test message to Slack...
[INFO] Test message sent successfully!
```

**Slack に以下のメッセージが届きます**：
```
:rocket: AI News Monitor is working!
This is a test message from ai-news-monitor.
```

エラーが出た場合：
- Webhook URL が正しいか確認
- チャンネルが public か確認
- Slack ワークスペースの権限を確認

### 3. ドライラン（Slack 通知なし）

```bash
python main.py --dry-run
```

期待出力：
```
[INFO] Fetching RSS feeds...
[INFO] RSS: 10 items collected
[INFO] Searching X API for keywords...
[INFO] X Search: 5 items collected
[INFO] DRY RUN: Skipping Slack notification
[INFO] Would send 15 items to Slack
```

### 4. 通常実行（RSS + X API → Slack 通知）

```bash
python main.py
```

期待出力：
```
[INFO] Fetching RSS feeds...
[INFO] RSS: 10 items collected
[INFO] Searching X API for keywords...
[INFO] X Search: 5 items collected
[INFO] Saving to database...
[INFO] Database: 15 items saved, 0 duplicates
[INFO] Sending to Slack...
[INFO] Successfully notified 15 items to Slack
```

**Slack に:**
- `:newspaper: AI News Update - 15 new items` というメッセージが届く
- 各記事が色分けされたアタッチメント形式で表示される

---

## 本番デプロイ

### オプション 1: VPS（最も推奨）

#### 前提条件
- Ubuntu 20.04 以上
- Python 3.11 以上
- Docker & Docker Compose

#### デプロイ手順

```bash
# 1. サーバーに SSH ログイン
ssh user@your-server.com

# 2. リポジトリをクローン
git clone https://github.com/ugu00x-cell/digital-analysis-tool.git
cd digital-analysis-tool/ai-news-monitor

# 3. .env ファイルをアップロード
# ローカルから
scp .env user@your-server.com:~/digital-analysis-tool/ai-news-monitor/

# 4. Docker で起動
docker-compose up -d

# 5. ログを確認
docker-compose logs -f
```

#### 動作確認

```bash
# コンテナが起動しているか確認
docker-compose ps

# ログを確認
docker-compose logs -f ai-news-monitor

# ジョブをリスト
docker-compose exec ai-news-monitor python main.py --list-jobs
```

#### 停止・再起動

```bash
# 再起動
docker-compose restart

# 停止
docker-compose down
```

### オプション 2: Heroku

#### 前提条件
- Heroku アカウント
- Heroku CLI

#### デプロイ手順

```bash
# 1. Heroku にログイン
heroku login

# 2. Heroku アプリを作成
heroku create your-app-name

# 3. 環境変数を設定
heroku config:set X_BEARER_TOKEN=xxxxxx
heroku config:set SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# 4. Procfile を作成
cat > Procfile << EOF
worker: python main.py --daemon
EOF

# 5. デプロイ
git push heroku main

# 6. ログを確認
heroku logs -f
```

### オプション 3: GCP Cloud Run

#### 前提条件
- Google Cloud Platform アカウント
- gcloud CLI

#### デプロイ手順

```bash
# 1. GCP にログイン
gcloud auth login

# 2. Docker イメージをビルド
docker build -t gcr.io/your-project/ai-news-monitor .

# 3. Container Registry にプッシュ
docker push gcr.io/your-project/ai-news-monitor

# 4. Cloud Run にデプロイ
gcloud run deploy ai-news-monitor \
  --image gcr.io/your-project/ai-news-monitor \
  --platform managed \
  --region us-central1 \
  --set-env-vars X_BEARER_TOKEN=xxxxx,SLACK_WEBHOOK_URL=https://...

# 5. ログを確認
gcloud logging read "resource.labels.service_name=ai-news-monitor"
```

⚠️ **注意**：Cloud Run は無状態で、デフォルトでは 15 分で終了します。
→ Cloud Scheduler + Cloud Functions で定期実行を推奨

---

## トラブルシューティング

### X API エラー

#### 「X_BEARER_TOKEN is not configured」

**原因**：環境変数が設定されていない

**解決方法**：
```bash
# .env を確認
cat .env | grep X_BEARER_TOKEN

# または環境変数を直接設定
export X_BEARER_TOKEN=xxxxxx
```

#### 「Rate limit exceeded」（429 エラー）

**原因**：X API の 15 分あたりのリクエスト制限に達した

**解決方法**：
- 少し待ってから再度実行
- キーワード数を減らす
- `X_REQUEST_DELAY_SEC` を増やす（デフォルト: 1.0秒）

```bash
export X_REQUEST_DELAY_SEC=2.0
```

#### 「Unauthorized」（401 エラー）

**原因**：Bearer Token が無効または失効

**解決方法**：
1. X Developer Portal で新しい Token を生成
2. .env を更新
3. アプリを再起動

### Slack エラー

#### 「SLACK_WEBHOOK_URL is not configured」

**原因**：Webhook URL が設定されていない

**解決方法**：.env を確認・設定

#### 「Unauthorized」（401 エラー）

**原因**：Webhook URL が無効

**解決方法**：
1. Slack API ページで新しい Webhook を生成
2. .env を更新
3. テストメッセージを送信

```bash
python main.py --test-slack
```

#### 「Channel not found」

**原因**：指定したチャンネルが存在しない

**解決方法**：
- Slack API で正しいチャンネル名を指定
- チャンネルが public か確認
- bot がチャンネルに参加しているか確認

### データベースエラー

#### 「database is locked」

**原因**：複数のプロセスが同時に DB にアクセス

**解決方法**：
- デーモンプロセスを 1 つだけ起動
- 別のプロセスが DB をロックしていないか確認

```bash
# プロセスを確認
ps aux | grep main.py

# 不要なプロセスを終了
kill -9 <PID>
```

---

## 運用・メンテナンス

### ログ確認

```bash
# リアルタイムログ
tail -f logs/ai_news_monitor.log

# 昨日のログ
grep "2026-08-14" logs/ai_news_monitor.log

# エラーのみ
grep "ERROR" logs/ai_news_monitor.log
```

### 定期メンテナンス

#### 古い記事の削除（30日以上前）

```python
from shared.database import get_database

db = get_database()
deleted_count = db.delete_old_records(days=30)
print(f"Deleted {deleted_count} old records")
```

#### 定期バックアップ

```bash
# データベースをバックアップ
cp data/ai_news.db data/ai_news.db.backup.$(date +%Y%m%d)

# 圧縮
gzip data/ai_news.db.backup.*
```

### スケジュール変更

```bash
# 朝10時・夜22時に変更したい場合
export SCHEDULER_MORNING_HOUR=10
export SCHEDULER_EVENING_HOUR=22

# デーモンを再起動
docker-compose restart
# または
python main.py --daemon
```

### 監視・アラート設定

#### cron でエラーを監視する例

```bash
# crontab -e で追加
*/5 * * * * if ! docker ps | grep -q ai-news-monitor; then echo "AI Monitor is down!" | mail -s "Alert" admin@example.com; fi
```

---

## サポート・問い合わせ

問題が解決しない場合：

1. **ログを確認** → logs/ai_news_monitor.log
2. **GitHub Issues** → https://github.com/ugu00x-cell/digital-analysis-tool/issues
3. **テストを実行** → `python -m pytest tests/ -v`

---

**最終更新**: 2026-08-15  
**バージョン**: 1.0.0 (Phase 2)
