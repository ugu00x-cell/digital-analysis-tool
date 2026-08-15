# 加工条件最適化ツール ── 工具摩耗予測 × 切削条件の自動最適化

**製造業15年（加工技術5年・品質管理10年）のエンジニアが、現場課題を自分で解決するために開発したツールです。**

## このツールが解決する現場課題

工作機械の加工現場では、切削条件の設定が作業者の経験に依存しています。

```
「この材料なら回転数これくらいかな」
「前にうまくいった条件をそのまま使おう」
「工具が欠けたから送りを落とそう」
```

経験則は属人的で、根拠が曖昧で、再現性がない。
このツールは **切削条件 → 工具摩耗量（VB）をMLモデルで予測** し、
**MRR（材料除去率）を最大化しつつ摩耗制約を満たす条件を自動提案** します。

---

## デモ（Streamlit Web UI）

```bash
streamlit run app.py
```

### タブ1：摩耗量予測
工具仕様（径・刃数・材種）と切削条件（Vc・fz・ap・ae）を入力すると、
VB（フランク摩耗量）をリアルタイム予測。状態バッジで危険度を表示。

| VB | 状態 |
|----|------|
| < 0.1mm | 🟢 良好 |
| < 0.2mm | 🟡 注意 |
| < 0.3mm | 🟠 警告 |
| ≥ 0.3mm | 🔴 交換推奨 |

### タブ2：工具寿命曲線 × トレードオフ分析
- VB vs 加工時間曲線（寿命限界0.3mmラインつき）
- 切削速度を振ったMRR vs 工具寿命のトレードオフ曲線

---

## 技術的な特徴

### 物理モデル（Taylor方程式）によるデータ生成

実データが手元にない段階でも検証できるよう、Taylor方程式ベースの合成データ生成機能を実装。

```
T = (C / Vc)^(1/n)
```

- **5材種対応**：S45C, SUS304, A5052, FC250, SKD11（材種ごとのTaylor定数を設定）
- **工具材種・クーラント係数**：超硬/CBN/セラミック、湿式/乾式/ミスト
- **VB摩耗進行の3段階モデル**：初期急速摩耗 → 定常摩耗 → 急速摩耗（現場で観察される実パターンを再現）

### 機械学習モデル

| モデル | チューニング | 用途 |
|--------|------------|------|
| RandomForest | GridSearchCV（n_estimators, max_depth） | ベースライン |
| XGBoost | GridSearchCV（n_estimators, max_depth, learning_rate） | 本番モデル |

- MAEで自動選択し `best_model.joblib` として保存
- 残差分析・特徴量重要度のプロットを自動生成

### 切削条件の最適化

- **scipy SLSQP法**：VB ≤ 制約値のもとでMRRを最大化
- **パレートフロント**：RPM × トルク空間のグリッド探索でMRR vs 摩耗のトレードオフを可視化

---

## プロジェクト構成

```
milling-tuning/
├── app.py                          # Streamlit Web UI（v3.0）
├── requirements.txt
├── src/
│   ├── data_loader.py              # UCI AI4I 2020データセット取得・前処理
│   ├── eda.py                      # EDA（相関ヒートマップ・分布・散布図）
│   ├── model.py                    # RF + XGBoost 学習・評価
│   ├── optimizer.py                # SLSQP最適化 + パレートフロント
│   ├── generate_realistic_data.py  # Taylor方程式による合成データ生成
│   └── train_realistic.py          # 合成データでの再学習
├── data/raw/
│   ├── ai4i2020.csv                # UCI Predictive Maintenance Dataset
│   └── realistic_milling.csv       # Taylor方程式で生成した2,000件
├── models/
│   ├── best_model.joblib           # 本番モデル
│   ├── feature_names.joblib        # 特徴量名
│   ├── rf_wear_predictor.joblib    # RandomForest
│   └── xgb_wear_predictor.joblib   # XGBoost
└── outputs/                        # EDA・モデル診断の出力画像
```

---

## セットアップ

```bash
pip install -r requirements.txt
streamlit run app.py
```

### 合成データの再生成・再学習

```bash
python src/generate_realistic_data.py   # Taylor方程式でデータ生成
python src/train_realistic.py           # モデル再学習
```

---

## 使用データセット

| データ | 用途 |
|--------|------|
| UCI AI4I 2020 Predictive Maintenance | 初期検証・EDA |
| Taylor方程式 合成データ（自作） | 物理モデルベースの学習・予測 |

---

## 開発の背景と位置づけ

加工技術部で5年間、NCプログラミング・工程設計・治具設計を担当してきました。
切削条件の決定が「カタログ値 × 経験則」に依存している現場を見てきたからこそ、
**データに基づいた条件設定を現場に持ち込みたい** という動機でこのツールを開発しています。

品質管理部に異動して10年、Cpk管理やデータ分析の実務を積んだことで、
「加工条件 → 品質指標」のつながりをデータで語れる基盤ができました。
このツールはその延長線上にあります。

---

## 技術スタック

| 用途 | ライブラリ |
|------|-----------|
| ML | scikit-learn, XGBoost |
| データ処理 | pandas, numpy |
| 最適化 | scipy.optimize |
| Web UI | Streamlit |
| 可視化 | matplotlib |

---

*現場課題を自分で解決する──加工技術＋品質管理＋Python実装の組み合わせで作ったツールです。*
