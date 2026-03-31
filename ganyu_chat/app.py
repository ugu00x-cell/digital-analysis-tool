"""
甘雨チャットアプリ
原神のキャラクター「甘雨」と会話できる Streamlit チャットUI
APIキーあり → Claude API / なし → データセット検索 で自動切り替え
"""

import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from responder import get_response

# .env ファイルを自動読み込み（同ディレクトリの .env を優先）
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

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

# ─── テーマカラー（璃月の水色・薄紫） ───────────────────
COLOR_PRIMARY   = "#7EC8D8"
COLOR_ACCENT    = "#C4A8D8"
COLOR_BG_USER   = "#EAF6FF"
COLOR_BG_GANYU  = "#F3EEFF"
COLOR_TEXT_DARK = "#2E2640"


def init_page() -> None:
    """ページ設定とカスタムCSSを初期化する"""
    st.set_page_config(
        page_title="甘雨チャット",
        page_icon="🦋",
        layout="centered",
    )
    st.markdown(f"""
    <style>
        .stApp {{
            background: linear-gradient(160deg, #E8F4FD 0%, #F0E8FF 100%);
        }}
        .stChatInput textarea {{
            border: 2px solid {COLOR_PRIMARY} !important;
            border-radius: 12px !important;
        }}
        .user-bubble {{
            background: {COLOR_BG_USER};
            border-left: 4px solid {COLOR_PRIMARY};
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            color: {COLOR_TEXT_DARK};
        }}
        .ganyu-bubble {{
            background: {COLOR_BG_GANYU};
            border-left: 4px solid {COLOR_ACCENT};
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            color: {COLOR_TEXT_DARK};
        }}
        .header-card {{
            background: linear-gradient(135deg, #5BA3BA, #9B7DBE);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 24px;
            color: white;
        }}
        .avatar-emoji {{ font-size: 48px; line-height: 1; }}
        .status-badge {{
            display: inline-block;
            background: rgba(255,255,255,0.25);
            border-radius: 20px;
            padding: 2px 12px;
            font-size: 12px;
            margin-top: 4px;
        }}
        .mode-badge-api {{
            display: inline-block;
            background: #4CAF50;
            color: white;
            border-radius: 20px;
            padding: 1px 10px;
            font-size: 11px;
        }}
        .mode-badge-offline {{
            display: inline-block;
            background: #FF9800;
            color: white;
            border-radius: 20px;
            padding: 1px 10px;
            font-size: 11px;
        }}
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #D6EEF7 0%, #E8DEFF 100%);
        }}
    </style>
    """, unsafe_allow_html=True)


def render_header(mode: str) -> None:
    """甘雨のヘッダーカードを表示する。現在のモードもバッジで表示する。

    Args:
        mode: "api" または "offline"
    """
    mode_label = (
        '<span class="mode-badge-api">⚡ Claude API</span>'
        if mode == "api"
        else '<span class="mode-badge-offline">📖 オフライン</span>'
    )
    st.markdown(f"""
    <div class="header-card">
        <div style="display:flex; align-items:center; gap:16px">
            <div class="avatar-emoji">🦋</div>
            <div>
                <div style="font-size:22px; font-weight:700; letter-spacing:2px">
                    甘雨 {mode_label}
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
    """サイドバーにプロフィール・APIキー設定・話しかけ例を表示する"""
    with st.sidebar:
        st.markdown("## 📋 甘雨プロフィール")
        st.markdown("""
        <div style="background:white; border-radius:12px; padding:14px; margin-bottom:12px">
            <p style="margin:4px 0; font-size:13px">🌙 <b>所属</b>：璃月港 七星秘書局</p>
            <p style="margin:4px 0; font-size:13px">🦋 <b>種族</b>：半仙人（麒麟の血統）</p>
            <p style="margin:4px 0; font-size:13px">❄️ <b>元素</b>：氷</p>
            <p style="margin:4px 0; font-size:13px">🍮 <b>好物</b>：杏仁豆腐</p>
            <p style="margin:4px 0; font-size:13px">📄 <b>特技</b>：書類仕事・情報整理</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("## 🔑 APIキー設定")

        env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        env_valid = env_key and not env_key.startswith("sk-ant-ここに")
        dot_env_path = Path(__file__).parent / ".env"

        if env_valid:
            source = ".env ファイル" if dot_env_path.exists() else "環境変数"
            st.success(f"{source}から読み込み済み ✅\n⚡ Claude API モードで動作中")
        else:
            # 未設定でもオフラインモードで動くことを案内
            st.info(
                "APIキーなしでも **オフラインモード** で動作します📖\n\n"
                "より自然な会話には `.env` にキーを設定してください",
                icon="💡",
            )
            input_key = st.text_input(
                "Anthropic APIキー（任意）",
                type="password",
                placeholder="sk-ant-...",
                help="設定するとClaude APIで返答します",
                key="api_key_input",
            )
            if input_key:
                st.success("APIキーが入力されました ✅\n⚡ Claude API モードで動作します")

        st.markdown("---")
        st.markdown("## 💬 話しかけてみよう")
        st.markdown("""
        <div style="font-size:13px; line-height:1.8">
        • 「おはよう、甘雨ちゃん」<br>
        • 「ツノ触らせて」<br>
        • 「好きな食べ物は？」<br>
        • 「休日は何してるの？」<br>
        • 「一緒に戦ってほしい」
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑️ 会話をリセット", use_container_width=True):
            st.session_state.messages = []
            logger.info("会話履歴をリセット")
            st.rerun()

        st.markdown("---")
        st.caption("📖 オフライン: データセット検索（100件）")
        st.caption("⚡ API: claude-sonnet-4-20250514")


def get_api_key() -> str | None:
    """APIキーを取得する。優先順位: .env/環境変数 → サイドバー入力欄。

    Returns:
        有効なAPIキー文字列。未設定の場合はNone
    """
    # 1. 環境変数（load_dotenv で .env を展開済み）
    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if env_key and not env_key.startswith("sk-ant-ここに"):
        return env_key
    # 2. サイドバーの手入力
    input_key = st.session_state.get("api_key_input", "").strip()
    return input_key if input_key else None


def render_message(role: str, content: str, mode: str = "") -> None:
    """メッセージをバブル形式で表示する。

    Args:
        role: "user" または "assistant"
        content: メッセージ本文
        mode: 甘雨の返答モード（"api" | "offline"）表示用
    """
    if role == "user":
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
        # モードバッジ（API / オフライン）
        mode_badge = ""
        if mode == "api":
            mode_badge = '<span class="mode-badge-api" style="float:right">⚡API</span>'
        elif mode == "offline":
            mode_badge = '<span class="mode-badge-offline" style="float:right">📖offline</span>'

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"""
            <div class="ganyu-bubble">
                <span style="font-size:11px; color:#888; display:block; margin-bottom:4px">
                    🦋 甘雨 {mode_badge}
                </span>
                {content}
            </div>
            """, unsafe_allow_html=True)


def init_session() -> None:
    """セッションステートを初期化する"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "modes" not in st.session_state:
        # 各返答に対応するモードを記録する
        st.session_state.modes = []


def main() -> None:
    """アプリのメインエントリーポイント"""
    init_page()
    init_session()

    # 現在のモードを判定（ヘッダー表示用）
    api_key = get_api_key()
    current_mode = "api" if api_key else "offline"

    render_header(current_mode)
    render_sidebar()

    # 会話履歴の表示
    if not st.session_state.messages:
        # 初期メッセージ（固定文・APIコールなし）
        st.markdown("""
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
        # メッセージと対応するモードをペアで表示
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] == "assistant":
                # 対応するモードを取り出す（記録がなければ空文字）
                mode = st.session_state.modes[i] if i < len(st.session_state.modes) else ""
                render_message(msg["role"], msg["content"], mode=mode)
            else:
                render_message(msg["role"], msg["content"])

    # チャット入力
    user_input = st.chat_input("旅人として話しかけてみてください…")

    if user_input:
        # ユーザーメッセージを追加・表示
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.session_state.modes.append("")   # ユーザーにはモードなし
        render_message("user", user_input)
        logger.info(f"ユーザー入力: {user_input[:50]}")

        # 返答生成（APIキーあり → Claude API / なし → オフライン）
        spinner_text = "甘雨が考えています…" if api_key else "甘雨がデータを検索しています…"
        with st.spinner(spinner_text):
            reply, mode = get_response(st.session_state.messages, api_key)

        # 返答を追加・表示
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.session_state.modes.append(mode)
        render_message("assistant", reply, mode=mode)
        logger.info(f"返答生成完了: モード={mode}, 文字数={len(reply)}")

        st.rerun()


if __name__ == "__main__":
    main()
