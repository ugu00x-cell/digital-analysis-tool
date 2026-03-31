"""
甘雨チャットアプリ
原神のキャラクター「甘雨」と会話できる Streamlit チャットUI
Claude API (claude-sonnet-4-20250514) を使用
"""

import logging
import os
from pathlib import Path

import anthropic
import streamlit as st
from dotenv import load_dotenv

# .env ファイルを自動読み込み（同ディレクトリの .env を優先）
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)  # 既存の環境変数は上書きしない

# ─── ログ設定 ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('ganyu_chat.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── 定数 ────────────────────────────────────────────────
MODEL_NAME   = "claude-sonnet-4-20250514"
MAX_TOKENS   = 1024
# 甘雨のテーマカラー（璃月の水色・薄紫）
COLOR_PRIMARY   = "#7EC8D8"   # 水色（甘雨の髪色）
COLOR_ACCENT    = "#C4A8D8"   # 薄紫（甘雨のツノ）
COLOR_BG_USER   = "#EAF6FF"   # ユーザーのバブル背景
COLOR_BG_GANYU  = "#F3EEFF"   # 甘雨のバブル背景
COLOR_TEXT_DARK = "#2E2640"   # 璃月の夜空色（文字）

# 甘雨のシステムプロンプト
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
- 自分が半仙人であることを少し気にしている（普通の人間に混じって暮らしている）
- 甘いものが好き（特に杏仁豆腐）
- 休暇の取り方がわからなく、仕事ばかりしてしまう
- 旅人のことを大切に思っており、できる限り力になろうとする

【応答スタイル】
- 2〜5文程度の自然な会話
- 突然の質問にも丁寧に対応する
- 感情表現は控えめだが、旅人への気遣いは言葉の端々ににじみ出る
- 質問には誠実に答え、わからないことは「存じません」と正直に言う
"""


def init_page() -> None:
    """ページ設定とスタイルを初期化する"""
    st.set_page_config(
        page_title="甘雨チャット",
        page_icon="🦋",
        layout="centered",
    )
    # カスタム CSS
    st.markdown(f"""
    <style>
        /* 全体背景 */
        .stApp {{
            background: linear-gradient(160deg, #E8F4FD 0%, #F0E8FF 100%);
        }}
        /* チャット入力欄 */
        .stChatInput textarea {{
            border: 2px solid {COLOR_PRIMARY} !important;
            border-radius: 12px !important;
        }}
        /* ユーザーメッセージ */
        .user-bubble {{
            background: {COLOR_BG_USER};
            border-left: 4px solid {COLOR_PRIMARY};
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            color: {COLOR_TEXT_DARK};
        }}
        /* 甘雨メッセージ */
        .ganyu-bubble {{
            background: {COLOR_BG_GANYU};
            border-left: 4px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            color: {COLOR_TEXT_DARK};
        }}
        /* ヘッダーカード */
        .header-card {{
            background: linear-gradient(135deg, #5BA3BA, #9B7DBE);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 24px;
            color: white;
        }}
        /* アバター装飾 */
        .avatar-emoji {{
            font-size: 48px;
            line-height: 1;
        }}
        /* ステータスバッジ */
        .status-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.25);
            border-radius: 20px;
            padding: 2px 12px;
            font-size: 12px;
            margin-top: 4px;
        }}
        /* サイドバー */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #D6EEF7 0%, #E8DEFF 100%);
        }}
    </style>
    """, unsafe_allow_html=True)


def render_header() -> None:
    """甘雨のヘッダーカードを表示する"""
    st.markdown("""
    <div class="header-card">
        <div style="display:flex; align-items:center; gap:16px">
            <div class="avatar-emoji">🦋</div>
            <div>
                <div style="font-size:22px; font-weight:700; letter-spacing:2px">
                    甘雨
                </div>
                <div style="font-size:13px; opacity:0.9; margin-top:2px">
                    璃月港・七星秘書局
                </div>
                <div class="status-badge">✦ 勤務中</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar() -> None:
    """サイドバーにプロフィール情報・APIキー入力欄を表示する"""
    with st.sidebar:
        st.markdown("## 📋 甘雨プロフィール")
        st.markdown(f"""
        <div style="background:white; border-radius:12px; padding:14px; margin-bottom:12px">
            <p style="margin:4px 0; font-size:13px">🌙 <b>所属</b>：璃月港 七星秘書局</p>
            <p style="margin:4px 0; font-size:13px">🦋 <b>種族</b>：半仙人（麒麟の血統）</p>
            <p style="margin:4px 0; font-size:13px">❄️ <b>元素</b>：氷</p>
            <p style="margin:4px 0; font-size:13px">🍮 <b>好物</b>：杏仁豆腐</p>
            <p style="margin:4px 0; font-size:13px">📄 <b>特技</b>：書類仕事・情報整理</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("## 💬 話しかけてみよう")
        st.markdown("""
        <div style="font-size:13px; line-height:1.8">
        • 「今日の仕事はどう？」<br>
        • 「ツノ触らせて」<br>
        • 「休日は何してるの？」<br>
        • 「好きな食べ物は？」<br>
        • 「璃月について教えて」
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        # 履歴クリアボタン
        if st.button("🗑️ 会話をリセット", use_container_width=True):
            st.session_state.messages = []
            logger.info("会話履歴をリセットしました")
            st.rerun()

        st.markdown("---")
        # APIキー設定状況の表示
        st.markdown("## 🔑 APIキー設定")
        env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        dot_env_path = Path(__file__).parent / ".env"
        env_loaded = (
            env_key
            and not env_key.startswith("sk-ant-ここに")
        )

        if env_loaded:
            # .env または環境変数から読み込み済み
            source = ".env ファイル" if dot_env_path.exists() else "環境変数"
            st.success(f"{source}から読み込み済み ✅")
        else:
            # 未設定 → サイドバーで手入力
            if dot_env_path.exists():
                st.info(
                    f"💡 **{dot_env_path.name}** にAPIキーを書くと\n"
                    "次回から自動で読み込まれます",
                    icon="💡",
                )
            input_key = st.text_input(
                "Anthropic APIキーを入力",
                type="password",
                placeholder="sk-ant-...",
                help="https://console.anthropic.com から取得できます",
                key="api_key_input",
            )
            if input_key:
                st.success("APIキーが入力されました ✅")
            else:
                st.warning("APIキーを入力してください")

        st.caption(f"🤖 モデル: {MODEL_NAME}")


def get_api_key() -> str | None:
    """APIキーを取得する。
    優先順位: .envファイル / 環境変数（起動時に load_dotenv で読込済み）→ サイドバー入力欄。

    Returns:
        APIキー文字列。どちらも未設定の場合はNone
    """
    # 1. 環境変数（.env の内容は起動時に環境変数へ展開済み）
    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    # プレースホルダーのままなら無効扱い
    if env_key and not env_key.startswith("sk-ant-ここに"):
        return env_key
    # 2. サイドバーの入力欄にフォールバック
    input_key = st.session_state.get("api_key_input", "").strip()
    return input_key if input_key else None


def call_claude(messages: list[dict]) -> str:
    """Claude API を呼び出して甘雨の返答を生成する。

    Args:
        messages: これまでの会話履歴（role / content の辞書リスト）

    Returns:
        甘雨の返答テキスト
    """
    api_key = get_api_key()
    if api_key is None:
        logger.error("ANTHROPIC_API_KEY が設定されていません")
        return "申し訳ございません…APIキーが設定されていないようです。環境変数 ANTHROPIC_API_KEY をご確認ください。"

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
        return "APIキーの認証に失敗しました。正しいキーが設定されているかご確認ください。"
    except anthropic.RateLimitError:
        logger.warning("APIレート制限")
        return "申し訳ございません、少し混み合っております。少し時間をおいてからお声がけください。"
    except Exception as e:
        logger.error(f"API呼び出しエラー: {e}")
        return "少々不具合が生じてしまいました。時間をおいて再度お試しください。"


def render_message(role: str, content: str) -> None:
    """メッセージをバブル形式で表示する。

    Args:
        role: "user" または "assistant"
        content: メッセージ本文
    """
    if role == "user":
        # ユーザーメッセージ（右寄せ風）
        col1, col2 = st.columns([1, 4])
        with col2:
            st.markdown(f"""
            <div class="user-bubble">
                <span style="font-size:11px; color:#888; display:block; margin-bottom:4px">
                    🌍 旅人
                </span>
                {content}
            </div>
            """, unsafe_allow_html=True)
    else:
        # 甘雨メッセージ（左寄せ）
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class="ganyu-bubble">
                <span style="font-size:11px; color:#888; display:block; margin-bottom:4px">
                    🦋 甘雨
                </span>
                {content}
            </div>
            """, unsafe_allow_html=True)


def init_session() -> None:
    """セッションステートを初期化する"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
        logger.info("新しい会話セッションを開始しました")


def main() -> None:
    """アプリのメインエントリーポイント"""
    init_page()
    init_session()

    render_header()
    render_sidebar()

    # APIキーチェック（環境変数・サイドバー入力どちらも未設定の場合は待機）
    if get_api_key() is None:
        st.markdown(f"""
        <div class="ganyu-bubble">
            <span style="font-size:11px; color:#888; display:block; margin-bottom:4px">
                🦋 甘雨
            </span>
            旅人さん、いらっしゃいませ。<br>
            ご用件を承る前に、左のサイドバーから<b>APIキーを入力</b>していただけますでしょうか。<br>
            <span style="font-size:12px; color:#999;">
            （環境変数 <code>ANTHROPIC_API_KEY</code> でも設定できます）
            </span>
        </div>
        """, unsafe_allow_html=True)
        return

    # 会話履歴の表示
    if not st.session_state.messages:
        # 初期メッセージ（APIコールなし・固定文）
        st.markdown(f"""
        <div class="ganyu-bubble">
            <span style="font-size:11px; color:#888; display:block; margin-bottom:4px">
                🦋 甘雨
            </span>
            旅人さん、いらっしゃいませ。<br>
            璃月港七星秘書局の甘雨です。<br>
            本日はどのようなご用件でしょうか？
        </div>
        """, unsafe_allow_html=True)
    else:
        for msg in st.session_state.messages:
            render_message(msg["role"], msg["content"])

    # チャット入力
    user_input = st.chat_input("旅人として話しかけてみてください…")

    if user_input:
        # ユーザーメッセージを履歴に追加・表示
        st.session_state.messages.append({"role": "user", "content": user_input})
        render_message("user", user_input)
        logger.info(f"ユーザー入力: {user_input[:50]}")

        # 甘雨の返答を生成
        with st.spinner("甘雨が返答を考えています…"):
            reply = call_claude(st.session_state.messages)

        # 返答を履歴に追加・表示
        st.session_state.messages.append({"role": "assistant", "content": reply})
        render_message("assistant", reply)

        # 再描画して最新の状態を反映
        st.rerun()


if __name__ == "__main__":
    main()
