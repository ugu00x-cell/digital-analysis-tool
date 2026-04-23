# 初期不良 自然言語分析 POC

## プロジェクト概要
製造業の初期不良（無償対応）の内容を自然言語でClaude APIが分類・細分化するPOC。  
工作機械3種（マシニングセンタ・放電加工機・研削盤）を対象に、現場記録の揺れを再現した
合成データ100件を使って分類精度を検証し、不良抑止の出発点となる原因・対策まで一気通貫で出す。

## 技術構成

```
[ 合成データ100件 ]                 [ Claude API ]              [ 精度検証 ]
 defects_raw.csv    ──►  classifier.py  ──►  defects_classified.csv  ──►  evaluate.py
  id                     ・10件ずつバッチ       ・predicted_label            ・accuracy
  date                   ・opus-4-6            ・confidence                 ・confusion matrix
  product_category       ・JSON強制            ・sub_category               ・誤分類Top10
  defect_description                           ・estimated_cause
  true_label                                   ・countermeasure
```

## 分類体系（細分化ラベル）

| キー | 説明 |
|---|---|
| `bearing_noise` | ベアリング起因の異音・振動 |
| `thermal_displacement` | 熱変位による寸法ずれ |
| `assembly_scratch` | 組立時の打痕・傷 |
| `alignment_error` | 芯出し・取付不良 |
| `dimension_oversize` | 加工寸法オーバー |
| `dimension_undersize` | 加工寸法アンダー |
| `surface_rust` | 錆・表面処理不良 |
| `motion_alarm` | 動作異常・アラーム |

分類体系は `src/labels.py` の `LABELS` 辞書で定義されており、品質管理の知見に応じて
後から編集可能。編集すると生成スクリプト・分類スクリプト・評価スクリプトの全てに反映される。

## セットアップ手順

```bash
cd defect_nlp_poc

# 依存関係インストール
pip install -r requirements.txt

# APIキーを設定
cp .env.example .env
# .env を開いて ANTHROPIC_API_KEY=sk-ant-... を記入
```

## 実行方法

Step1 → Step2 → Step3 の順に実行する。

```bash
# Step1: 合成データ100件生成（data/defects_raw.csv を出力）
python src/generate_synthetic_data.py

# Step2: Claude APIで分類（data/defects_classified.csv を出力）
python src/classifier.py

# Step3: 精度検証（標準出力 + data/confusion_matrix.csv を出力）
python src/evaluate.py
```

## テスト実行

```bash
pytest tests/ -v
```

正常系2・異常系2・境界値1の最低構成 + 補助テストで、全モジュールを網羅している。

## 精度検証結果の見方

### 全体一致率（accuracy）
```
全体一致率: 87/100 = 87.0%
```
- 分子：true_label と predicted_label が一致した件数
- 分母：predicted_label が空でない件数（API失敗行は除外）

### ラベル別一致率
```
bearing_noise          | 12/13          | 92.3%
thermal_displacement   | 10/12          | 83.3%
...
```
- ラベルごとの精度を確認し、どのラベルが弱いかを把握する

### 間違えやすいパターン Top10
```
bearing_noise          -> motion_alarm           | 3
dimension_oversize     -> thermal_displacement   | 2
...
```
- true → predicted の誤分類パターンを件数降順で表示
- カテゴリ境界が曖昧な箇所を見つける手がかりになる

### Confusion Matrix（`data/confusion_matrix.csv`）
8×8の表形式で、行=true_label、列=predicted_label の件数を保存。
ExcelやPandasで開いて、カテゴリ間の誤分類の全体像を確認できる。

## ディレクトリ構成

```
defect_nlp_poc/
├── data/
│   ├── defects_raw.csv           # Step1生成物（再生成可能）
│   ├── defects_classified.csv    # Step2出力
│   └── confusion_matrix.csv      # Step3出力
├── src/
│   ├── labels.py                 # 分類体系の定数定義
│   ├── generate_synthetic_data.py
│   ├── classifier.py
│   └── evaluate.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## 注意事項
- APIキーは `.env` からのみ読み込む（ハードコード禁止）
- `.env` は `.gitignore` 対象のためコミットされない
- CSVファイルはリポジトリルートの `.gitignore` で除外対象。再現性は
  `generate_synthetic_data.py` の固定seed（42）で担保される
