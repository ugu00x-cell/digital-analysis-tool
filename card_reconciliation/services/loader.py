"""CSVを読み込んで Transaction / Order のリストに変換するモジュール。"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from card_reconciliation import config
from card_reconciliation.models.transaction import Order, Transaction

logger = logging.getLogger(__name__)


def _to_int_amount(value: object) -> int:
    """
    金額の値（文字列や数値）を整数に変換する。

    カンマ・円記号（半角/全角/「円」）・ウォン記号・通貨記号・空白を除去してから
    int に変換。変換できない場合は ValueError を送出。

    例: "5,940" → 5940
        "28,539円" → 28539
        "¥1,234" → 1234
        "17,180" → 17180 (ウォン表記の数値部分)
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("金額が空です")

    text = str(value).strip()
    # 外側のダブルクォート・シングルクォートを剥がす（"28,539円" 等）
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ('"', "'"):
        text = text[1:-1].strip()
    # カンマ・円記号（半角/全角/「円」）・ウォン記号・空白を除去
    cleaned = re.sub(r"[,¥￥円₩\s]", "", text)

    if cleaned == "" or cleaned == "-":
        raise ValueError(f"金額が不正です: {value!r}")

    try:
        return int(float(cleaned))
    except ValueError as exc:
        raise ValueError(f"金額を数値に変換できません: {value!r}") from exc


def _to_date(value: object) -> date:
    """
    日付らしき値を date 型に変換する。

    pandas の Timestamp、datetime、'YYYY-MM-DD HH:MM:SS'、'YYYY/MM/DD' 等に対応。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("日付が空です")

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    # pandas に任せると多くのフォーマットを吸収してくれる
    try:
        return pd.to_datetime(text).date()
    except (ValueError, TypeError) as exc:
        raise ValueError(f"日付を変換できません: {value!r}") from exc


def _to_date_with_year(value: object, default_year: int) -> date:
    """
    「3/2」のような年抜き日付に default_year を補って date に変換する。

    既に年を含む形式（YYYY/MM/DD, YYYY-MM-DD 等）ならそのまま日付化する。
    竹中さん発注表のように「処理日=3/2」等の表記向け。
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("日付が空です")

    text = str(value).strip()
    # "3/2" "03/02" "3-2" のような M/D 形式を検出（年抜き）
    if re.fullmatch(r"\d{1,2}[/\-]\d{1,2}", text):
        month_str, day_str = re.split(r"[/\-]", text)
        try:
            return date(default_year, int(month_str), int(day_str))
        except ValueError as exc:
            raise ValueError(f"日付を変換できません: {value!r}") from exc

    # それ以外は通常パース
    return _to_date(text)


def load_bakuraku_csv(path: Path) -> list[Transaction]:
    """
    バク楽クレカ明細CSVを読み込んで Transaction のリストを返す。

    「確定」ステータスのみを対象にする（返品等は除外）。

    Args:
        path: バク楽CSVのパス

    Returns:
        確定済み Transaction のリスト

    Raises:
        FileNotFoundError: CSVが存在しない場合
        KeyError: 必要な列が無い場合
    """
    logger.info("バク楽CSVを読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.BAKURAKU_ENCODING, dtype=str)

    required = [
        config.BAKURAKU_COL_DATETIME,
        config.BAKURAKU_COL_AMOUNT,
        config.BAKURAKU_COL_STORE,
        config.BAKURAKU_COL_STATUS,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"バク楽CSVに必要な列がありません: {missing}")

    transactions: list[Transaction] = []
    for idx, row in df.iterrows():
        status = str(row[config.BAKURAKU_COL_STATUS]).strip()
        # 確定以外（返品・キャンセル等）はスキップ
        if status != config.BAKURAKU_VALID_STATUS:
            continue

        try:
            tx = Transaction(
                row_index=int(idx),
                used_at=_to_date(row[config.BAKURAKU_COL_DATETIME]),
                amount=_to_int_amount(row[config.BAKURAKU_COL_AMOUNT]),
                store=str(row[config.BAKURAKU_COL_STORE]).strip(),
                status=status,
            )
        except ValueError as exc:
            # 1行だけ壊れていてもスキップして続行
            logger.warning("バク楽CSV %s行目をスキップ: %s", idx, exc)
            continue
        transactions.append(tx)

    logger.info("バク楽: %d件の確定明細を読み込みました", len(transactions))
    return transactions


def _should_keep_order_row(row: pd.Series) -> bool:
    """
    発注表の1行を採用するかどうか判定する（カード・ステータスでフィルタ）。

    config.ORDER_CARD_FILTERS が空タプルならカード絞り込みなし。
    config.ORDER_VALID_STATUSES が空タプルならステータス絞り込みなし。

    注: 呼び出し側で列存在は事前検証済みの前提（load_order_csv 内）。
    """
    # カード番号フィルタ（Amazon CSVは '="4521"' 形式で来るので部分一致・OR条件）
    if config.ORDER_CARD_FILTERS:
        card_value = str(row[config.ORDER_COL_CARD]) if row[config.ORDER_COL_CARD] is not None else ""
        if not any(card in card_value for card in config.ORDER_CARD_FILTERS):
            return False

    # 注文状況フィルタ
    if config.ORDER_VALID_STATUSES:
        status_value = (
            str(row[config.ORDER_COL_STATUS]).strip()
            if row[config.ORDER_COL_STATUS] is not None
            else ""
        )
        if status_value not in config.ORDER_VALID_STATUSES:
            return False

    return True


def load_order_csv(path: Path) -> list[Order]:
    """
    発注表CSVを読み込んで Order のリストを返す。

    config.ORDER_CARD_FILTERS に指定されたカードのみ、
    config.ORDER_VALID_STATUSES に含まれるステータスのみを対象にする。

    Args:
        path: 発注表CSVのパス

    Returns:
        Order のリスト

    Raises:
        FileNotFoundError: CSVが存在しない場合
        KeyError: 必要な列が無い場合
    """
    logger.info("発注表CSVを読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.ORDER_ENCODING, dtype=str)

    required = [
        config.ORDER_COL_DATE,
        config.ORDER_COL_PRODUCT,
        config.ORDER_COL_UNIT_PRICE,
        config.ORDER_COL_QUANTITY,
        config.ORDER_COL_TOTAL,
    ]
    # フィルタが有効なら対応列も必須（設定ミス・CSV仕様変更を早期検出するため）
    if config.ORDER_CARD_FILTERS:
        required.append(config.ORDER_COL_CARD)
    if config.ORDER_VALID_STATUSES:
        required.append(config.ORDER_COL_STATUS)

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"発注表CSVに必要な列がありません: {missing}")

    orders: list[Order] = []
    skipped_filtered = 0
    for idx, row in df.iterrows():
        # カード・ステータスフィルタ
        if not _should_keep_order_row(row):
            skipped_filtered += 1
            continue

        try:
            order = Order(
                row_index=int(idx),
                ordered_at=_to_date(row[config.ORDER_COL_DATE]),
                product=str(row[config.ORDER_COL_PRODUCT]).strip(),
                unit_price_a=_to_int_amount(row[config.ORDER_COL_UNIT_PRICE]),
                quantity_a=int(_to_int_amount(row[config.ORDER_COL_QUANTITY])),
                total=_to_int_amount(row[config.ORDER_COL_TOTAL]),
                # Amazon注文履歴はA単独なのでBは0のまま（デフォルト）
            )
        except ValueError as exc:
            logger.warning("発注表CSV %s行目をスキップ: %s", idx, exc)
            continue
        orders.append(order)

    logger.info(
        "発注表: %d件の発注を読み込みました（フィルタで除外: %d件）",
        len(orders),
        skipped_filtered,
    )
    return orders


# ============================================================
# 竹中さん発注表（韓国スプシ・A/B仕入れ対応）
# ============================================================
def load_takenaka_order_csv(path: Path) -> list[Order]:
    """
    竹中さん形式の発注表CSVを読み込んで Order のリストを返す。

    特徴:
        - utf-8-sig エンコーディング
        - 「注文日」は「3/2」のような年抜き表記 → config.DEFAULT_YEAR で補完
        - A仕入れ値/A個数 と B仕入れ値/B個数 の両方をサポート
          （Bが空欄の場合は unit_price_b=0, quantity_b=0）
        - ステータス列で config.TAKENAKA_VALID_STATUSES のみ採用
          （キャンセル・返金系は除外）
        - 電話番号などのPIIは一切 Order オブジェクトに入れない
    """
    logger.info("竹中さん発注表CSVを読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.TAKENAKA_ENCODING, dtype=str)

    required = [
        config.TAKENAKA_COL_DATE,
        config.TAKENAKA_COL_PRODUCT,
        config.TAKENAKA_COL_STATUS,
        config.TAKENAKA_COL_UNIT_PRICE_A,
        config.TAKENAKA_COL_QUANTITY_A,
        config.TAKENAKA_COL_UNIT_PRICE_B,
        config.TAKENAKA_COL_QUANTITY_B,
        config.TAKENAKA_COL_TOTAL,
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"竹中さん発注表CSVに必要な列がありません: {missing}")

    orders: list[Order] = []
    skipped_status = 0
    for idx, row in df.iterrows():
        # ステータスフィルタ（発送済み系のみ採用）
        status = str(row[config.TAKENAKA_COL_STATUS]).strip()
        if status not in config.TAKENAKA_VALID_STATUSES:
            skipped_status += 1
            continue

        try:
            order = _build_takenaka_order(idx, row)
        except ValueError as exc:
            logger.warning("竹中さん発注表 %s行目をスキップ: %s", idx, exc)
            continue
        orders.append(order)

    logger.info(
        "竹中さん発注表: %d件 採用（ステータス除外: %d件）",
        len(orders),
        skipped_status,
    )
    return orders


def _build_takenaka_order(idx: int, row: pd.Series) -> Order:
    """竹中さん発注表の1行から Order を組み立てる（50行制約維持のため分離）。"""
    # A仕入れ値・A個数は必須
    unit_price_a = _to_int_amount(row[config.TAKENAKA_COL_UNIT_PRICE_A])
    quantity_a = int(_to_int_amount(row[config.TAKENAKA_COL_QUANTITY_A]))

    # B仕入れ値・B個数は任意（空欄なら0）
    unit_price_b = _safe_int_amount_or_zero(row[config.TAKENAKA_COL_UNIT_PRICE_B])
    quantity_b = _safe_int_amount_or_zero(row[config.TAKENAKA_COL_QUANTITY_B])

    return Order(
        row_index=int(idx),
        ordered_at=_to_date_with_year(row[config.TAKENAKA_COL_DATE], config.DEFAULT_YEAR),
        product=str(row[config.TAKENAKA_COL_PRODUCT]).strip(),
        unit_price_a=unit_price_a,
        quantity_a=quantity_a,
        total=_to_int_amount(row[config.TAKENAKA_COL_TOTAL]),
        unit_price_b=unit_price_b,
        quantity_b=quantity_b,
    )


def _safe_int_amount_or_zero(value: object) -> int:
    """空欄・パース不能なら0を返す（B仕入れ値・B個数の省略対応）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    text = str(value).strip()
    if text == "":
        return 0
    try:
        return _to_int_amount(text)
    except ValueError:
        return 0


# ============================================================
# JCB手動コピペ版 明細（山中さん形式・4行1ブロック）
# ============================================================
def load_jcb_manual_csv(path: Path) -> list[Transaction]:
    """
    JCB手動コピペ版（山中さん形式）の明細ファイルを読み込んで Transaction のリストを返す。

    ファイル構造:
        1行目: 日付（YYYY/MM/DD）
        2行目: 店名
        3行目: 支払区分（"1回払い" 等）
        4行目: 金額（"28,539円" 形式）
        5行目: 空行（ブロック区切り）

    CSV形式ではなく、4行1ブロック＋空行区切りのプレーンテキスト。
    """
    logger.info("JCB手動コピペ明細を読み込みます: %s", path)
    with open(path, "r", encoding=config.JCB_MANUAL_ENCODING) as f:
        raw_lines = [line.rstrip() for line in f]

    transactions: list[Transaction] = []
    block: list[str] = []
    block_count = 0
    skipped_incomplete = 0

    for line in raw_lines:
        if line:
            block.append(line)
            if len(block) == config.JCB_MANUAL_BLOCK_SIZE:
                tx = _try_parse_jcb_block(block_count, block)
                if tx is not None:
                    transactions.append(tx)
                block_count += 1
                block = []
        else:
            # 空行: 不完全ブロックは破棄して警告
            if 0 < len(block) < config.JCB_MANUAL_BLOCK_SIZE:
                logger.warning("JCB明細: 不完全ブロック(%d行)をスキップ", len(block))
                skipped_incomplete += 1
                block = []
            # 空行だけが続く場合は何もしない

    # ファイル末尾の処理（最後のブロックに空行が無い場合）
    if len(block) == config.JCB_MANUAL_BLOCK_SIZE:
        tx = _try_parse_jcb_block(block_count, block)
        if tx is not None:
            transactions.append(tx)
    elif 0 < len(block):
        logger.warning("JCB明細: ファイル末尾の不完全ブロックをスキップ")
        skipped_incomplete += 1

    logger.info(
        "JCB手動コピペ明細: %d件を読み込みました（不完全ブロック: %d件）",
        len(transactions),
        skipped_incomplete,
    )
    return transactions


def _try_parse_jcb_block(block_index: int, block: list[str]) -> Transaction | None:
    """JCB明細の1ブロック（4行）を Transaction に変換する。失敗時は None。"""
    try:
        return Transaction(
            row_index=block_index,
            used_at=_to_date(block[0]),
            store=block[1],
            status=block[2],  # "1回払い" 等をそのまま保存
            amount=_to_int_amount(block[3]),
        )
    except ValueError as exc:
        logger.warning("JCB明細ブロック%d をスキップ: %s", block_index, exc)
        return None


# ============================================================
# Amazon注文履歴を明細側(Transaction)として読み込むアダプタ
#   期間検証用: 竹中さん発注表と期間が被るデータで動作確認するため
# ============================================================
def load_amazon_history_as_statements(path: Path) -> list[Transaction]:
    """
    Amazon注文履歴CSV（昨日までの orders_*.csv 形式）を、
    明細側の Transaction として読み込む。

    config.AMAZON_STATEMENT_CARD_FILTERS でカード絞り込み、
    config.AMAZON_STATEMENT_VALID_STATUSES でステータス絞り込み。
    """
    logger.info("Amazon履歴を明細として読み込みます: %s", path)
    df = pd.read_csv(path, encoding=config.ORDER_ENCODING, dtype=str)

    required = [
        config.ORDER_COL_DATE,
        config.ORDER_COL_TOTAL,
        config.ORDER_COL_PRODUCT,
    ]
    if config.AMAZON_STATEMENT_CARD_FILTERS:
        required.append(config.ORDER_COL_CARD)
    if config.AMAZON_STATEMENT_VALID_STATUSES:
        required.append(config.ORDER_COL_STATUS)

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Amazon履歴CSVに必要な列がありません: {missing}")

    transactions: list[Transaction] = []
    skipped_filtered = 0
    for idx, row in df.iterrows():
        if not _should_keep_amazon_statement_row(row):
            skipped_filtered += 1
            continue

        try:
            tx = Transaction(
                row_index=int(idx),
                used_at=_to_date(row[config.ORDER_COL_DATE]),
                amount=_to_int_amount(row[config.ORDER_COL_TOTAL]),
                store=str(row[config.ORDER_COL_PRODUCT]).strip(),
                status="確定",  # Amazon履歴は終了ステータスのみ残る運用
            )
        except ValueError as exc:
            logger.warning("Amazon履歴 %s行目をスキップ: %s", idx, exc)
            continue
        transactions.append(tx)

    logger.info(
        "Amazon履歴(明細): %d件採用（フィルタ除外: %d件）",
        len(transactions),
        skipped_filtered,
    )
    return transactions


def load_combined_statements(ignored_path: Path) -> list[Transaction]:
    """
    バク楽CSVとJCB手動コピペ版を両方読み込んで、単一のTransactionリストに結合する。

    期間が重なる部分は両方から取り込まれるが、カードが異なるため重複しない。
    引数のパスは無視し、config.INPUT_DIR 配下から自動検出する。

    Args:
        ignored_path: 既存のディスパッチ互換のため受け取るが使用しない。

    Returns:
        バク楽とJCBを結合した Transaction のリスト。
    """
    logger.info("統合明細モード: バク楽 + JCB手動コピペ を読み込みます")

    bakuraku_files = sorted(config.INPUT_DIR.glob("bakuraku_*.csv"))
    jcb_files = sorted(config.INPUT_DIR.glob("jcb_manual_*.csv"))

    if not bakuraku_files and not jcb_files:
        raise FileNotFoundError(
            f"{config.INPUT_DIR} に bakuraku_*.csv / jcb_manual_*.csv の"
            "いずれも見つかりません。"
        )

    combined: list[Transaction] = []
    bakuraku_count = 0
    jcb_count = 0

    for path in bakuraku_files:
        txs = load_bakuraku_csv(path)
        combined.extend(txs)
        bakuraku_count += len(txs)
    for path in jcb_files:
        txs = load_jcb_manual_csv(path)
        combined.extend(txs)
        jcb_count += len(txs)

    # 結合後の row_index を振り直し（1対1マッチで同IDが被らないように）
    for new_idx, tx in enumerate(combined):
        tx.row_index = new_idx

    logger.info(
        "統合明細: バク楽 %d件 + JCB %d件 = 計 %d件",
        bakuraku_count,
        jcb_count,
        len(combined),
    )
    return combined


def _should_keep_amazon_statement_row(row: pd.Series) -> bool:
    """Amazon履歴を明細として使う時のフィルタ判定。"""
    if config.AMAZON_STATEMENT_CARD_FILTERS:
        card_value = (
            str(row[config.ORDER_COL_CARD])
            if row[config.ORDER_COL_CARD] is not None
            else ""
        )
        if not any(c in card_value for c in config.AMAZON_STATEMENT_CARD_FILTERS):
            return False

    if config.AMAZON_STATEMENT_VALID_STATUSES:
        status_value = (
            str(row[config.ORDER_COL_STATUS]).strip()
            if row[config.ORDER_COL_STATUS] is not None
            else ""
        )
        if status_value not in config.AMAZON_STATEMENT_VALID_STATUSES:
            return False

    return True
