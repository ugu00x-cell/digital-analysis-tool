"""ハイパーソフト管理画面から31日区切りで売上伝票データをエクスポートするツール

ログインは手動で行う前提。ログイン完了後にEnterキーで実行を継続し、
指定した期間を31日ずつに区切って「エクセル」ボタンをクリック、
ダウンロードされたファイルを日付範囲つきのファイル名でリネームして保存する。
"""

import argparse
import calendar
import logging
from datetime import date
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from config import DATE_END_ID, DATE_START_ID, DOWNLOAD_DIR, EXPORT_BUTTON_TEXT, EXPORT_URL, LOG_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def generate_date_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """開始日〜終了日を暦月単位（各月1日〜月末）の区間に分割する

    Args:
        start: エクスポート対象の開始日
        end: エクスポート対象の終了日

    Returns:
        (区間開始日, 区間終了日) のタプルのリスト。各区間は31日以内に収まる
    """
    if start > end:
        raise ValueError("開始日は終了日より前である必要があります")

    chunks: list[tuple[date, date]] = []
    year, month = start.year, start.month
    while date(year, month, 1) <= end:
        last_day = calendar.monthrange(year, month)[1]
        chunk_start = max(start, date(year, month, 1))
        chunk_end = min(end, date(year, month, last_day))
        chunks.append((chunk_start, chunk_end))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return chunks


def export_chunk(page: Page, chunk_start: date, chunk_end: date, store_label: str, download_dir: Path) -> Path:
    """1区間分の期間を指定してエクセルエクスポートを実行し、リネームして保存する

    Args:
        page: ログイン済み・エクスポート画面を開いているPlaywrightページ
        chunk_start: 区間開始日
        chunk_end: 区間終了日
        store_label: 出力ファイル名に使う店舗識別子（例: amuse_kannai）
        download_dir: 保存先ディレクトリ

    Returns:
        保存したファイルのパス
    """
    page.fill(f"table#{DATE_START_ID} input", chunk_start.strftime("%Y/%m/%d"))
    page.fill(f"table#{DATE_END_ID} input", chunk_end.strftime("%Y/%m/%d"))

    with page.expect_download(timeout=3_000) as download_info:
        page.get_by_text(EXPORT_BUTTON_TEXT, exact=True).click()
    download = download_info.value

    store_dir = download_dir / store_label
    store_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"売上伝票一覧_{chunk_start:%Y%m}.xlsx"
    save_path = store_dir / file_name
    download.save_as(save_path)
    logger.info(f"保存完了: {save_path}")
    return save_path


def run(start_date: date, end_date: date, store_label: str) -> None:
    """手動ログイン待機後、期間を31日ずつに分割してエクスポートを繰り返す

    Args:
        start_date: エクスポート対象の開始日
        end_date: エクスポート対象の終了日
        store_label: 出力ファイル名に使う店舗識別子
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    chunks = generate_date_chunks(start_date, end_date)
    logger.info(f"期間 {start_date} 〜 {end_date} を {len(chunks)} 区間に分割しました")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(EXPORT_URL)

        input("ハイパーソフト管理画面にログインし、売上伝票確認の画面を開いたらEnterキーを押してください...")

        for chunk_start, chunk_end in chunks:
            try:
                export_chunk(page, chunk_start, chunk_end, store_label, DOWNLOAD_DIR)
            except Exception as e:
                logger.error(f"区間 {chunk_start}〜{chunk_end} のエクスポートに失敗しました: {e}")

        browser.close()


def main() -> None:
    """コマンドライン引数を受け取ってエクスポート処理を実行する"""
    parser = argparse.ArgumentParser(description="ハイパーソフト31日区切りエクスポートツール")
    parser.add_argument("--start", required=True, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="終了日 (YYYY-MM-DD)")
    parser.add_argument("--store", required=True, help="出力ファイル名に使う店舗識別子（例: amuse_kannai）")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    run(start_date, end_date, args.store)


if __name__ == "__main__":
    main()
