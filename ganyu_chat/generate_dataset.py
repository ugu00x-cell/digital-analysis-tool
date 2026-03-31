"""
甘雨ファインチューニング用会話データ生成スクリプト
Claude API を使い、テーマ別に10件×10バッチ＝100件の会話ペアを生成する
"""

import argparse
import getpass
import json
import logging
import os
import time
from pathlib import Path

import anthropic

# ─── ログ設定 ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('generate_dataset.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── 定数 ────────────────────────────────────────────────
MODEL_NAME    = "claude-sonnet-4-20250514"
MAX_TOKENS    = 2048
OUTPUT_FILE   = "ganyu_dataset.json"
PAIRS_PER_BATCH = 10   # 1バッチあたりの会話ペア数

# 甘雨のキャラクター設定（生成プロンプトに埋め込む）
GANYU_PROFILE = """
【キャラクター設定: 甘雨（ガンユ）】
・原神のキャラクター。璃月港の七星秘書局で働く半仙人の少女
・口調：丁寧な敬語、落ち着いて穏やか
・相手の呼び方：「旅人さん」
・口癖：「かしこまりました」「お役に立てて光栄です」「それは…少し困りますが」
・性格：仕事熱心・真面目・少し堅い。書類仕事が好き
・半仙人（麒麟の血統）でツノと尻尾がある
・ツノに触れられると「ツノには触れないでください…！」と困った様子で言う
・甘いもの、特に杏仁豆腐が好き
・休暇の取り方がわからず、仕事ばかりしてしまう
・感情表現は控えめだが、旅人への気遣いは言葉の端々ににじみ出る
・返答は2〜4文程度の自然な会話
"""

# 10テーマ（各テーマから10ペアずつ生成）
THEMES: list[dict] = [
    {
        "name": "挨拶・日常の声かけ",
        "description": "朝の挨拶、久しぶりの再会、別れの挨拶など日常的な声かけ",
        "examples": ["おはよう", "久しぶりだね", "今日もお疲れ様"],
    },
    {
        "name": "仕事の依頼・相談",
        "description": "書類の処理、情報収集、手配の依頼など業務に関するやりとり",
        "examples": ["書類を整理してほしい", "璃月港の地図を見せて", "明日の会議の準備をお願い"],
    },
    {
        "name": "ツノ・半仙人への言及",
        "description": "ツノに触れようとする、半仙人について聞く、麒麟の血統について聞くなど",
        "examples": ["ツノ触っていい？", "半仙人ってどんな感じ？", "ツノはやわらかい？"],
    },
    {
        "name": "璃月・仙人の話",
        "description": "璃月港の文化、七星、仙人について話す",
        "examples": ["璃月港はどんなところ？", "仙人って怖い？", "岩王帝君について教えて"],
    },
    {
        "name": "休日・プライベート",
        "description": "休日の過ごし方、趣味、リフレッシュ方法について",
        "examples": ["休日は何してるの？", "好きな場所はある？", "最近楽しかったことは？"],
    },
    {
        "name": "食べ物・杏仁豆腐",
        "description": "好きな食べ物、杏仁豆腐、璃月料理について",
        "examples": ["好きな食べ物は？", "杏仁豆腐って好き？", "一緒にご飯食べよう"],
    },
    {
        "name": "褒め言葉・感謝",
        "description": "甘雨を褒める、感謝を伝える、一緒に仕事をした後のやりとり",
        "examples": ["甘雨ちゃんってすごいね", "助かったよ、ありがとう", "甘雨ちゃんがいてよかった"],
    },
    {
        "name": "冒険・戦闘の話",
        "description": "モンスター討伐、探索の依頼、戦闘について話す",
        "examples": ["一緒に戦ってほしい", "最近モンスターが多いね", "弓の腕前はどれくらい？"],
    },
    {
        "name": "感情・悩み相談",
        "description": "旅人の悩みを聞く、励ます、甘雨自身の感情について話す",
        "examples": ["最近疲れてて…", "ちょっと落ち込んでる", "甘雨ちゃんは悩みとかある？"],
    },
    {
        "name": "ユーモア・意外な質問",
        "description": "ちょっとズレた質問、冗談、甘雨が困る質問など",
        "examples": ["甘雨ちゃんって結婚できる？", "仙人に休日ってある？", "書類仕事が好きってホント？"],
    },
]


def build_generation_prompt(theme: dict) -> str:
    """テーマに合わせた会話ペア生成プロンプトを組み立てる。

    Args:
        theme: テーマ情報（name, description, examples を含む辞書）

    Returns:
        Claude に渡すプロンプト文字列
    """
    examples_str = "・" + "\n・".join(theme["examples"])
    return f"""
{GANYU_PROFILE}

以下のテーマで、「旅人（プレイヤー）」と「甘雨」の会話ペアを{PAIRS_PER_BATCH}組生成してください。

【テーマ】{theme["name"]}
【内容】{theme["description"]}
【旅人の発言例（参考）】
{examples_str}

【出力形式】
必ず以下のJSON形式のみで出力し、コードブロックや説明文は含めないこと。

{{
  "pairs": [
    {{"input": "旅人のセリフ", "output": "甘雨の返答"}},
    ...
  ]
}}

【生成ルール】
・旅人のセリフはバリエーションを持たせること（敬語・タメ口・質問・お願いなど混在）
・甘雨の返答は2〜4文程度で、キャラクターらしい自然な日本語にすること
・同じようなやりとりが重複しないようにすること
・甘雨は必ず「旅人さん」と呼ぶこと
・口癖（かしこまりました・お役に立てて光栄です等）は自然な場面で使うこと
"""


def parse_response(response_text: str) -> list[dict]:
    """APIレスポンスから会話ペアのリストを取り出す。

    JSONが不正な場合は空リストを返す。

    Args:
        response_text: Claude が返したテキスト

    Returns:
        {"input": str, "output": str} の辞書リスト
    """
    # コードブロックが含まれていた場合は除去
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        data = json.loads(text)
        pairs = data.get("pairs", [])
        # inputとoutputの両方があるペアだけを取り出す
        valid = [p for p in pairs if "input" in p and "output" in p]
        logger.info(f"  パース成功: {len(valid)}ペア取得")
        return valid
    except json.JSONDecodeError as e:
        logger.error(f"  JSONパースエラー: {e}")
        logger.debug(f"  レスポンス内容: {response_text[:200]}")
        return []


def generate_batch(client: anthropic.Anthropic, theme: dict) -> list[dict]:
    """1テーマ分の会話ペアをAPIから生成する。

    Args:
        client: Anthropic クライアント
        theme: テーマ情報

    Returns:
        会話ペアのリスト（失敗時は空リスト）
    """
    prompt = build_generation_prompt(theme)
    logger.info(f"バッチ生成中: 【{theme['name']}】")

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        pairs = parse_response(response.content[0].text)
        return pairs

    except anthropic.RateLimitError:
        logger.warning("レート制限のため60秒待機します")
        time.sleep(60)
        return []
    except anthropic.APIError as e:
        logger.error(f"APIエラー: {e}")
        return []


def save_dataset(conversations: list[dict], output_path: Path) -> None:
    """会話データをJSONファイルに保存する。

    Args:
        conversations: {"input": str, "output": str} のリスト
        output_path: 保存先ファイルパス
    """
    dataset = {"conversations": conversations}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    logger.info(f"保存完了: {output_path} ({len(conversations)}ペア)")


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Returns:
        解析済み引数のNamespace
    """
    parser = argparse.ArgumentParser(description="甘雨ファインチューニング用データ生成")
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Anthropic APIキー（省略時は環境変数 ANTHROPIC_API_KEY を使用）",
    )
    return parser.parse_args()


def get_api_key(cli_key: str = "") -> str:
    """APIキーを取得する。優先順位: CLI引数 → 環境変数 → 対話入力。

    Args:
        cli_key: コマンドライン引数で渡されたキー（省略可）

    Returns:
        APIキー文字列

    Raises:
        ValueError: いずれの方法でも取得できなかった場合
    """
    # 1. CLI引数
    if cli_key:
        logger.info("APIキー: コマンドライン引数から読み込みました")
        return cli_key.strip()
    # 2. 環境変数
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        logger.info("APIキー: 環境変数から読み込みました")
        return key
    # 3. 対話入力（ターミナル直接実行時のフォールバック）
    logger.info("APIキーが未設定です。直接入力してください")
    key = getpass.getpass("Anthropic APIキー (sk-ant-...): ").strip()
    if not key:
        raise ValueError("APIキーが入力されませんでした")
    logger.info("APIキー: 対話入力から読み込みました")
    return key


def main() -> None:
    """全テーマの会話データを生成して JSON に保存するメイン処理"""
    logger.info("=" * 50)
    logger.info("甘雨 ファインチューニング用データ生成開始")
    logger.info(f"テーマ数: {len(THEMES)} / 各テーマ: {PAIRS_PER_BATCH}ペア")
    logger.info(f"目標合計: {len(THEMES) * PAIRS_PER_BATCH}ペア")
    logger.info("=" * 50)

    # コマンドライン引数の解析とAPIキーの確認
    args = parse_args()
    try:
        api_key = get_api_key(cli_key=args.api_key)
    except ValueError as e:
        logger.error(str(e))
        return

    client = anthropic.Anthropic(api_key=api_key)
    all_conversations: list[dict] = []

    for i, theme in enumerate(THEMES, start=1):
        logger.info(f"\n[{i}/{len(THEMES)}] {theme['name']}")

        pairs = generate_batch(client, theme)

        if pairs:
            all_conversations.extend(pairs)
            logger.info(f"  累計: {len(all_conversations)}ペア")
        else:
            logger.warning(f"  このバッチは0件でした（スキップ）")

        # レート制限対策：バッチ間に少し待機（最後のバッチ以外）
        if i < len(THEMES):
            time.sleep(2)

    # 保存
    output_path = Path(__file__).parent / OUTPUT_FILE
    save_dataset(all_conversations, output_path)

    # 完了サマリー
    logger.info("\n" + "=" * 50)
    logger.info(f"生成完了！")
    logger.info(f"  総会話ペア数: {len(all_conversations)}")
    logger.info(f"  保存先: {output_path}")
    logger.info("=" * 50)

    # サンプル表示
    if all_conversations:
        logger.info("\n【サンプル（先頭3件）】")
        for sample in all_conversations[:3]:
            logger.info(f"  Q: {sample['input']}")
            logger.info(f"  A: {sample['output']}")
            logger.info("")


if __name__ == "__main__":
    main()
