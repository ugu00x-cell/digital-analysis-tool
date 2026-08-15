"""音声入力でタスクを記録し、日付ファイルに保存するスクリプト（叩き台）。

マイクから音声を取得し、Google Web Speech APIでテキスト化して
本日日付のタスクファイル（tasks/YYYY-MM-DD.md）に追記する。
「終了」と発話するか Ctrl+C で終了する。

前提ライブラリ（未インストールの場合）:
    pip install SpeechRecognition PyAudio
"""

import logging

import speech_recognition as sr

from utils.file_helper import append_task

# CLAUDE.md記載のログフォーマットに準拠
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# 終了を意味する発話キーワード
EXIT_KEYWORDS = ("終了", "おわり", "終わり")


def recognize_once(recognizer: sr.Recognizer, microphone: sr.Microphone) -> str | None:
    """マイクから1回分の音声を取得し、テキストに変換する。

    Args:
        recognizer: speech_recognitionの認識器インスタンス。
        microphone: 入力元マイクインスタンス。

    Returns:
        str | None: 認識できたテキスト。認識できなかった場合はNone。
    """
    with microphone as source:
        # 周囲のノイズレベルに合わせて調整する
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        logger.info("話しかけてください...")
        try:
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            logger.warning("音声入力がタイムアウトしました（無音）")
            return None

    try:
        text = recognizer.recognize_google(audio, language="ja-JP")
        logger.info(f"認識結果: {text}")
        return text
    except sr.UnknownValueError:
        logger.warning("音声を認識できませんでした")
        return None
    except sr.RequestError as e:
        logger.error(f"音声認識APIへの接続に失敗しました: {e}")
        return None


def run_voice_task_once() -> None:
    """音声入力を1回だけ受け付け、タスクとして保存して自動終了する。

    「終了」等のキーワードが発話された場合は保存せずに終了する。
    Ctrl+Cでの中断にも対応する。
    """
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    logger.info("音声タスク入力を開始します。1回の発話でタスクを記録し、自動的に終了します。")

    try:
        text = recognize_once(recognizer, microphone)
        if text is None:
            logger.warning("タスクを認識できなかったため、何も保存せず終了します。")
            return

        if text.strip() in EXIT_KEYWORDS:
            logger.info("終了キーワードを検知したため、保存せず終了します。")
            return

        append_task(text)
        logger.info("タスクを1件記録しました。処理を終了します。")
    except KeyboardInterrupt:
        logger.info("Ctrl+Cにより処理を中断しました。")


if __name__ == "__main__":
    run_voice_task_once()
