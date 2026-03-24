---
title: "品質管理10年の現場エンジニアがPythonでCpk自動計算ツールを作るまで"
emoji: "📊"
type: "tech"
topics: ["Python", "製造業", "品質管理", "pandas", "DX"]
published: false
---

## はじめに

はじめまして。製造業で品質管理を10年やっているエンジニアです。その前は加工技術を5年担当していたので、合わせて15年ほど現場に立っています。

品質管理の仕事をしていると、こんな場面に出くわしませんか？

- **Excelで毎回Cpkを手計算**している
- 機械が10台あると、**同じ作業を10回繰り返す**
- 数値は出せるけど、**どの機械がヤバいのか一覧で比較しづらい**
- 上司に「全機械のCpkまとめて」と言われて**残業が確定する**

私も長年こういう状態でした。

あるときPythonを触り始めて、「これ、全部自動化できるのでは？」と気づきました。実際に作ってみたら、**10台分のCpk計算が数秒で終わる**ようになりました。

この記事では、PythonほぼはじめてでもCpkを知っている方に向けて、「意外と簡単にできるんだな」と感じてもらえるように書いていきます。

## Cpkとは何か（簡単な復習）

ご存じの方も多いと思いますが、簡単に振り返ります。

**Cpk（工程能力指数）** は、工程が規格に対してどれくらい余裕を持って収まっているかを表す指標です。

計算式はこうなります：

$$
Cpk = \min\left(\frac{USL - \bar{x}}{3\sigma},\ \frac{\bar{x} - LSL}{3\sigma}\right)
$$

| 記号 | 意味 |
|------|------|
| USL | 規格上限（Upper Specification Limit） |
| LSL | 規格下限（Lower Specification Limit） |
| $\bar{x}$ | 測定値の平均 |
| $\sigma$ | 測定値の標準偏差 |

ざっくり言えば：

| Cpk | 状態 |
|-----|------|
| 1.33以上 | 十分な工程能力あり |
| 1.00〜1.33 | ギリギリ。要注意 |
| 1.00未満 | 規格外が出るリスクあり |

現場では **Cpk ≥ 1.33** を合格ラインにしていることが多いですよね。

## 実際に作ったコード

### 使うライブラリ

```bash
pip install pandas
```

pandasだけで動きます。グラフを出したい方はmatplotlibも入れてください。

### ダミーデータを用意する

まず、こんなCSVを想定します。機械ごとの測定データが入っているイメージです。

```python
import pandas as pd
import numpy as np

# --- ダミーデータ生成 ---
# 実際にはCSVから読み込みますが、記事用にコードで作ります
np.random.seed(42)

records = []
machines = ["MC-01", "MC-02", "MC-03", "MC-04", "MC-05"]
# 機械ごとに少しずつ傾向を変える
offsets = [0.0, 0.02, -0.01, 0.05, 0.0]
spreads = [0.01, 0.015, 0.008, 0.025, 0.012]

for machine, offset, spread in zip(machines, offsets, spreads):
    for i in range(50):
        value = np.random.normal(loc=10.0 + offset, scale=spread)
        records.append({"機械": machine, "測定値": round(value, 4)})

df = pd.DataFrame(records)
print(df.head(10))
```

出力イメージ：

```
     機械      測定値
0  MC-01  10.0050
1  MC-02   9.9862
2  MC-03  10.0065
3  MC-04  10.0124
4  MC-05   9.9981
...
```

実際の業務では `pd.read_csv("measurement.csv")` でCSVを読み込む形になります。

### Cpkを計算する関数

ここが本丸です。やっていることはシンプルで、**平均と標準偏差を出して、式に当てはめるだけ**です。

```python
def calc_cpk(values, usl, lsl):
    """Cpkを計算する

    Parameters
    ----------
    values : array-like
        測定値の配列
    usl : float
        規格上限
    lsl : float
        規格下限

    Returns
    -------
    dict
        平均、標準偏差、Cpu、Cpl、Cpkをまとめた辞書
    """
    mean = np.mean(values)
    std = np.std(values, ddof=1)  # 不偏標準偏差を使う

    if std == 0:
        return {"平均": mean, "標準偏差": 0, "Cpu": None, "Cpl": None, "Cpk": None}

    cpu = (usl - mean) / (3 * std)  # 上限側の工程能力
    cpl = (mean - lsl) / (3 * std)  # 下限側の工程能力
    cpk = min(cpu, cpl)             # 小さい方がCpk

    return {
        "平均": round(mean, 4),
        "標準偏差": round(std, 4),
        "Cpu": round(cpu, 2),
        "Cpl": round(cpl, 2),
        "Cpk": round(cpk, 2),
    }
```

ポイントは `ddof=1` です。これを入れないと母標準偏差になってしまいます。品質管理ではサンプルから推定するので、**不偏標準偏差（ddof=1）**を使うのが一般的です。

### 機械ごとにCpkを計算する

```python
# --- 規格 ---
USL = 10.05  # 規格上限
LSL = 9.95   # 規格下限

# --- 機械ごとに計算 ---
results = []
for machine, group in df.groupby("機械"):
    cpk_result = calc_cpk(group["測定値"], USL, LSL)
    cpk_result["機械"] = machine
    results.append(cpk_result)

result_df = pd.DataFrame(results)[["機械", "平均", "標準偏差", "Cpu", "Cpl", "Cpk"]]
print(result_df.to_string(index=False))
```

たったこれだけです。`groupby` で機械ごとにデータを分けて、さっきの関数に渡すだけ。

## 動かしてみた結果

実行すると、こんな感じの表が出ます：

```
  機械      平均   標準偏差   Cpu   Cpl   Cpk
MC-01  10.0003   0.0103  1.61  1.63  1.61
MC-02  10.0186   0.0139  0.75  1.64  0.75
MC-03   9.9893   0.0083  2.44  1.58  1.58
MC-04  10.0498   0.0237  0.00  1.40  0.00
MC-05  10.0009   0.0116  1.41  1.46  1.41
```

※乱数のシードで毎回同じ結果になります

ここからわかること：

- **MC-01, MC-03**：Cpk 1.33以上 → 安定。問題なし
- **MC-05**：Cpk 1.41 → ギリギリ合格だが注意して見たい
- **MC-02**：Cpk 0.75 → 上限に寄っている。調整が必要
- **MC-04**：Cpk ≒ 0 → 平均が規格上限付近。すぐに対策すべき

これをExcelで10台分やると30分かかりますが、このスクリプトなら**数秒**です。しかも、CSVを差し替えるだけで毎月繰り返し使えます。

### 判定を付けるともっと便利

結果に合否判定を足してみましょう。

```python
def judge_cpk(cpk):
    """Cpkの値から判定を返す"""
    if cpk is None:
        return "計算不可"
    if cpk >= 1.33:
        return "○ 十分"
    if cpk >= 1.00:
        return "△ 要注意"
    return "× 能力不足"

result_df["判定"] = result_df["Cpk"].apply(judge_cpk)
print(result_df.to_string(index=False))
```

```
  機械      平均   標準偏差   Cpu   Cpl   Cpk      判定
MC-01  10.0003   0.0103  1.61  1.63  1.61    ○ 十分
MC-02  10.0186   0.0139  0.75  1.64  0.75  × 能力不足
MC-03   9.9893   0.0083  2.44  1.58  1.58    ○ 十分
MC-04  10.0498   0.0237  0.00  1.40  0.00  × 能力不足
MC-05  10.0009   0.0116  1.41  1.46  1.41    ○ 十分
```

上司への報告もこのまま使えます。

## 感想・次のステップ

### 作ってみて感じたこと

- Cpk計算そのものは**十数行で書ける**。難しくない
- 時間がかかっていたのは計算ではなく、**Excelの繰り返し作業**だった
- Pythonを使うと「繰り返し」と「一覧化」が圧倒的にラク

### 次にやりたいこと

このツールをベースに、以下のような拡張を考えています：

1. **ヒストグラムと規格線を重ねたグラフ**を自動出力する
2. **時系列でCpkの推移**を追えるようにする（月次レポート用）
3. **異常の早期検知**（管理図やIsolation Forestと組み合わせる）

品質管理の仕事をしている方で、「Excel作業が多くて大変だな」と感じている方は、まずこのCpk計算から試してみてください。pandas + 数行のコードで、日常業務がかなりラクになります。

---

最後まで読んでいただきありがとうございます。
「自分の現場でも使えそう」と思っていただけたら、いいねを押してもらえると嬉しいです。
