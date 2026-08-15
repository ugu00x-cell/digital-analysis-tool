---
title: "DCASE 2026 異常音検知でMobileNetV2に乗り換えたら精度が下がった話 ── AE系の限界と3つの敗因"
emoji: "📉"
type: "tech"
topics: ["DCASE", "異常検知", "PyTorch", "MobileNetV2", "AutoEncoder"]
published: false
---

## 結論から言う

**Dense AutoEncoder (AUC 0.57) から MobileNetV2ベースCNN AE に切り替えたら、AUCが 0.55 まで下がった。**

工場の予知保全を意識して、DCASE 2026 Challenge Task 2 (Bearing Emu) のベースライン改善に挑んだ結果だ。目標は AUC 0.65+ だったが、**事前学習の強い CNN に替えるほど精度が下がる**という直感に反する結果になった。

この記事はその失敗記録だ。「なぜ下がったのか」「なぜ AE 自体に限界があるのか」を、現場目線で書く。

## 前提：DCASE 2026 Task 2 Bearing Emu とは

DCASE (Detection and Classification of Acoustic Scenes and Events) は、音響イベント検知の国際コンペ。Task 2 は **機械の正常音のみで学習し、異常音を検知する教師なし異常検知タスク**だ。

2026年版のBearing (Emu) データセットは:

- 10秒のモノラル音声（16kHz）
- 学習データ: 正常音 1,000件
- テストデータ: 正常100件 + 異常100件
- 配布元: [Zenodo](https://zenodo.org/records/19336329)

## 試行1: Dense AutoEncoder（ベースライン）

DCASE公式ベースラインに近い Dense AutoEncoder を組んだ。

```python
# 入力: log-melスペクトログラム 128mel × 連続5フレーム = 640次元ベクトル
# Encoder: 640 → 512 → 256 → 128 → 64 → 32 (latent)
# Decoder: 32 → 64 → 128 → 256 → 512 → 640
```

正常音だけで学習し、ファイル単位の再構成誤差（MSE）を異常スコアにする。

**結果:**

| 指標 | 値 |
|---|---|
| AUC-ROC | **0.5659** |
| Partial AUC (FPR≤0.1) | 0.5732 |
| 正常スコア平均 | 0.4258 |
| 異常スコア平均 | 0.4513 |
| 分離度 | 0.0255 |

DCASE Bearing Emu は難しいデータセットで、過去の公式ベースラインも AUC 0.55-0.65 が典型値だ。とりあえずそこそこ妥当な出発点と言える。

## 試行2: MobileNetV2 ベース CNN AutoEncoder

より強力なモデルなら精度が上がるはず、という仮説で MobileNetV2 ベースに切り替えた。

```python
class MobileNetAutoEncoder(nn.Module):
    def __init__(self, latent_dim: int = 128):
        super().__init__()
        # Encoder: ImageNet事前学習済みMobileNetV2
        backbone = mobilenet_v2(weights=MobileNet_V2_Weights.IMAGENET1K_V1)
        self.features = backbone.features  # (B, 1280, H/32, W/32)
        self.pool = nn.AdaptiveAvgPool2d((4, 2))
        self.bottleneck = nn.Sequential(
            nn.Flatten(),
            nn.Linear(1280 * 4 * 2, 512),
            nn.BatchNorm1d(512), nn.ReLU(inplace=True),
            nn.Linear(512, latent_dim),
        )
        # Decoder: ConvTranspose2dの段階的アップサンプリング
        ...

    def forward(self, x):
        x_3ch = x.repeat(1, 3, 1, 1)  # 1ch → 3ch (ImageNet向け)
        z = self.encoder(x_3ch)
        return self.decoder(z)
```

入力はメルスペクトログラムを 128×64 のパッチに切り出し、1chを3chにブロードキャストして MobileNetV2 に食わせる。

GPU（RTX 2070）で 80エポック学習（Early Stopping で実際は75epoch）した結果:

**結果:**

| 指標 | Dense AE | **MobileNetV2 CNN** |
|---|---|---|
| AUC-ROC | 0.5659 | **0.5466** |
| Partial AUC | 0.5732 | 0.5374 |
| 分離度 | 0.0255 | 0.0206 |

**むしろ悪化した。**

## 敗因1: Information Leak 問題

一番大きな敗因はこれだ。

AE の異常検知の前提は「正常音だけで学習した AE は、正常音は綺麗に再構成できるが、異常音は再構成が崩れる」というもの。ところが **強力な CNN AE ほど、未知の異常音まで"それっぽく"再構成してしまう**。

これは画像異常検知の世界では **Information Leak** あるいは **identity shortcut** と呼ばれる既知の問題だ。

3回の試行で分離度（異常平均 - 正常平均）を見ると:

| モデル | 分離度 |
|---|---|
| Dense AE (小さいモデル) | 0.0255 |
| MobileNetV2 CPU | 0.0264 |
| MobileNetV2 GPU 75epoch | **0.0206** ← 改善するどころか縮まっている |

学習を進めるほど、異常音との差が縮まっている。これは AE が「汎化しすぎている」証拠だ。

**教訓: AE の異常検知では、モデルを強くすることは必ずしも正解ではない。**

## 敗因2: ImageNet 事前学習のドメイン不一致

MobileNetV2 の事前学習重みは ImageNet の自然画像で獲得されたものだ。犬、猫、車、ビルのエッジ検出器たち。

一方、**メルスペクトログラムの「画像」は、横軸が時間、縦軸が周波数、値が対数パワー**。自然画像とは統計的性質が根本的に違う:

- 自然画像: 空間的な連続性、エッジ、テクスチャ
- メルスペクトログラム: 周波数依存の縦方向構造、時間方向のリズム

転移学習の恩恵を受けるには、**ソースドメイン（ImageNet）とターゲットドメイン（メルスペクトログラム）の分布が近い必要がある**。ところがこの2つは遠すぎた。

実際、スペクトログラム用の事前学習モデル（AudioSet で学習した VGGish や PANNs）なら状況が違っただろうが、それは別の話だ。

**教訓: 事前学習は万能ではない。ドメインが遠いと有害ですらある。**

## 敗因3: 環境問題（torchvision が CPU 版で入った事件）

これは技術的な敗因というより **オペレーションミス**だが、晒しておく。

最初の MobileNetV2 実行時、`pip install torchvision` しただけで済ませたら、**CPU 版の torchvision が入り、同時に既存の GPU 版 torch を上書きして CPU 版 torch (2.11.0+cpu) に置き換えた**。

結果:

- ログに「学習デバイス: cpu」と出てた（気づくの遅れた）
- 1 エポック約 80 秒、30epoch で 40分
- そもそも学習が収束しきれなかった

GPU を使うときは必ず両方を同じ index から入れる:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

**教訓: ログ先頭の「device: cpu/cuda」は毎回確認する。**

## AUC 0.65 に届かなかったが、得たもの

結果だけ見れば失敗だ。AUC 0.57 → 0.55 でむしろ悪化した。

でも DCASE Task 2 の過去のSOTA手法を調べ直すと、勝っているチームは **AE 系ではない**ことがわかった。

SOTA のアプローチは大きく2系統:

**1. Mahalanobis距離系 (PaDiM風)**
事前学習 CNN の中間層特徴量の分布を正常音でガウシアンフィットし、テスト音の Mahalanobis 距離で判定する。再構成を使わないので Information Leak が起きない。

**2. 自己教師あり分類系**
正常音にデータ拡張（ピッチシフト、ノイズ付加）をかけて複数クラスに分類させ、学習済みモデルの埋め込み距離を異常スコアにする。

つまり、**「AE の再構成誤差」という発想そのものが古い**というのが今回の一番大きな学びだった。

## 工場の予知保全への示唆

私は機械加工メーカーの品質管理部で10年働いている。振動データや音響データを使った異常検知は、コーストFIRE後のDXコンサルの主戦場として考えている領域だ。

今回の実験で痛感したのは:

1. **「AE で再構成誤差」は入門用、本番用ではない**
   現場のPoCで「なんとなく動きそう」と AE を持ち込むと、顧客の期待を裏切る可能性が高い

2. **ベースラインを作る前に敗因パターンを知っておく**
   Information Leak、ドメイン不一致、評価指標の罠 — 知らずに挑むと失敗する

3. **公開データセットでのAUC値を鵜呑みにしない**
   同じ AUC 0.6 でも、工場の実機では誤報率 FPR が重要。Partial AUC で評価するのが現場では妥当

次回は PaDiM 風の Mahalanobis 距離ベースで再挑戦する。AUC 0.65+ の壁を越えたらまた書く。

## 使ったコード

全コードは GitHub に公開している:

- [dcase2026_baseline リポジトリ](https://github.com/ugu00x-cell/digital-analysis-tool/tree/main/dcase2026_baseline)

## 参考資料

- [DCASE 2026 Challenge Task 2 Development Dataset (Zenodo)](https://zenodo.org/records/19336329)
- Zavrtanik et al., "Reconstruction by inpainting for visual anomaly detection" (Information Leak の議論)
- Defard et al., "PaDiM: a Patch Distribution Modeling Framework for Anomaly Detection"
