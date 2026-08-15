"""タスクファイルの保存・読み込みを担当するヘルパーモジュール。

副作用（ファイルI/O）を含むため、utils/ではあるが単純な純粋関数ではない。
呼び出し元（voice_task_recorder.py）から日付・タスク文字列を受け取り、
`tasks/YYYY-MM-DD.md` に追記保存する。
"""

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# タスクファイルの保存先ディレクトリ（voice_tasklist/tasks/）
TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"


def ensure_tasks_dir() -> None:
    """tasksディレクトリが存在しない場合は作成する。

    Raises:
        OSError: ディレクトリ作成に失敗した場合（権限不足等）。
    """
    try:
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"tasksディレクトリの作成に失敗しました: {e}")
        raise


def get_today_task_file_path() -> Path:
    """本日日付のタスクファイルパスを返す。

    Returns:
        Path: `tasks/YYYY-MM-DD.md` の形式のファイルパス。
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    return TASKS_DIR / f"{today_str}.md"


def append_task(task_text: str) -> Path:
    """本日のタスクファイルに、時刻つきでタスクを1行追記する。

    ファイルが存在しない場合は見出し（# YYYY-MM-DD タスク一覧）から新規作成する。

    Args:
        task_text: 音声認識で取得したタスク文字列。

    Returns:
        Path: 追記したファイルのパス。

    Raises:
        OSError: ファイル書き込みに失敗した場合。
    """
    ensure_tasks_dir()
    file_path = get_today_task_file_path()
    now_str = datetime.now().strftime("%H:%M")

    try:
        # ファイルが未作成なら見出し付きで新規作成する
        if not file_path.exists():
            today_str = datetime.now().strftime("%Y-%m-%d")
            file_path.write_text(f"# {today_str} タスク一覧\n\n", encoding="utf-8")

        with file_path.open("a", encoding="utf-8") as f:
            f.write(f"- [ ] ({now_str}) {task_text}\n")

        logger.info(f"タスクを追記しました: {task_text}")
        return file_path
    except OSError as e:
        logger.error(f"タスクファイルへの書き込みに失敗しました: {e}")
        raise
