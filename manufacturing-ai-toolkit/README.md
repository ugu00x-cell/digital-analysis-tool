# Manufacturing AI Toolkit

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-red.svg)](https://pytorch.org/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4%2B-F7931E.svg)](https://scikit-learn.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![C++](https://img.shields.io/badge/C%2B%2B-Arduino%2FPlatformIO-orange.svg)](https://platformio.org/)

> **製造業15年の現場経験 × Python実装による異常検知・分類フレームワーク**

実験室データ・公開ベンチマーク・自作ハードウェアからの実機データを横断的に扱い、
**「現場で本当に検知したいもの」**を軸に設計した製造業向けツールキットです。

---

## このリポジトリの位置付け

本リポジトリは、**製造業データ分析フレームワーク**の数値データ編です。

| 系統 | リポジトリ | 対象 | 状態 |
|---|---|---|---|
| **数値データ系（本リポジトリ）** | `manufacturing-ai-toolkit` | 振動・音響・加工条件 | ✅ 公開中 |
| CWRU/NASA ベアリング専用 | [`bearing-anomaly-detection`](https://github.com/ugu00x-cell/bearing-anomaly-detection) | CWRU + NASA IMS の導入解析 | ✅ 公開中 |
| 予知保全API | [`predictive-maintenance-api`](https://github.com/ugu00x-cell/predictive-maintenance-api) | M5StickC→FastAPI→Slack | ✅ 公開中 |
| 自然言語データ系 | `defect-text-classification` | 不良報告書のLLM分類 | 🗓 スケルトンのみ |

各リポジトリを単体で使うことも、組み合わせて予知保全プロダクトの下地にすることもできます。

---

## 対象データセット一覧

本リポジトリで扱うベアリング・音響異常検知のベンチマーク:

| データセット | サンプリング | 種別 | 主な用途 |
|---|---|---|---|
| **CWRU** | 12 kHz | 実験室・意図的損傷 | 入門／特徴量設計（[別リポジトリ](https://github.com/ugu00x-cell/bearing-anomaly-detection)）|
| **NASA IMS** | 20 kHz | 実稼働・Run-to-Failure | 自然劣化の追体験（[別リポジトリ](https://github.com/ugu00x-cell/bearing-anomaly-detection)）|
| **XJTU-SY** | 25.6 kHz | 実稼働・3条件 × 15ベアリング | 運転条件クロス検証 |
| **FEMTO (PRONOSTIA)** | 25.6 kHz | 実稼働・振動+温度 | マルチセンサー解析 |
| **DCASE 2026 Task 2** | 16 kHz | 音響・Bearing (Emu) | 異常音検知ベースライン |

---

## モジュール構成

```
manufacturing-ai-toolkit/
├── bearing_datasets/
│   ├── xjtu_sy/                    # XJTU-SY ベアリング異常検知
│   └── femto/                      # FEMTO ベアリング異常検知（振動+温度）
├── threshold_analysis/             # 3段階しきい値比較フレームワーク
├── dcase2026_baseline/             # DCASE 2026 Task 2 音響異常検知
├── anomaly_detection_generic/      # 汎用センサー異常検知
├── milling_optimization/           # 加工条件最適化
└── hardware/                       # 自作センサー実装
    ├── m5stick_accel/
    ├── m5stick_wifi_test/
    └── m5stack_vibration/
```

### 1. `bearing_datasets/`

**XJTU-SY ベアリング解析** (`xjtu_sy/`)
- 3つの運転条件（回転数・荷重）× 5ベアリング × 3セットを解析
- Condition1 (2100rpm/12kN) で学習したモデルを Condition2/3 でクロス検証
- 水平・垂直2軸の特徴量抽出（h_rms, h_kurtosis, ...）
- スクリプト: `download_data.py`, `feature_extract.py`, `anomaly_detect.py`, `cross_condition.py`, `visualize.py`

**FEMTO/PRONOSTIA ベアリング解析** (`femto/`)
- 17ベアリング × 3条件の Run-to-Failure データ
- エンベロープRMS（ヒルベルト変換）による早期検出
- 温度センサーとの多変量解析
- スクリプト: `download_data.py`, `feature_extract.py`, `anomaly_detect.py`, `compare_bearings.py`, `multi_sensor.py`, `individual_vs_common.py`, `visualize.py`

### 2. `threshold_analysis/` — 3段階しきい値比較フレームワーク

「製造業の段階的アラーム（注意/警告/危険）の基準を科学的に決める」ためのフレームワーク。

| Stage | アプローチ | モデル |
|---|---|---|
| Stage 1 | 統計ベース | 平均+Nσ / パーセンタイル / MAD |
| Stage 2 | 機械学習 | IsolationForest / One-Class SVM |
| Stage 3 | ディープラーニング | LSTM-AutoEncoder |

4データセット（CWRU・NASA・XJTU-SY・FEMTO）で手法を横断比較し、
データの変動係数に応じて最適な手法を自動選定する。

**実行例**
```bash
cd threshold_analysis
python run_comparison.py
```

→ `threshold_config.json`（全手法の基準値）と `comparison_report.csv`（比較テーブル）を出力。

### 3. `dcase2026_baseline/` — DCASE 2026 Task 2 音響異常検知

DCASE Challenge 2026 Task 2 の Bearing (Emu) データセット向けベースライン。

- メルスペクトログラム抽出（128 mel × 5 frames）
- Dense AutoEncoder で再構成誤差ベースの異常検知
- AUC-ROC + Partial AUC で評価

**実行例**
```bash
cd dcase2026_baseline
python -m main  # データ不在時は合成データで動作確認
```

### 4. `anomaly_detection_generic/` — 汎用センサー異常検知

IsolationForest + 3σ ルールのデュアル手法による汎用センサーデータ異常検知モジュール。
温度・圧力・振動の合成データで動作確認済み。

### 5. `milling_optimization/` — 加工条件最適化

Streamlit UI + 機械学習による加工条件（回転数・送り・切り込み）最適化ツール。
OSG社の工具データベースからの取り込みスクリプトも同梱。

### 6. `hardware/` — 自作センサー実装

M5StickC Plus2 / M5Stack Core シリーズ向けの振動データ収集ファームウェア。

| ディレクトリ | 用途 |
|---|---|
| `m5stick_accel/` | StickCP2 で3軸加速度を取得し GAS (Google Apps Script) にPOST送信 |
| `m5stick_wifi_test/` | WiFi接続確認用の軽量ファーム（PlatformIO） |
| `m5stack_vibration/` | 高レートな振動データ収集（SPIFFS保存） |

**⚠️ セキュリティ注意**
- WiFi SSID/パスワードはすべて `YOUR_WIFI_SSID` 等のプレースホルダーに置換済み
- GAS URL も `YOUR_DEPLOY_ID` プレースホルダーに置換済み
- 使用時は各自の環境に合わせて書き換えてください

---

## 動作環境

- **Python**: 3.10 以上
- **OS**: Windows 11 / WSL2 で動作確認
- **GPU**: NVIDIA RTX 2070 (CUDA 12.4) で確認。CPU のみでも動作可能

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/ugu00x-cell/manufacturing-ai-toolkit.git
cd manufacturing-ai-toolkit

# 仮想環境を推奨
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt

# GPU を使う場合は torch を個別インストール
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

### 主要な依存ライブラリ

| カテゴリ | ライブラリ |
|---|---|
| 数値計算 | numpy, scipy, pandas |
| 機械学習 | scikit-learn (IsolationForest, OCSVM, RandomForest, StandardScaler) |
| ディープラーニング | torch, torchvision |
| 音響処理 | librosa, soundfile |
| 可視化 | matplotlib |
| ユーティリティ | tqdm, requests, pyyaml |

---

## 使い方の例

### XJTU-SY で Condition1 → Condition2/3 のクロス検証

```bash
cd bearing_datasets/xjtu_sy
python download_data.py         # データをダウンロード
python feature_extract.py       # 特徴量抽出
python cross_condition.py       # Condition間のドメイン転移検証
```

### 段階的アラームしきい値の最適化

```bash
cd threshold_analysis
python stage1_statistical.py    # 統計ベースの基準値
python run_comparison.py        # 全手法の比較レポート
```

### DCASE 2026 音響異常検知

```bash
cd dcase2026_baseline
python -m utils.download_data   # データ取得（約600MB）
python -m main                  # Dense AE ベースラインの全パイプライン実行
```

---

## 主要な知見（現場目線のコメント）

1. **「ピーク→フェードアウト→破損」パターン (NASA)** — 劣化の一時安定期が最も危険。詳細は [別リポジトリ](https://github.com/ugu00x-cell/bearing-anomaly-detection)
2. **運転条件によるモデルの転移失敗 (XJTU-SY)** — Condition1 で学習したモデルの Condition3 での精度は30%低下する
3. **固定倍率しきい値は高変動データで機能しない (Threshold Analysis)** — XJTU-SYの場合、120%固定倍率では注意しきい値が0.5σしかない
4. **AE系の Information Leak (DCASE)** — モデルを強くするほど異常音まで再構成してしまう。SOTAは Mahalanobis 距離など

---

## 今後の展望

### 本リポジトリの発展
- [ ] 実機（工作機械）のデータを M5StickC Plus2 で取得しパイプラインを実行
- [ ] 時間の概念追加（劣化速度・変化開始時点の検出 → 残寿命推定）
- [ ] PaDiM風 Mahalanobis距離スコアリングの導入（DCASE）

### フレームワーク全体の展開

本リポジトリは **製造業データ異常検知フレームワーク** の数値データ編です。
第二弾として、自然言語データ系 [`defect-text-classification`](https://github.com/ugu00x-cell/defect-text-classification) を準備中です。

**両者に共通する設計思想**
1. **分類体系の設計** — ラベル定義は現場知識と密結合
2. **教師データとの一致率検証** — モデル精度よりラベル品質の可視化が先
3. **再発防止への接続** — 検知で終わらず、原因分析と対策まで繋ぐ

数値と自然言語という異なるドメインでも、**設計思想は同じ**であることを示すのが目標です。

---

## 関連リポジトリ

| リポジトリ | 内容 |
|---|---|
| [bearing-anomaly-detection](https://github.com/ugu00x-cell/bearing-anomaly-detection) | CWRU + NASA IMS の導入解析（入門→実稼働の構成） |
| [predictive-maintenance-api](https://github.com/ugu00x-cell/predictive-maintenance-api) | M5StickC → FastAPI → Slack の予知保全API |
| defect-text-classification | 不良報告書の LLM 分類（スケルトン版） |

---

## ライセンス

MIT License. 詳細は [LICENSE](LICENSE) を参照してください。

---

## 著者

**竹中純也 (Junya Takenaka)**
- 製造業15年（加工技術5年 + 品質管理10年）
- GitHub: [@ugu00x-cell](https://github.com/ugu00x-cell)

本リポジトリは、現場の知見を機械学習に接続することを目的とした個人取り組みです。
