"""
甘雨チャット 返答ロジックモジュール
APIキーの有無で Claude API / データセット検索 を自動切り替えする
"""

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

# ─── 定数 ────────────────────────────────────────────────
MODEL_NAME      = "claude-sonnet-4-20250514"
MAX_TOKENS      = 1024
DATASET_PATH    = Path(__file__).parent / "ganyu_dataset.json"
MATCH_THRESHOLD = 0.25   # 類似度スコアの最低ライン（これ未満は汎用返答）

# 甘雨のシステムプロンプト（API モード用）
SYSTEM_PROMPT = """あなたは原神のキャラクター「甘雨（ガンユ）」です。
璃月港の七星の秘書として働いており、仕事に対して真面目で誠実な半仙人の少女です。

【口調・話し方】
- 丁寧な敬語を使い、落ち着いて穏やかに話す
- 相手のことは「旅人さん」と呼ぶ
- 口癖：「かしこまりました」「お役に立てて光栄です」「それは…少し困りますが」
- 文末は「〜です」「〜ます」「〜でしょうか」など丁寧な語尾
- 仕事の話題になると少しテンションが上がる

【性格・背景】
- 仕事熱心で真面目。書類仕事が好き
- 半仙人（麒麟の血を引く）なのでツノと尻尾がある
- ツノに触れられると「ツノには触れないでください…！」と困った様子で言う
- 甘いものが好き（特に杏仁豆腐）
- 休暇の取り方がわからなく、仕事ばかりしてしまう
- 旅人のことを大切に思っており、できる限り力になろうとする

【応答スタイル】
- 2〜5文程度の自然な会話
- 感情表現は控えめだが、旅人への気遣いは言葉の端々ににじみ出る
"""

# ─── オフライン返答（データセットにヒットしない場合の保険） ──
FALLBACK_RESPONSES = [
    "かしこまりました。もう少し詳しくお聞かせいただけますでしょうか？",
    "旅人さん、そのようなことでしたら、ぜひお力になれればと思います。",
    "なるほど…少々お時間をいただけますでしょうか。しっかりと考えてご返答します。",
    "お役に立てて光栄です。他にも何かご用件がおありでしたら、遠慮なくどうぞ。",
    "旅人さんのお話は、いつも興味深く聞いております。続けてください。",
]
_fallback_index = 0


def _load_dataset() -> list[dict]:
    """ganyu_dataset.json を読み込んで返す。

    Returns:
        会話ペアのリスト。ファイルが存在しない場合は空リスト
    """
    if not DATASET_PATH.exists():
        logger.warning(f"データセットが見つかりません: {DATASET_PATH}")
        return []
    try:
        with open(DATASET_PATH, encoding="utf-8") as f:
            data = json.load(f)
        pairs = data.get("conversations", [])
        logger.info(f"データセット読み込み: {len(pairs)}件")
        return pairs
    except Exception as e:
        logger.error(f"データセット読み込みエラー: {e}")
        return []


# 起動時に一度だけ読み込む
_DATASET: list[dict] = _load_dataset()


def _normalize(text: str) -> str:
    """類似度計算用にテキストを正規化する。

    全角スペース・記号を除去し、小文字に統一する。

    Args:
        text: 元テキスト

    Returns:
        正規化済みテキスト
    """
    text = text.lower()
    text = re.sub(r"[　\s]+", "", text)          # スペース除去
    text = re.sub(r"[？！。、…「」『』【】]", "", text)  # 記号除去
    return text


def _find_best_match(user_input: str) -> tuple[str, float]:
    """データセットから最も近い返答を検索する。

    SequenceMatcher で文字列類似度を計算し、スコアが最大のペアを返す。

    Args:
        user_input: ユーザーの入力テキスト

    Returns:
        (最適な甘雨の返答, 類似スコア) のタプル
    """
    if not _DATASET:
        return "", 0.0

    query = _normalize(user_input)
    best_score = 0.0
    best_output = ""

    for pair in _DATASET:
        candidate = _normalize(pair.get("input", ""))
        score = SequenceMatcher(None, query, candidate).ratio()
        if score > best_score:
            best_score = score
            best_output = pair.get("output", "")

    logger.info(f"データセット検索: スコア={best_score:.3f}")
    return best_output, best_score


def _get_fallback() -> str:
    """フォールバック返答をローテーションして返す。

    Returns:
        汎用返答テキスト
    """
    global _fallback_index
    reply = FALLBACK_RESPONSES[_fallback_index % len(FALLBACK_RESPONSES)]
    _fallback_index += 1
    return reply


def respond_offline(user_input: str) -> str:
    """APIキーなしでデータセットから返答を生成する。

    類似度が閾値を超えた場合はデータセットの返答を、
    超えない場合はフォールバック返答を返す。

    Args:
        user_input: ユーザーの最新メッセージ

    Returns:
        甘雨の返答テキスト
    """
    output, score = _find_best_match(user_input)

    if score >= MATCH_THRESHOLD and output:
        logger.info(f"オフライン返答: データセットヒット (score={score:.3f})")
        return output
    else:
        logger.info(f"オフライン返答: フォールバック使用 (score={score:.3f})")
        return _get_fallback()


def respond_with_api(messages: list[dict], api_key: str) -> str:
    """Claude API を使って甘雨の返答を生成する。

    Args:
        messages: 会話履歴（role / content の辞書リスト）
        api_key: Anthropic APIキー

    Returns:
        甘雨の返答テキスト
    """
    try:
        client = anthropic.Anthropic(api_key=api_key)
        logger.info(f"APIリクエスト送信: {len(messages)}件の履歴")

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        reply = response.content[0].text
        logger.info(f"APIレスポンス受信: {len(reply)}文字")
        return reply

    except anthropic.AuthenticationError:
        logger.error("APIキー認証エラー")
        return "APIキーの認証に失敗しました。サイドバーのキーをご確認ください。"
    except anthropic.RateLimitError:
        logger.warning("APIレート制限")
        return "申し訳ございません、少し混み合っております。少し時間をおいてからお声がけください。"
    except Exception as e:
        logger.error(f"API呼び出しエラー: {e}")
        return "少々不具合が生じてしまいました。時間をおいて再度お試しください。"


def get_response(messages: list[dict], api_key: str | None) -> tuple[str, str]:
    """APIキーの有無でモードを切り替えて返答を生成する。

    Args:
        messages: 会話履歴（role / content の辞書リスト）
        api_key: Anthropic APIキー（Noneの場合はオフラインモード）

    Returns:
        (甘雨の返答テキスト, 使用モード名) のタプル
        モード名: "api" | "offline"
    """
    if api_key:
        reply = respond_with_api(messages, api_key)
        return reply, "api"
    else:
        # 最新のユーザーメッセージを取り出す
        user_input = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        reply = respond_offline(user_input)
        return reply, "offline"
