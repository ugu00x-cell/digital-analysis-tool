# 📊 企業デジタル分析ツール

企業のWebサイトを自動分析し、デジタル成熟度を **7項目100点満点** でスコアリングするWebアプリです。  
スコアが低い企業ほど、Web制作・デジタルマーケティングの **営業対象候補** として抽出できます。

## 🌐 デモ

> **[▶ アプリを試す]([https://your-app-url.streamlit.app](https://digital-analysis-tool-esscfcgxuecerdf3riesem.streamlit.app/)**  
> ※ Streamlit Community Cloud で無料公開中

## ✨ 主な機能

### 🔍 単体分析
- URLを入力するだけで即座に分析
- 7項目のスコア内訳をレーダーチャートで可視化
- S〜Dの営業ランク自動判定

### 📋 一括分析
- 複数URLをテキスト入力またはCSVアップロードで一括分析
- プログレスバー付きリアルタイム進捗表示
- スコア昇順（営業対象が上位）のテーブル表示

### 📄 PDFレポート出力
- 1社ごとの詳細レポートPDF（営業提案資料として使用可能）
- 一括分析のサマリーPDF

### 📥 CSV出力
- 全分析項目を網羅したCSVダウンロード

## 📊 分析項目（7カテゴリ / 100点満点）

| カテゴリ | 配点 | 分析内容 |
|---------|------|---------|
| 🔒 HTTPS対応 | 10点 | SSL証明書の有無 |
| 🔍 SEO基礎 | 25点 | title, meta description, viewport, H1, favicon, canonical |
| 📱 SNS連携 | 15点 | Twitter/X, Facebook, Instagram, YouTube, LINE, TikTok等 |
| 📄 コンテンツ充実度 | 15点 | 総リンク数, 内部リンク数 |
| 📞 問い合わせ導線 | 15点 | フォーム, 電話番号, メール, 問い合わせページ |
| ⚙️ 技術・運用 | 10点 | Google Analytics, 構造化データ, OGP |
| 👥 採用ページ | 10点 | 採用関連ページの有無 |

## 🎯 営業ランク判定

| ランク | スコア | 判定 |
|--------|--------|------|
| **S** | 0〜25点 | 最優先ターゲット |
| **A** | 26〜40点 | 営業対象（高確度） |
| **B** | 41〜55点 | 営業対象（中確度） |
| **C** | 56〜70点 | 要検討 |
| **D** | 71〜100点 | 対象外（デジタル成熟） |

## 🛠 技術スタック

- **Python 3.13**
- **Streamlit** - WebアプリUI
- **BeautifulSoup4** - HTML解析
- **Requests** - HTTP通信
- **ReportLab** - PDF生成
- **カスタムCSS** - プロ仕様のUI/UX
- **SVG** - レーダーチャート（外部ライブラリ不使用）

## 🚀 ローカルで動かす

```bash
# リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/digital-analysis-tool.git
cd digital-analysis-tool

# 依存関係をインストール
pip install -r requirements.txt

# アプリを起動
streamlit run app.py
```

## 📁 ファイル構成

```
digital-analysis-tool/
├── app.py              # メインアプリケーション
├── pdf_report.py       # PDFレポート生成モジュール
├── requirements.txt    # Python依存関係
├── .streamlit/
│   └── config.toml     # Streamlit設定（テーマ等）
└── README.md           # このファイル
```

## 💡 活用シーン

- **Web制作会社の新規営業**: 地域の企業サイトを一括分析し、改善提案の営業リストを作成
- **デジタルマーケティング**: クライアント候補のデジタル成熟度を事前調査
- **競合分析**: 同業他社のWeb施策を比較分析

## 📝 開発背景

Web制作の営業活動において、手作業で企業サイトを1つずつ確認する非効率さを解消するために開発しました。URLを入力するだけで、SEO対策・SNS活用・問い合わせ導線などを自動チェックし、営業優先度を判定します。

## ⚠️ 注意事項

- 本ツールはWebサイトのHTML構造を分析するものであり、アクセス解析データ等は含まれません
- 分析対象サイトへの過度なアクセスを避けるため、一括分析には1秒間のインターバルを設けています
- スコアはあくまで参考値であり、実際の営業判断は総合的に行ってください

---

Made with ❤️ using Python & Streamlit
