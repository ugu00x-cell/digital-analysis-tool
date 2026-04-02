"""
フォーム送信
マッピング結果に基づいてダミーデータを入力し、フォームを送信する
"""

import logging

from playwright.sync_api import Page, TimeoutError as PwTimeout

from config import DUMMY_DATA, PAGE_TIMEOUT

log = logging.getLogger(__name__)


def fill_and_submit(
    page: Page,
    mapping: dict[str, dict],
    dry_run: bool = True,
) -> tuple[bool, str]:
    """マッピングに基づいてフォームにダミーデータを入力・送信する

    Returns:
        (成功フラグ, メッセージ)
    """
    if dry_run:
        return True, "dry-runのため送信スキップ"

    filled_count = _fill_form_fields(page, mapping)
    if filled_count == 0:
        return False, "入力可能なフィールドなし"

    return _submit_form(page)


def _fill_form_fields(page: Page, mapping: dict[str, dict]) -> int:
    """マッピングされたフィールドにダミーデータを入力する"""
    filled = 0
    for field_type, field_info in mapping.items():
        value = DUMMY_DATA.get(field_type)
        if not value:
            continue

        selector = _build_selector(field_info)
        if not selector:
            continue

        try:
            element = page.query_selector(selector)
            if element:
                element.fill(value)
                filled += 1
                log.info(f"  入力: {field_type} = {value[:20]}...")
        except Exception as e:
            log.warning(f"  入力失敗 ({field_type}): {e}")

    return filled


def _build_selector(field_info: dict) -> str | None:
    """フィールド情報からCSSセレクタを構築する"""
    # name属性が最も信頼性が高い
    name = field_info.get('name', '')
    if name:
        tag = field_info.get('tag', 'input')
        return f'{tag}[name="{name}"]'

    # id属性で代替
    field_id = field_info.get('id', '')
    if field_id:
        return f'#{field_id}'

    return None


def _submit_form(page: Page) -> tuple[bool, str]:
    """送信ボタンを探してフォームを送信する"""
    # 送信ボタンのセレクタ候補
    submit_selectors = [
        'input[type="submit"]',
        'button[type="submit"]',
        'button:has-text("送信")',
        'button:has-text("確認")',
        'input[value="送信"]',
        'input[value="確認"]',
    ]

    for selector in submit_selectors:
        btn = page.query_selector(selector)
        if btn:
            try:
                btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
                log.info("  フォーム送信完了")
                return True, "送信成功"
            except PwTimeout:
                return True, "送信後タイムアウト（送信自体は完了の可能性）"
            except Exception as e:
                return False, f"送信エラー: {e}"

    return False, "送信ボタンが見つからない"
