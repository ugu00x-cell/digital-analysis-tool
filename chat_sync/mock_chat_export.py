"""Claude Chatのやり取りをローカルファイルにエクスポートするモック版。

実際のClaude API連携の前に、ダミーデータで仕組みを検証するためのプロトタイプ。
将来的には実のAPI連携に置き換える。
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# チャットログの保存先ディレクトリ
CHAT_LOGS_DIR = Path(__file__).resolve().parent / "chat_logs"


def ensure_chat_logs_dir() -> None:
    """chat_logsディレクトリが存在しない場合は作成する。

    Raises:
        OSError: ディレクトリ作成に失敗した場合。
    """
    try:
        CHAT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"チャットログディレクトリを確認: {CHAT_LOGS_DIR}")
    except OSError as e:
        logger.error(f"chat_logsディレクトリの作成に失敗しました: {e}")
        raise


def generate_mock_chat_data() -> list[dict]:
    """ダミーのチャット会話データを生成する。

    Returns:
        list[dict]: チャット会話の辞書リスト。各要素は以下のキーを持つ:
            - timestamp (str): 時刻（HH:MM形式）
            - speaker (str): 発話者（"User" または "Claude"）
            - content (str): メッセージ本文
    """
    mock_data = [
        {
            "timestamp": "17:30",
            "speaker": "User",
            "content": "音声タスクツールをスマホから操作したいんだけど、なんかいい方法ある？",
        },
        {
            "timestamp": "17:31",
            "speaker": "Claude",
            "content": "いくつか方法があります。Web版のclaude.ai/codeを使うか、自宅PCにSSH接続する方法が考えられます。",
        },
        {
            "timestamp": "17:45",
            "speaker": "User",
            "content": "Claude ChatとClaude Codeを使い分けるのが効率的かな？",
        },
        {
            "timestamp": "17:46",
            "speaker": "Claude",
            "content": "そうですね。自宅での実装はClaude Code、外出先での相談はClaude Chatという役割分担がおすすめです。",
        },
    ]
    return mock_data


def format_chat_to_markdown(chat_data: list[dict]) -> str:
    """チャットデータをMarkdown形式に変換する。

    Args:
        chat_data: チャット会話の辞書リスト。

    Returns:
        str: Markdown形式のテキスト。
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    markdown_lines = [f"# Chat Export: {today_str}\n"]

    for message in chat_data:
        timestamp = message["timestamp"]
        speaker = message["speaker"]
        content = message["content"]
        markdown_lines.append(f"## {timestamp} - {speaker}")
        markdown_lines.append(f"\n{content}\n")

    return "\n".join(markdown_lines)


def export_mock_chat() -> Path:
    """ダミーチャットデータを生成し、ファイルに保存する。

    Returns:
        Path: 保存したファイルのパス。

    Raises:
        OSError: ファイル書き込みに失敗した場合。
    """
    ensure_chat_logs_dir()

    # ダミーデータを生成
    mock_data = generate_mock_chat_data()
    logger.info(f"ダミーチャットデータを生成しました: {len(mock_data)}件")

    # Markdown形式に変換
    markdown_content = format_chat_to_markdown(mock_data)

    # ファイル名（YYYY-MM-DD-chat.md）で保存
    today_str = datetime.now().strftime("%Y-%m-%d")
    file_path = CHAT_LOGS_DIR / f"{today_str}-chat.md"

    try:
        file_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"チャットログを保存しました: {file_path}")
        return file_path
    except OSError as e:
        logger.error(f"チャットログの保存に失敗しました: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler("app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    export_mock_chat()
