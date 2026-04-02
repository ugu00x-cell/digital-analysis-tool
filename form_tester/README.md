# form_tester — 企業サイトお問い合わせフォーム自動検出・テストツール

企業サイトのお問い合わせフォームを自動で検出・解析し、フィールドマッピングと送信テストを行うツールです。

## セットアップ

```bash
pip install playwright beautifulsoup4 pandas openai tqdm
python -m playwright install chromium
```

## 使い方

```bash
# 最初の20社をドライランでテスト
python main.py --dry-run --limit 20 input.csv

# 結果確認後、5社だけ実際に送信（10秒間隔）
python main.py --send --limit 5 --delay 10 input.csv

# 前回の続きから再開
python main.py --dry-run --resume input.csv

# ブラウザを表示して動作確認
python main.py --dry-run --limit 3 --headed input.csv
```

## 入力CSV

文字コード: UTF-8 BOM付き

```
企業名,企業サイトURL,電話番号,メールアドレス,業種,住所,代表者名,タグ
```

## 実行オプション

| オプション | 説明 | デフォルト |
|-----------|------|-----------|
| `--dry-run` | フォーム解析のみ、送信しない | 有効 |
| `--send` | 実際に送信する（確認プロンプト表示） | - |
| `--limit N` | 処理する企業数の上限 | 全件 |
| `--delay N` | 1件ごとの待機秒数 | 5 |
| `--headed` | ブラウザを画面表示する | headless |
| `--resume` | 前回中断した続きから再開 | - |

## ファイル構成

```
form_tester/
├── main.py       # エントリーポイント
├── scraper.py    # フォーム検出・解析（Playwright + BeautifulSoup）
├── mapper.py     # フィールドマッピング（キーワード + OpenAI API）
├── sender.py     # フォーム送信
├── logger.py     # ログ・レポート出力
└── config.py     # 設定値まとめ
```
