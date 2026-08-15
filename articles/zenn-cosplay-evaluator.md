---
title: "OllamaとStreamlitでコスプレ写真SNS映え採点アプリを作った"
emoji: "📸"
type: "tech"
topics: ["Python", "Ollama", "Streamlit", "llava", "AI"]
published: false
---

## はじめに

コスプレイヤーの方が写真をSNSに投稿するとき、「この写真、映えてるかな？」と気になることはありませんか？

今回、**ローカルLLM（Ollama + llava）** と **Streamlit** を組み合わせて、コスプレ写真を5つの観点から100点満点で採点するWebアプリを作りました。

**特徴：**
- 画像をアップロードするだけで、AIが自動で採点＋改善アドバイスを出す
- ローカル実行なので **API費用ゼロ**・**画像が外部に送信されない**
- 日本語で結果が返ってくる（テンプレート変換方式）

この記事では、実装のポイントや「llavaを実際に使ってみてわかったこと」を中心にお伝えします。


## システム構成

```
┌──────────────┐     画像アップロード     ┌──────────────┐
│  Streamlit   │ ──────────────────────> │   Ollama     │
│  (Web UI)    │ <────────────────────── │   llava      │
│  app.py      │     英語テキスト応答     │  (Vision LM) │
└──────────────┘                         └──────────────┘
       │
       ▼  テンプレート変換
  日本語の採点結果を表示
```

### 使用技術

| 技術 | 役割 |
|------|------|
| **Ollama** | ローカルLLMサーバー。llavaモデルをホスティング |
| **llava** | 画像を理解できるVision Language Model（7Bパラメータ） |
| **Streamlit** | PythonだけでWeb UIを構築できるフレームワーク |
| **Python 3.12** | メイン言語 |

### llavaとは？

llava（Large Language and Vision Assistant）は、テキストだけでなく **画像も入力として受け取れる** マルチモーダルLLMです。GPT-4Vのローカル版のようなイメージで、Ollamaを使えば `ollama pull llava` の一発でダウンロードできます（約4.7GB）。


## 実装のポイント

### 1. プロンプトは英語で書く

llava（7Bモデル）に日本語で構造化された出力を求めると、文字化けや意味不明な応答が返ってきます。これはモデルの訓練データが英語中心であるためです。

```python
# 英語プロンプト（llavaが安定して応答できるシンプルな形式）
EVAL_PROMPT = (
    "You are a cosplay photo expert. Rate this cosplay photo.\n\n"
    "Score each category from 0 to 20. "
    "Reply in EXACTLY this format:\n\n"
    "Expression: SCORE/20 - REASON\n"
    "Costume: SCORE/20 - REASON\n"
    "Pose: SCORE/20 - REASON\n"
    "Lighting: SCORE/20 - REASON\n"
    "Overall: SCORE/20 - REASON\n"
    "Total: XX/100\n"
    "Advice1: first improvement tip\n"
    "Advice2: second improvement tip\n"
    "Advice3: third improvement tip"
)
```

ポイントは **「EXACTLY this format」** と明示すること。llavaは指示が曖昧だと自由に語り始めてしまうので、フォーマットを厳密に指定します。

### 2. 画像解析はCPU推論で安定する

Ollamaはデフォルトで利用可能なGPUを使おうとしますが、llavaの画像解析（ビジョンエンコーダ部分）はGPUとCPUに処理を分割すると不安定になることがあります。

私の環境（RTX 2070 8GB）では、GPU推論だと画像解析時に `<unk>` トークンが大量に出力される現象が発生しました。

```python
# num_gpu=0: CPU推論を明示的に指定
payload = {
    "model": MODEL_NAME,
    "messages": [
        {
            "role": "user",
            "content": EVAL_PROMPT,
            "images": [b64_image],  # Base64エンコードした画像
        }
    ],
    "stream": False,
    "options": {
        "temperature": 0.3,
        "num_predict": 512,
        "num_ctx": 2048,
        "num_gpu": 0,  # ← これが重要
    }
}
```

CPU推論だと1回の評価に **約50〜65秒** かかりますが、安定して正しい結果が得られます。

:::message
**`num_gpu` パラメータについて**
- `0` = 全レイヤーをCPUで処理
- `20`（など正の数） = 指定レイヤー数をGPUにオフロード
- 省略 = Ollamaが自動判断

テキスト生成だけならGPU推論で問題ありませんが、画像入力を伴う場合はCPU推論の方が安定します（モデルやGPU環境に依存）。
:::

### 3. APIエンドポイントは `/api/chat` を使う

Ollamaには `/api/generate` と `/api/chat` の2つのエンドポイントがありますが、**画像を送る場合は `/api/chat` を使います**。`/api/generate` でも画像を送れますが、llavaとの相性が悪く不安定な出力になることがあります。

```python
resp = requests.post(
    f"{OLLAMA_BASE_URL}/api/chat",  # /api/generate ではなく /api/chat
    json=payload,
    timeout=300,  # CPU推論は時間がかかるので余裕を持つ
)
```

### 4. 日本語変換はテンプレート方式で

英語の評価結果を日本語に変換する方法として、最初は以下を検討しました：

| 方法 | メリット | デメリット |
|------|----------|------------|
| Gemini API翻訳 | 自然な日本語 | API費用・レート制限 |
| llama3翻訳 | ローカル完結 | 日本語品質が低い（ローマ字混在） |
| **テンプレート変換** | **高速・無料・安定** | **表現の幅が限定的** |

最終的に **テンプレート変換方式** を採用しました。スコアの高低（高:15点以上 / 中:8〜14点 / 低:7点以下）に応じて、カテゴリごとに用意した日本語テンプレートを選択します。

```python
# スコア帯ごとの日本語コメントテンプレート（一部抜粋）
_SCORE_COMMENTS = {
    "Expression": {
        "high": "キャラクターの表情を見事に再現しています。視線も自然で魅力的です。",
        "mid": "表情の雰囲気は伝わりますが、もう少しキャラクターらしさを出せるとさらに良くなります。",
        "low": "表情が硬い印象です。キャラクターの感情をもっと意識してみましょう。",
    },
    # ... 他カテゴリも同様
}

def _to_japanese(category: str, score: int, reason_en: str) -> str:
    """スコアと英語理由から日本語コメントを生成する"""
    templates = _SCORE_COMMENTS.get(category, {})
    if score >= 15:
        ja = templates.get("high", "高評価です。")
    elif score >= 8:
        ja = templates.get("mid", "改善の余地があります。")
    else:
        ja = templates.get("low", "大きな改善が必要です。")

    # 元の英語理由も補足として追記
    if reason_en and "取得できませんでした" not in reason_en:
        return f"{ja}（{reason_en}）"
    return ja
```

アドバイスもキーワードマッチで変換します：

```python
_ADVICE_KEYWORDS = [
    ("lighting", "ライティングを工夫して、被写体に立体感を出しましょう。"),
    ("background", "背景をシンプルにすると、コスプレが引き立ちます。"),
    ("pose", "ポーズにキャラクターらしい動きを加えると、表現力がアップします。"),
    # ... 12パターン用意
]
```

LLM翻訳に比べると表現の幅は限定的ですが、**レイテンシゼロ・コストゼロ・品質安定** という大きなメリットがあります。


### 5. 応答のパースは正規表現で堅牢に

llavaの出力は必ずしもプロンプト通りのフォーマットにはなりません。メインパターンとフォールバックの2段構えでパースします。

```python
def _extract_score(text: str, category: str) -> tuple[int, str]:
    """テキストから英語カテゴリのスコアと理由を抽出する"""
    # メインパターン: "Category: XX/20 - reason"
    pattern = rf"{category}:\s*(\d+)/20\s*[-–]\s*(.+?)(?:\n|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        score = min(int(match.group(1)), 20)  # 20点上限でクリップ
        return score, match.group(2).strip()

    # フォールバック: "Category: XX/20" だけでも拾う
    fallback = rf"{category}:\s*(\d+)\s*/\s*20"
    fb_match = re.search(fallback, text, re.IGNORECASE)
    if fb_match:
        return min(int(fb_match.group(1)), 20), "(No details)"

    return 0, "（評価を取得できませんでした）"
```

`min(score, 20)` で20点を超えるスコア（llavaがたまに出す）を丸めている点もポイントです。


## 実際の評価結果

実際にコスプレ写真を評価してみた結果がこちらです：

### 合計: 38/100

| カテゴリ | スコア | コメント |
|----------|--------|----------|
| 表情・視線 | 7/20 | 表情が硬い印象です。キャラクターの感情をもっと意識してみましょう。 |
| 衣装の見え方 | 8/20 | 衣装の雰囲気は良いですが、フィット感や細部の仕上げを改善するとさらに映えます。 |
| ポーズ・体の向き | 9/20 | ポーズは悪くないですが、もう少し動きや角度を工夫するとインパクトが増します。 |
| 背景・光の当たり方 | 6/20 | 照明が平坦で、メリハリが不足しています。サイドライトや逆光を試してみましょう。 |
| 全体的なバランス | 8/20 | まとまりのある写真ですが、いくつかの改善で大きくレベルアップできます。 |

### 改善アドバイス
1. ライティングを工夫して、被写体に立体感を出しましょう。
2. ポーズにキャラクターらしい動きを加えると、表現力がアップします。
3. 背景をシンプルにすると、コスプレが引き立ちます。

38点という厳しめの結果ですが、具体的な改善点が明確になるのは面白いですね。ライティングとポーズを改善するだけでもかなりスコアが上がりそうです。


## 苦労したポイント

### llavaのGPU推論問題

最も苦労したのが、GPU推論時の文字化け問題です。

```
# GPU推論時の出力例（壊れている）
##<unk>$<unk>$<unk>...
```

RTX 2070（VRAM 8GB）でllava 7Bを動かすと、VRAMに収まりきらないレイヤーがCPUにフォールバックされます。このとき**ビジョンエンコーダ（画像を理解する部分）がGPUとCPUに分割されてしまい、テンソルの受け渡しで不整合が起きる**ようです。

テキストのみの質問はGPU推論で問題なく動くので、画像入力時だけの問題です。`num_gpu=0` でCPU推論に切り替えることで解決しました。

### 日本語出力の壁

llava 7Bに日本語で応答させようとすると：
- 文字化け
- 英語と日本語が混在
- フォーマットが崩れる

といった問題が頻発します。7Bクラスのモデルでは日本語の構造化出力は荷が重いようです。

llama3での後処理翻訳も試しましたが、ローマ字が混在する品質でした。最終的にテンプレート変換に落ち着きましたが、**「LLMに何でもやらせようとしない」** という判断が重要だと感じました。


## プロジェクト構成

```
cosplay_evaluator/
├── app.py                      # Streamlit UI（166行）
├── services/
│   └── ollama_client.py        # Ollama連携・パース・翻訳（312行）
├── start.bat                   # Windows起動スクリプト
├── start.sh                    # Mac/Linux起動スクリプト
├── requirements.txt
└── .gitignore
```

1ファイル1責務を意識して、UI層（`app.py`）とロジック層（`ollama_client.py`）を分離しています。


## まとめ

### 学んだこと

1. **llavaは英語プロンプトで使うべき** — 7Bモデルで日本語構造化出力は無理がある
2. **画像解析はCPU推論が安定** — GPU/CPU分割でビジョンエンコーダが壊れることがある
3. **翻訳はテンプレートで十分なケースがある** — LLMに全部やらせなくていい
4. **Ollamaは `/api/chat` を使う** — 特に画像入力時は `/api/generate` より安定

### 今後やりたいこと

- より大きなモデル（llava 13B, llava-next）での精度比較
- 複数枚の写真を比較して「ベストショット」を選ぶ機能
- 評価履歴の保存と成長トラッキング

ローカルLLMは環境構築でハマりやすいですが、一度動いてしまえば **API費用を気にせず好きなだけ実験できる** のが最大の魅力です。コスプレ以外にも、料理写真やペット写真の評価など、応用の幅は広いと思います。

ぜひ試してみてください！

:::message
**リポジトリ**: [cosplay_evaluator](https://github.com/ugu00x-cell/my-secretary/tree/main/cosplay_evaluator)
:::
