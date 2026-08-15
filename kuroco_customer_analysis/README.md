# kuroco_customer_analysis

KUROCO案件（新築分譲マンション販売データ分析）の追加スコープ：通勤距離分析用スクリプト。

`dj-ga4.scd.customer_data` から①住居最寄駅・②勤務地最寄駅・③購入物件最寄駅の駅名をユニーク抽出し、
Google Geocoding APIで緯度経度を取得、BigQuery側で直線距離（ST_DISTANCE）を算出する。

## 方式変更の経緯（2026/08/06）

当初はGoogle Maps Directions API（TRANSIT・乗換案内モード）で実際の電車移動時間を取得する方針だったが、
**Google Maps Platformの仕様上、日本の交通事業者はTRANSIT機能に非対応**であることが判明した
（DRIVEモードは正常動作、TRANSITのみ`ZERO_RESULTS`）。

クライアント合意の上、簡易指標として「駅間の直線距離」を採用する方式に変更した。
実際の電車移動時間ではなく、あくまで「近さの目安」である点に注意。

## セットアップ

### 1. 依存パッケージのインストール

```bash
cd C:\Users\ugu00\my-secretary
py -m pip install -r kuroco_customer_analysis/requirements.txt
```

### 2. Google Maps APIキーの設定

`dj-ga4` プロジェクトで発行した「Commute Time Directions API (server)」キーを環境変数に設定する
（Geocoding APIも同じキーで利用可能）。

```bash
set GOOGLE_MAPS_API_KEY=<発行したAPIキー>
```

### 3. BigQuery認証（サービスアカウント）

`commute-time-analysis@dj-ga4.iam.gserviceaccount.com` の鍵ファイル（JSON）へのパスを環境変数に設定する。

```bash
set GOOGLE_APPLICATION_CREDENTIALS=D:\ダウンロード\dj-ga4-b1503a438942.json
```

※ファイル名・保存先フォルダは実際の環境に合わせること。ファイルはGitにコミットしないこと。

## 実行

```bash
py -m kuroco_customer_analysis.main
```

ジオコーディング対象はユニークな駅名のみ（駅ペア単位ではない）なので、API呼び出し件数は数百〜千件程度に収まる見込み。

## テスト

```bash
py -m pytest kuroco_customer_analysis/tests/ -v
```

## 出力先

- `dj-ga4.scd.station_master`（駅名・緯度経度のマスタ）
- `dj-ga4.scd.commute_distance_results`（住居→勤務地・勤務地→物件の直線距離、メートル単位）

## 権限まわりのメモ

- サービスアカウント `commute-time-analysis@dj-ga4.iam.gserviceaccount.com` に `BigQuery データ編集者`・`BigQuery ジョブユーザー` を付与済み（2026/08/05・鬼塚さんに付与依頼）
- Google Maps APIキーは元々Directions API用に発行したものを流用（Geocoding APIも含めプロジェクトで有効な範囲のAPIが使える状態）
