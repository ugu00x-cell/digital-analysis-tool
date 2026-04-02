"""
フォームテスター — エントリーポイント
企業サイトの問い合わせフォームを自動検出・解析・送信テストする
全件スクリーニング対応: 結果を4つのCSVに振り分けて出力
asyncio並列処理対応: --workers N で同時処理数を指定
"""

import argparse
import asyncio
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PwTimeout
from tqdm import tqdm

from config import (
    DEFAULT_DELAY, DELAY_JITTER, MAX_PER_HOUR,
    PAGE_TIMEOUT, CONSECUTIVE_ERROR_LIMIT,
    STATUS_SUCCESS, STATUS_PARTIAL, STATUS_NO_FORM,
    STATUS_CAPTCHA, STATUS_TIMEOUT, STATUS_ERROR,
)
from mapper import get_full_mapping
from logger import (
    generate_result_filename, save_results,
    load_processed_urls, print_summary, print_screening_summary,
    save_screening_csvs,
)

# UTF-8コンソール出力
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

log = logging.getLogger(__name__)

# 並列処理の上限
MAX_WORKERS: int = 10


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(
        description="企業サイトのお問い合わせフォームを自動検出・テスト"
    )
    parser.add_argument("input_csv", help="入力CSVファイルパス")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="フォーム解析のみ、送信しない（デフォルト）")
    parser.add_argument("--send", action="store_true",
                        help="実際に送信する（確認プロンプト表示）")
    parser.add_argument("--limit", type=int, default=None,
                        help="処理する企業数の上限")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY,
                        help=f"1件ごとの待機秒数（デフォルト: {DEFAULT_DELAY}）")
    parser.add_argument("--headed", action="store_true",
                        help="ブラウザを画面表示する")
    parser.add_argument("--resume", action="store_true",
                        help="前回中断した続きから再開")
    parser.add_argument("--workers", type=int, default=5,
                        help="並列処理数（デフォルト: 5、最大: 10）")
    parser.add_argument("--timeout", type=int, default=None,
                        help="1件あたりのタイムアウト秒数（デフォルト: config.pyのPAGE_TIMEOUT）")
    return parser.parse_args()


def load_input_csv(filepath: str) -> pd.DataFrame:
    """入力CSVを読み込む（UTF-8 BOM付き対応、列名の揺れを吸収）"""
    df = pd.read_csv(filepath, encoding='utf-8-sig')
    # error_list.csv等の結果CSVを再入力する場合、列名を統一
    if "URL" in df.columns and "企業サイトURL" not in df.columns:
        df["企業サイトURL"] = df["URL"]
    log.info(f"入力CSV読み込み: {filepath} ({len(df)}件)")
    return df


# === async版 scraper関数群 ===

def _timeout() -> int:
    """現在のタイムアウト値を取得する（--timeout反映用）"""
    import config
    return config.PAGE_TIMEOUT


async def async_check_site_alive(page, url: str) -> tuple[int, bool]:
    """サイトの死活確認（async版）"""
    try:
        resp = await page.goto(url, timeout=_timeout(), wait_until="networkidle")
        status = resp.status if resp else 0
        return status, 200 <= status < 400
    except PwTimeout:
        return 0, False
    except Exception:
        return 0, False


async def async_find_contact_link(page, base_url: str) -> str | None:
    """トップページから「お問い合わせ」リンクを探す（async版）"""
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    from config import CONTACT_LINK_KEYWORDS

    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('a', href=True)

    for link in links:
        text = link.get_text(strip=True).lower()
        href = link['href'].lower()
        for kw in CONTACT_LINK_KEYWORDS:
            if kw in text or kw in href:
                return urljoin(base_url, link['href'])
    return None


async def async_try_fallback(page, base_url: str) -> str | None:
    """フォールバックパスを試す（async版）"""
    from urllib.parse import urljoin
    from config import FALLBACK_PATHS

    for path in FALLBACK_PATHS:
        url = urljoin(base_url, path)
        try:
            resp = await page.goto(url, timeout=_timeout(), wait_until="networkidle")
            if resp and resp.status < 400:
                form = await page.query_selector('form')
                if form:
                    return url
        except Exception:
            continue
    return None


async def async_navigate_to_form(page, base_url: str) -> str | None:
    """フォームページへ遷移する（async版）"""
    contact_url = await async_find_contact_link(page, base_url)
    if contact_url:
        try:
            await page.goto(contact_url, timeout=_timeout(), wait_until="networkidle")
            return contact_url
        except Exception:
            pass
    return await async_try_fallback(page, base_url)


async def async_extract_fields(page) -> list[dict[str, str]]:
    """フォーム要素を全取得する（async版）"""
    from bs4 import BeautifulSoup, Tag

    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.find('form')
    if not form:
        return []

    fields: list[dict[str, str]] = []
    for tag in form.find_all(['input', 'textarea', 'select']):
        if not isinstance(tag, Tag):
            continue
        input_type = tag.get('type', 'text')
        if input_type in ('hidden', 'submit', 'button', 'image', 'reset'):
            continue
        # labelテキスト取得
        label = ''
        tag_id = tag.get('id', '')
        if tag_id:
            lbl = soup.find('label', attrs={'for': tag_id})
            if lbl:
                label = lbl.get_text(strip=True)
        if not label and tag.parent and tag.parent.name == 'label':
            label = tag.parent.get_text(strip=True)

        fields.append({
            'tag': tag.name, 'type': input_type,
            'name': tag.get('name', ''), 'placeholder': tag.get('placeholder', ''),
            'label': label, 'id': tag_id,
        })
    return fields


async def async_detect_captcha(page) -> bool:
    """CAPTCHA検出（async版）"""
    from config import CAPTCHA_PATTERNS
    html = (await page.content()).lower()
    for pattern in CAPTCHA_PATTERNS:
        if pattern in html:
            return True
    return False


async def async_detect_form_type(page) -> str:
    """フォーム種別判定（async版）"""
    from bs4 import BeautifulSoup
    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    forms = soup.find_all('form')
    if not forms:
        return 'none'
    for form in forms:
        inputs = form.find_all(['input', 'textarea', 'select'])
        visible = [i for i in inputs if i.get('type') not in ('hidden',)]
        if visible:
            return 'static'
    return 'dynamic'


# === メイン処理 ===

def _judge_status(mapping: dict[str, dict]) -> str:
    """マッピング結果からステータスを判定する"""
    required = {"company", "name", "email", "message"}
    mapped_keys = set(mapping.keys())
    if required.issubset(mapped_keys):
        return STATUS_SUCCESS
    elif mapped_keys:
        return STATUS_PARTIAL
    else:
        return STATUS_NO_FORM


async def process_one_async(
    context, url: str, company: str, dry_run: bool, semaphore: asyncio.Semaphore,
) -> dict:
    """1企業分の処理（async版、セマフォで並列数制御）"""
    async with semaphore:
        start = time.time()
        result = {
            "企業名": company, "URL": url, "HTTPステータス": 0,
            "フォームURL": "", "ステータス": STATUS_ERROR,
            "失敗理由": "", "マッピング結果": "", "フォーム種別": "",
            "CAPTCHA有無": "なし", "処理時間(秒)": 0.0,
            "処理日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        page = await context.new_page()
        page.set_default_timeout(_timeout())

        try:
            # 死活確認
            http_status, alive = await async_check_site_alive(page, url)
            result["HTTPステータス"] = http_status
            if not alive:
                result["ステータス"] = STATUS_TIMEOUT if http_status == 0 else STATUS_ERROR
                result["失敗理由"] = f"サイトアクセス不可 (HTTP {http_status})"
                return result

            # フォーム遷移
            form_url = await async_navigate_to_form(page, url)
            if not form_url:
                result["ステータス"] = STATUS_NO_FORM
                result["失敗理由"] = "フォームページが見つからない"
                return result
            result["フォームURL"] = form_url
            result["フォーム種別"] = await async_detect_form_type(page)

            # CAPTCHA
            if await async_detect_captcha(page):
                result["ステータス"] = STATUS_CAPTCHA
                result["CAPTCHA有無"] = "あり"
                return result

            # フィールド抽出・マッピング
            fields = await async_extract_fields(page)
            if not fields:
                result["ステータス"] = STATUS_NO_FORM
                result["失敗理由"] = "フォーム要素なし"
                return result

            mapping = get_full_mapping(fields)
            result["マッピング結果"] = str(list(mapping.keys()))
            result["失敗理由"] = "dry-runのため送信スキップ" if dry_run else ""
            result["ステータス"] = _judge_status(mapping)

        except PwTimeout:
            result["ステータス"] = STATUS_TIMEOUT
            result["失敗理由"] = "タイムアウト"
        except Exception as e:
            result["ステータス"] = STATUS_ERROR
            result["失敗理由"] = str(e)[:200]
        finally:
            result["処理時間(秒)"] = round(time.time() - start, 1)
            await page.close()

        # ランダム待機（サーバー負荷軽減）
        jitter = max(0.5, DEFAULT_DELAY / 2 + random.uniform(-1, 1))
        await asyncio.sleep(jitter)

        return result


async def run_parallel(
    tasks_data: list[tuple[str, str]],
    args: argparse.Namespace,
    processed_urls: set[str],
) -> list[dict]:
    """全企業を並列で処理する"""
    workers = min(args.workers, MAX_WORKERS)
    dry_run = not args.send
    semaphore = asyncio.Semaphore(workers)

    log.info(f"並列処理: {workers}ワーカー")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # タスクを作成（処理済みスキップ）
        pending_tasks = []
        for url, company in tasks_data:
            if url in processed_urls:
                continue
            pending_tasks.append((url, company))

        log.info(f"処理対象: {len(pending_tasks)}社（スキップ: {len(tasks_data) - len(pending_tasks)}社）")

        # 非同期タスクを実行し、完了順に結果を収集
        records: list[dict] = []
        result_file = generate_result_filename()
        consecutive_errors = 0

        pbar = tqdm(total=len(pending_tasks), desc="スクリーニング中")

        # バッチ処理（workers数ずつ投入）
        for i in range(0, len(pending_tasks), workers):
            batch = pending_tasks[i:i + workers]
            coros = [
                process_one_async(context, url, company, dry_run, semaphore)
                for url, company in batch
            ]
            batch_results = await asyncio.gather(*coros, return_exceptions=True)

            for j, res in enumerate(batch_results):
                if isinstance(res, Exception):
                    url, company = batch[j]
                    res = {
                        "企業名": company, "URL": url, "HTTPステータス": 0,
                        "フォームURL": "", "ステータス": STATUS_ERROR,
                        "失敗理由": str(res)[:200], "マッピング結果": "",
                        "フォーム種別": "", "CAPTCHA有無": "なし",
                        "処理時間(秒)": 0.0,
                        "処理日時": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }

                records.append(res)
                status = res["ステータス"]
                company_name = res["企業名"]
                pbar.set_postfix_str(f"{company_name} → {status}")
                pbar.update(1)

                # 連続エラー検知
                if status in (STATUS_ERROR, STATUS_TIMEOUT):
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

            # 途中保存（バッチごと）
            save_results(records, result_file)

            # 連続エラー5件で一時停止
            if consecutive_errors >= CONSECUTIVE_ERROR_LIMIT:
                log.warning(f"{CONSECUTIVE_ERROR_LIMIT}件連続エラー検出")
                try:
                    pbar.close()
                    answer = input("続行しますか？ (y/n): ").strip().lower()
                    if answer != 'y':
                        log.info("ユーザーにより中断")
                        break
                except EOFError:
                    log.info("入力なし — 自動続行")
                consecutive_errors = 0
                pbar = tqdm(
                    total=len(pending_tasks), initial=len(records),
                    desc="スクリーニング中"
                )

        pbar.close()
        await browser.close()

    return records


def confirm_send() -> bool:
    """送信モード実行前の確認プロンプトを表示する"""
    log.info("⚠️ --send モードが指定されました。実際にフォーム送信を行います。")
    answer = input("続行しますか？ (y/n): ").strip().lower()
    return answer == 'y'


def main() -> None:
    """メイン処理を実行する"""
    args = parse_args()

    # --timeout: グローバルのPAGE_TIMEOUTを上書き
    if args.timeout:
        import config
        config.PAGE_TIMEOUT = args.timeout * 1000  # 秒→ミリ秒
        # このモジュールのPAGE_TIMEOUTも更新
        global PAGE_TIMEOUT
        PAGE_TIMEOUT = config.PAGE_TIMEOUT
        log.info(f"タイムアウト変更: {args.timeout}秒 ({config.PAGE_TIMEOUT}ms)")

    if args.send and not confirm_send():
        log.info("送信キャンセル")
        return

    # 入力CSV読み込み
    df = load_input_csv(args.input_csv)

    # --limit適用
    if args.limit:
        df = df.head(args.limit)
        log.info(f"先頭{args.limit}件に制限")

    # --resume: 処理済みURLをスキップ
    processed_urls: set[str] = set()
    if args.resume:
        processed_urls = load_processed_urls(Path("."))

    # タスクデータ作成
    tasks_data: list[tuple[str, str]] = []
    for _, row in df.iterrows():
        url = str(row.get("企業サイトURL", "")).strip()
        company = str(row.get("企業名", "不明")).strip()
        tasks_data.append((url, company))

    mode_label = "dry-run" if not args.send else "SEND"
    log.info(f"=== フォームテスト開始 ({mode_label}) ===")

    total_start = time.time()

    # 並列実行
    records = asyncio.run(run_parallel(tasks_data, args, processed_urls))

    # 最終保存
    result_file = generate_result_filename()
    save_results(records, result_file)

    # 振り分けCSV出力
    save_screening_csvs(records)

    # サマリー表示
    elapsed = time.time() - total_start
    print_summary(records, elapsed)
    print_screening_summary(records)


if __name__ == "__main__":
    main()
