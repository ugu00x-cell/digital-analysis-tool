"""
消込ツールの設定値をまとめたモジュール。

後から変更する可能性のある値は、全てここに集約してあります。
ロジックを触らずに、このファイルだけを編集すれば挙動を変えられます。
"""
from pathlib import Path


# --- パス設定 ---
# プロジェクトのルート（card_reconciliation/ ディレクトリ）
BASE_DIR: Path = Path(__file__).resolve().parent

# 入力CSVを置くディレクトリ
INPUT_DIR: Path = BASE_DIR / "input"

# 出力CSVを書き出すディレクトリ
OUTPUT_DIR: Path = BASE_DIR / "output"


# --- マッチング設定 ---
# 日付の許容範囲（日数）
# バク楽の利用日が、発注日 〜 発注日 + DATE_TOLERANCE_DAYS の範囲内ならOK
# ※発注→請求のタイムラグが前提なので、非対称（利用日が発注日より前はNG）
DATE_TOLERANCE_DAYS: int = 2

# 対称マッチング（±）にしたい場合は True にする
# True にすると、|利用日 - 発注日| <= DATE_TOLERANCE_DAYS で判定
USE_SYMMETRIC_DATE_MATCH: bool = True

# 金額の許容誤差（円）
# 完全一致にしたい場合は 0 のまま
AMOUNT_TOLERANCE: int = 0


# --- バク楽CSV設定 ---
BAKURAKU_ENCODING: str = "utf-8-sig"

# バク楽CSVで「確定」扱いとみなすステータス文字列
# これ以外のステータス（返品など）は全てスキップされる
BAKURAKU_VALID_STATUS: str = "確定"

# バク楽CSVの列名
BAKURAKU_COL_DATETIME: str = "利用日時"
BAKURAKU_COL_AMOUNT: str = "金額"
BAKURAKU_COL_STORE: str = "当初取引内容"
BAKURAKU_COL_STATUS: str = "ステータス"


# --- 発注表CSV設定 ---
ORDER_ENCODING: str = "utf-8-sig"

# 発注表CSVの列名（Amazon注文履歴CSVの実際の列名に合わせてある）
ORDER_COL_DATE: str = "注文日"
ORDER_COL_PRODUCT: str = "商品名"
ORDER_COL_UNIT_PRICE: str = "商品の価格（税込）"
ORDER_COL_QUANTITY: str = "注文の数量"
ORDER_COL_TOTAL: str = "注文の合計（税込）"

# --- 発注表の絞り込み設定 ---
# カード番号（下4桁）列と、フィルタする値のタプル（複数カード対応）
# 空タプル () にするとフィルタなし（全カード対象）
# Amazon CSVでは '="1234"' のように = とダブルクォートで囲まれているので、
# 値に各フィルタ文字列が含まれているかで判定する（部分一致・OR条件）
# 使い方:
#   対象カード下4桁を指定して絞り込む。利用者側で編集してください。
#   例: ("1234",)         … 1234カードのみ
#   例: ("1234", "5678")  … 1234 と 5678 の両方を対象
#   デフォルトは空タプル（フィルタ無効・全件採用）
ORDER_COL_CARD: str = "クレジットカード番号（下4桁）"
ORDER_CARD_FILTERS: tuple[str, ...] = ()

# 注文状況列と、有効とみなすステータス
# 空タプル () にするとフィルタなし
ORDER_COL_STATUS: str = "注文状況"
ORDER_VALID_STATUSES: tuple[str, ...] = ("終了",)


# --- 出力設定 ---
OUTPUT_ENCODING: str = "utf-8-sig"

# 出力ファイル名のプレフィックス（末尾に日付が付く）
OUTPUT_FILENAME_PREFIX: str = "消込結果_"


# --- ステータスラベル（出力CSVに使う文言） ---
STATUS_MATCHED: str = "✅ 消込済み"
STATUS_MATCHED_RECALC: str = "✅⚠️ 消込済み（手打ちミス疑い）"
STATUS_SUSPICIOUS: str = "🚨 要確認（不正疑い）"
STATUS_GRAY: str = "⚠️ グレー"
