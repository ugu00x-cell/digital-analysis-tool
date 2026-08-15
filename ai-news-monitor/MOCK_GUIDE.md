# AI News Monitor - モック版ガイド

API 認証情報を用意せずに、**サンプルデータで完全な動作確認ができます** 🎭

---

## 概要

### モック版とは？

- ✅ X API なし（Twitter API を呼び出さない）
- ✅ Slack Webhook なし（通知しない）
- ✅ サンプルニュース 8件で全フローをテスト
- ✅ データベース保存・ログ・エラーハンドリング完全動作

### モック版でテストできること

```
✅ ニュースアイテムの生成
✅ データベースへの保存
✅ 重複防止機構の動作確認
✅ ログ記録
✅ エラーハンドリング
✅ 本番コードの動作確認

❌ できないこと
  - 実際の X API データ取得
  - 実際の Slack 通知
  - RSS フィード解析（代わりにサンプルデータ使用）
```

---

## クイックスタート

### 1. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 2. モック版を実行

```bash
python main_mock.py --show-samples
```

期待出力：
```
============================================================
AI News Monitor - モック版
実行時刻: 2026-08-15 20:45:30
============================================================
============================================================
【モック版】情報収集を開始
============================================================
✓ サンプル ニュース 8 件を生成
  - Twitter: 4件
  - RSS: 4件
============================================================
============================================================
生成されたサンプルニュース
============================================================

【1】Claude 3.5 Sonnet API が全ユーザーに開放
    ソース: TWITTER
    キーワード: Claude, API
    著者: Anthropic
    公開日: 2026-08-15 18:45

【2】RAG（検索拡張生成）の最新ベストプラクティス
    ソース: TWITTER
    キーワード: RAG, LLM
    著者: Hugging Face
    公開日: 2026-08-15 17:45

...（以下略）
```

---

## 実行オプション

### オプション 1: サンプルニュースを表示

```bash
python main_mock.py --show-samples
```

✅ 生成されたサンプルニュース 8 件が画面に表示されます

### オプション 2: ドライラン（DB 保存のみ、Slack 通知なし）

```bash
python main_mock.py --dry-run
```

✅ Slack 通知をスキップして、DB に保存します

実行ログ：
```
============================================================
データベースに保存中...
============================================================
✓ 8 件を保存
============================================================
🔵 ドライラン：Slack 通知をスキップします
   → 実際には 8 件の記事が通知されます
```

### オプション 3: サンプルと合わせて表示

```bash
python main_mock.py --show-samples --dry-run
```

✅ サンプルニュース一覧 → DB 保存 → Slack スキップ

### オプション 4: Slack 通知も有効化（本番のように実行）

```bash
python main_mock.py --with-slack
```

⚠️ **前提条件**：
- `.env` ファイルで `SLACK_WEBHOOK_URL` が設定されていること
- Slack Webhook URL が有効であること

実行ログ：
```
============================================================
Slack 通知を送信中...
============================================================
✓ Slack に 8 件を通知しました
```

---

## サンプルデータの内容

モック版では以下のサンプルニュースが生成されます：

| # | タイトル | ソース | キーワード | 著者 |
|----|---------|--------|-----------|------|
| 1 | Claude 3.5 Sonnet API が全ユーザーに開放 | Twitter | Claude, API | Anthropic |
| 2 | RAG（検索拡張生成）の最新ベストプラクティス | Twitter | RAG, LLM | Hugging Face |
| 3 | OpenAI の GPT-5 トレーニングが加速 | Twitter | AI, LLM | OpenAI |
| 4 | TechCrunch: AI スタートアップが 5 億ドルの資金調達 | RSS | AI | TechCrunch |
| 5 | Hacker News: LLM の推論速度を 10 倍高速化 | RSS | LLM | Hacker News |
| 6 | MIT: 次世代 AI チップが記録的なパフォーマンス達成 | RSS | AI | MIT News |
| 7 | Data Science 最新トレンド：AutoML の実用化 | RSS | Data Science | Data Science Weekly |
| 8 | Google の新しい Gemini Ultra モデル | Twitter | Claude, API | Google DeepMind |

**特徴**：
- Twitter / RSS 両ソースを含む
- 複数のキーワード（Claude, API, RAG, LLM, AI 等）でマッチ
- 異なる著者（Anthropic, OpenAI, Google 等）
- 時系列データ（直近 8 時間）

---

## データベース確認

モック版で保存したデータを確認できます：

### 方法 1: SQLite CLI で確認

```bash
sqlite3 data/ai_news.db
```

```sql
-- テーブル構造を確認
.schema news_items

-- すべてのニュースを表示
SELECT title, source, author FROM news_items;

-- キーワード別に検索
SELECT * FROM news_items WHERE keywords LIKE '%Claude%';

-- ソース別に集計
SELECT source, COUNT(*) FROM news_items GROUP BY source;

-- 終了
.quit
```

### 方法 2: Python で確認

```python
from shared.database import get_database

db = get_database()
items = db.get_news_items_since(hours=24)

for item in items:
    print(f"📰 {item.title[:50]}")
    print(f"   {item.source.upper()} | {', '.join(item.keywords)}")
    print()
```

---

## テスト実行

### テスト 1: モック版の基本動作

```bash
python main_mock.py --show-samples --dry-run
```

✅ サンプルニュースが表示され、DB に保存される

### テスト 2: データベース動作確認

```bash
# モック版を実行
python main_mock.py --dry-run

# DB を確認
sqlite3 data/ai_news.db "SELECT COUNT(*) FROM news_items;"
```

✅ 8件が保存されていることを確認

### テスト 3: 重複防止機能

```bash
# 1回目：8件を保存
python main_mock.py --dry-run

# 2回目：同じ内容を実行
python main_mock.py --dry-run
```

✅ ログで「重複スキップ: 8 件」と表示される

---

## 本番版への移行

### Step 1: モック版で動作確認

```bash
python main_mock.py --show-samples --dry-run
```

### Step 2: 実際の API を取得

- X API Bearer Token（[DEPLOYMENT.md](DEPLOYMENT.md) 参照）
- Slack Webhook URL（[DEPLOYMENT.md](DEPLOYMENT.md) 参照）

### Step 3: .env に設定

```bash
cp .env.example .env
# 以下を入力
X_BEARER_TOKEN=xxxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Step 4: 本番版で実行

```bash
# テスト
python main.py --validate-config
python main.py --test-slack
python main.py --dry-run

# 本番実行
python main.py
```

---

## よくある質問

### Q: モック版は本番データを使用しないので安全ですか？

**A: はい、完全に安全です** ✅

- X API を呼び出さない
- Slack に通知しない
- サンプルデータのみを使用
- データベースにも保存される（テスト用）

### Q: モック版でログや DB に保存されたデータを削除したい場合は？

**A: 以下で削除できます**

```bash
# ログファイルを削除
rm logs/ai_news_monitor.log

# データベースをリセット
rm data/ai_news.db
```

次回実行時に新しいファイルが自動作成されます。

### Q: モック版をカスタマイズしたい（サンプルデータを追加・変更したい）

**A: `generate_sample_news_items()` 関数を編集**

```python
# main_mock.py の generate_sample_news_items() 関数を開く
# NewsItem を追加

def generate_sample_news_items() -> list[NewsItem]:
    """..."""
    now = datetime.now()
    
    return [
        # 既存のアイテム...
        
        # 新しく追加
        NewsItem(
            title="My Custom News Title",
            source="rss",
            url="https://example.com/custom",
            published_at=now - timedelta(hours=9),
            keywords=["Custom", "Keyword"],
            raw_text="Custom news content",
            author="Custom Author",
        ),
    ]
```

### Q: モック版でも Slack に通知したい場合は？

**A: `--with-slack` フラグを使用**

```bash
# .env に SLACK_WEBHOOK_URL が設定されていることを確認
python main_mock.py --with-slack
```

✅ Slack に 8 件のサンプルニュースが通知されます

---

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'feedparser'`

**解決方法：**
```bash
pip install -r requirements.txt
```

### エラー: `database is locked`

**解決方法：**
```bash
# プロセスを終了
ps aux | grep main_mock.py
kill -9 <PID>

# DB をリセット
rm data/ai_news.db
```

### エラー: `SLACK_WEBHOOK_URL is not configured`（--with-slack 実行時）

**解決方法：**
```bash
# .env を確認
cat .env | grep SLACK_WEBHOOK_URL

# 設定されていなければ追加
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/..." >> .env
```

---

## まとめ

| 実行方法 | 用途 | API 必要 |
|---------|------|---------|
| `python main_mock.py --show-samples --dry-run` | 動作確認 | ❌ |
| `python main.py --dry-run` | 本番シミュレーション | ✅ X API |
| `python main.py` | 本番実行 | ✅ X API + Slack |
| `python main.py --daemon` | 24時間自動実行 | ✅ X API + Slack |

**モック版で完全な動作確認ができるため、API 取得前に本番コードの品質を検証できます** ✨

---

**最終更新**: 2026-08-15  
**バージョン**: 1.0.0 (Mock Edition)
