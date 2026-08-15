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
DATE_TOLERANCE_DAYS: int = 3

# 対称マッチング（±）にしたい場合は True にする
# True にすると、|利用日 - 発注日| <= DATE_TOLERANCE_DAYS で判定
USE_SYMMETRIC_DATE_MATCH: bool = True

# 金額の許容誤差（円）
# 完全一致にしたい場合は 0 のまま
AMOUNT_TOLERANCE: int = 0


# --- Stage 3: マイナス差許容マッチング ---
# 完全一致できなかった分について、マイナス差（JCB < 発注表）のみ許容してマッチを試みる
# 業務プロセス上「未修正残（クーポン未反映等で発注表より少ない請求）は許容範囲」のため
#
# プラス差（JCB > 発注表）は「プロセス上ありえない＝担当ミス」なので絶対に許容しない
ENABLE_NEGATIVE_DIFF_TOLERANCE: bool = False  # クライアント要望によりまだ有効化しない

# 許容するマイナス差の範囲（円）
# 例: (-100, -1) → -100円 ≤ (JCB - 発注表) ≤ -1円 のときに消込
NEGATIVE_DIFF_TOLERANCE_RANGE: tuple[int, int] = (-100, -1)


# --- Stage 4: ペア候補マッチング ---
# Stage 1〜3 で消込できなかった「要確認JCB」と「グレー発注」を、
# 同日±数日で金額差がある「ペア候補」として紐付ける
# 完全一致ではないので消込扱いではないが、業務側の確認工数を大幅削減
ENABLE_PAIR_MATCHING: bool = True

# ペア候補とみなす最大差額の絶対値（円）
# これを超える差は「無関係な別取引」と判断してペアにしない
PAIR_MAX_ABS_DIFF: int = 500


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
ORDER_CARD_FILTERS: tuple[str, ...] = ("4521",)  # ローカル専用（コミットしない）

# 注文状況列と、有効とみなすステータス
# 空タプル () にするとフィルタなし
ORDER_COL_STATUS: str = "注文状況"
ORDER_VALID_STATUSES: tuple[str, ...] = ("終了",)


# ============================================================
# 新フォーマット（竹中さん発注表 × JCB手動コピペ）用の設定
# ============================================================

# --- 入力フォーマットの切替 ---
# 発注表フォーマット:
#   "amazon_orders"  ... Amazon注文履歴CSV (昨日までの形式)
#   "takenaka_korea" ... 竹中さん発注表・韓国スプシ形式（A/B仕入れ対応）
ORDER_FORMAT: str = "takenaka_korea"

# クレカ明細フォーマット:
#   "bakuraku"           ... バク楽CSV（昨日までの形式）
#   "jcb_manual"         ... JCB手動コピペ版（4行1ブロック、本番運用）
#   "amazon_history"     ... Amazon注文履歴CSVを明細側として使う（期間重複検証用）
#   "bakuraku_and_jcb"   ... バク楽とJCB手動コピペを両方読み込んで結合（統合消込）
CREDIT_STATEMENT_FORMAT: str = "bakuraku_and_jcb"


# --- 日付の年補完（「3/2」のような年抜け日付を日付化する時の既定年） ---
DEFAULT_YEAR: int = 2026


# --- 竹中さん発注表（韓国）用の設定 ---
TAKENAKA_ENCODING: str = "utf-8-sig"
TAKENAKA_COL_DATE: str = "注文日"
TAKENAKA_COL_PRODUCT: str = "商品名"
TAKENAKA_COL_STATUS: str = "ステータス"
TAKENAKA_COL_UNIT_PRICE_A: str = "A仕入れ値"
TAKENAKA_COL_QUANTITY_A: str = "A個数"
TAKENAKA_COL_UNIT_PRICE_B: str = "B仕入れ値"
TAKENAKA_COL_QUANTITY_B: str = "B個数"
TAKENAKA_COL_TOTAL: str = "仕入れ総額"

# 発送済み・マッチ対象としてみなすステータスのみ採用
# それ以外（キャンセル系・返金系など）は全てスキップ
TAKENAKA_VALID_STATUSES: tuple[str, ...] = (
    "スマート配送 発送済み",
    "HANIRO 発送済み",
)


# --- JCB手動コピペ版 明細 用の設定 ---
# ファイルは 4行1ブロック＋空行区切りのプレーンテキスト
# 行1: 日付 / 行2: 店名 / 行3: 支払区分 / 行4: 金額
JCB_MANUAL_ENCODING: str = "utf-8-sig"
JCB_MANUAL_BLOCK_SIZE: int = 4


# --- Amazon履歴を明細として使う時の設定（期間検証用） ---
# 発注表がJCBカード(1112)の注文を対象にしている場合、
# Amazon履歴側も同じカードでフィルタする
AMAZON_STATEMENT_CARD_FILTERS: tuple[str, ...] = ("1112",)  # ローカル専用（コミットしない）
# Amazon履歴の「注文状況」列で、明細として採用する値（≒決済が発生している状態）
AMAZON_STATEMENT_VALID_STATUSES: tuple[str, ...] = ("終了",)


# --- 出力設定 ---
OUTPUT_ENCODING: str = "utf-8-sig"

# 出力ファイル名のプレフィックス（末尾に日付が付く）
OUTPUT_FILENAME_PREFIX: str = "消込結果_"


# --- ステータスラベル（出力CSVに使う文言） ---
STATUS_MATCHED: str = "✅ 消込済み"
STATUS_MATCHED_RECALC: str = "✅⚠️ 消込済み（手打ちミス疑い）"
STATUS_MATCHED_TOLERANCE: str = "✅⚠️ 消込済み（マイナス差許容・未修正残）"
STATUS_PAIR_CANDIDATE: str = "📎 ペア候補（差額あり・要確認）"
STATUS_SUSPICIOUS: str = "🚨 要確認（不正疑い）"
STATUS_GRAY: str = "⚠️ グレー"
