# 不動産広告データ補完プロジェクト

物件マスタ（research_results テーブル）の欠損値を、SUUMO・HOLMES のデスクトップリサーチで自動補完するプロジェクトです。

## 🎯 目的

BigQueryの `research_results` テーブルにおいて、以下6項目の欠損を補完します：

**優先度順（8/12までに完成）：**
1. ✅ **郵便番号1・2** - `zipcode_master` テーブルとの JOIN
2. ✅ **総戸数住居** - SUUMO・HOLMES スクレイピング
3. **駅名コード** - Fuzzy matching で既存コード対応テーブルとの突合
4. **沿線名コード** - Fuzzy matching で既存コード対応テーブルとの突合
5. **土地の権利区分** - スクレイピング or マスタ照合

## 📁 プロジェクト構成

```
kuroco_property_completion/
├── services/
│   ├── bigquery_handler.py     # BigQuery 操作ハンドラー
│   ├── zipcode_fetcher.py      # 郵便番号補完ロジック
│   └── suumo_scraper.py        # SUUMO・HOLMES スクレイピング
├── utils/
│   └── text_matcher.py         # 表記ゆれ補正（予定）
├── main.py                     # フェーズ1実行スクリプト
├── check_schema.py             # BigQuery スキーマ確認
├── requirements.txt            # 依存パッケージ
└── README.md                   # このファイル
```

## 🚀 セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Google Cloud 認証

既に環境構築済みの場合は不要です。
必要に応じて以下を設定：

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
```

### 3. テーブルスキーマの確認

```bash
python check_schema.py
```

## 📋 使用方法

### Phase 1 実行（郵便番号補完 + スクレイピング試験）

```bash
python main.py
```

**実行内容：**
- ① 郵便番号未入力レコードを `zipcode_master` で補完
- ② SUUMO・HOLMES の sample URLs (3件) から総戸数を試験スクレイピング
- ③ 結果をログ出力

### 結果ファイル

- `app.log` - 詳細ログ（実行内容・エラー情報）

## 🔧 技術スタック

| 項目 | 技術 |
|------|------|
| **BigQuery** | google-cloud-bigquery |
| **スクレイピング** | Selenium + BeautifulSoup4 |
| **ブラウザ** | Chrome WebDriver |
| **テキストマッチング** | difflib / fuzzywuzzy |
| **ロギング** | Python logging |

## ⚠️ 注意事項

### カラム名について

実装に使用しているカラム名は、BigQuery の実際のスキーマに基づいて調整が必要です。

**確認すべきカラム：**
- `yubinkodo1`, `yubinkodo2` - 郵便番号
- `todofuken`, `shikuchoson` - 都道府県・市区町村
- `soukosujuukyo` - 総戸数住居
- `ekimei` - 駅名
- `ensenmei` - 沿線名
- `tochinokenrikubun` - 土地の権利区分
- `source_url` - ソースURL

### スクレイピング

SUUMO・HOLMES のページ構造は定期的に変更される可能性があります。
セレクタが機能しない場合は、該当のメソッドを調整してください。

## 📊 実行結果例

```
==================================================
PHASE 1: Zipcode + Scraping Test (Aug 11)
==================================================

==================================================
Phase 1: Complementing zipcode
==================================================
[INFO] Fetched 128 records with missing zipcode
[INFO] Complemented 98 records with zipcode
✓ Complemented 98 records with zipcode

==================================================
Phase 2: Testing total units scraping
==================================================
[1/3] Scraping: https://suumo.jp/...
✓ Extracted: {'total_units': '123', 'stories': '10', ...}
...

==================================================
SUMMARY
==================================================
✓ Zipcode complemented: 98 rows
✓ Scraping test completed: 3 properties
==================================================
```

## 🐛 トラブルシューティング

### BigQuery 接続エラー

```
google.auth.exceptions.DefaultCredentialsError: ...
```

**対処法：**
- Google Cloud 認証の設定を確認
- `GOOGLE_APPLICATION_CREDENTIALS` 環境変数の確認

### Chrome WebDriver エラー

```
selenium.common.exceptions.WebDriverException: ...
```

**対処法：**
- Chrome ブラウザがインストールされているか確認
- Chrome WebDriver のバージョンを確認
- `pip install webdriver-manager` でドライバー管理をインストール

### スクレイピング失敗

セレクタが正しくない場合、抽出失敗のログが出ます。
該当するサイトのページ構造を確認して、セレクタを調整してください。

## 📝 実装ロードマップ

| フェーズ | 内容 | 期限 |
|---------|------|------|
| Phase 1 | ①郵便番号 + ②総戸数試験 | 2026-08-11 |
| Phase 2 | ③駅名コード + ④沿線名コード + ⑤土地権利 | 2026-08-12 |
| Phase 3 | 品質検証・クライアント納品 | 2026-08-12 |

## 👤 作成者

竹中純也 (Claude Code Byob Coding)

## 📅 更新履歴

- **2026-08-11**: Phase 1 基本実装完成
  - BigQuery ハンドラー実装
  - 郵便番号補完ロジック実装
  - スクレイピング基本実装

