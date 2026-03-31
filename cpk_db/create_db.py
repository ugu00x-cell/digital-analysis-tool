"""
Cpk管理サンプルDB作成スクリプト
製造業の完成品検査データを模したSQLiteデータベースを構築する
"""

import logging
import sqlite3
import random
import math
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "cpk_sample.db"

# テーブル定義
SCHEMA_SQL = """
-- 製品マスタ
CREATE TABLE IF NOT EXISTS products (
    product_id   TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL
);

-- 検査項目マスタ（公差付き）
CREATE TABLE IF NOT EXISTS inspection_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   TEXT NOT NULL,
    item_name    TEXT NOT NULL,
    nominal      REAL NOT NULL,       -- 基準値
    upper_spec   REAL NOT NULL,       -- 上限規格（USL）
    lower_spec   REAL NOT NULL,       -- 下限規格（LSL）
    unit         TEXT DEFAULT 'mm',
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- 検査ライン（工程）マスタ
CREATE TABLE IF NOT EXISTS lines (
    line_id   TEXT PRIMARY KEY,
    line_name TEXT NOT NULL,
    location  TEXT NOT NULL
);

-- 検査員マスタ
CREATE TABLE IF NOT EXISTS inspectors (
    inspector_id   TEXT PRIMARY KEY,
    inspector_name TEXT NOT NULL,
    line_id        TEXT NOT NULL,
    FOREIGN KEY (line_id) REFERENCES lines(line_id)
);

-- 測定データ（メインテーブル）
CREATE TABLE IF NOT EXISTS measurements (
    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL,
    line_id        TEXT NOT NULL,
    inspector_id   TEXT NOT NULL,
    lot_number     TEXT NOT NULL,
    measured_value REAL NOT NULL,
    measured_at    TEXT NOT NULL,       -- 'YYYY-MM-DD HH:MM:SS'
    is_ng          INTEGER DEFAULT 0,  -- 0=OK, 1=NG
    FOREIGN KEY (item_id) REFERENCES inspection_items(item_id),
    FOREIGN KEY (line_id) REFERENCES lines(line_id),
    FOREIGN KEY (inspector_id) REFERENCES inspectors(inspector_id)
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """テーブルを作成する"""
    conn.executescript(SCHEMA_SQL)
    logger.info("スキーマ作成完了")


def insert_master_data(conn: sqlite3.Connection) -> None:
    """マスタデータを投入する"""
    # 製品マスタ
    products = [
        ("PRD-001", "スピンドルシャフト", "主軸部品"),
        ("PRD-002", "ボールねじナット", "送り機構"),
        ("PRD-003", "リニアガイドブロック", "案内機構"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO products VALUES (?, ?, ?)", products
    )

    # 検査項目マスタ（各製品に複数の検査寸法）
    items = [
        # スピンドルシャフト
        ("PRD-001", "外径φ40", 40.000, 40.015, 39.985, "mm"),
        ("PRD-001", "全長200", 200.00, 200.05, 199.95, "mm"),
        ("PRD-001", "真円度",  0.000,  0.005, -0.005, "mm"),
        # ボールねじナット
        ("PRD-002", "内径φ25", 25.000, 25.010, 24.990, "mm"),
        ("PRD-002", "溝深さ",   3.500,  3.520,  3.480, "mm"),
        # リニアガイドブロック
        ("PRD-003", "幅寸法30",  30.000, 30.020, 29.980, "mm"),
        ("PRD-003", "高さ寸法15", 15.000, 15.015, 14.985, "mm"),
        ("PRD-003", "平面度",    0.000,  0.003, -0.003, "mm"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO inspection_items "
        "(product_id, item_name, nominal, upper_spec, lower_spec, unit) "
        "VALUES (?, ?, ?, ?, ?, ?)", items
    )

    # 検査ライン
    lines = [
        ("LINE-A", "第1検査ライン", "本社工場"),
        ("LINE-B", "第2検査ライン", "本社工場"),
        ("LINE-C", "第3検査ライン", "厚木工場"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO lines VALUES (?, ?, ?)", lines
    )

    # 検査員
    inspectors = [
        ("INS-01", "田中", "LINE-A"),
        ("INS-02", "鈴木", "LINE-A"),
        ("INS-03", "佐藤", "LINE-B"),
        ("INS-04", "山本", "LINE-B"),
        ("INS-05", "中村", "LINE-C"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO inspectors VALUES (?, ?, ?)", inspectors
    )
    conn.commit()
    logger.info("マスタデータ投入完了")


def generate_measurements(conn: sqlite3.Connection, n_per_item: int = 500) -> None:
    """測定データを生成する（正規分布ベース＋一部NG品を含む）"""
    random.seed(42)

    # 検査項目を取得
    items = conn.execute(
        "SELECT item_id, nominal, upper_spec, lower_spec FROM inspection_items"
    ).fetchall()

    line_ids = ["LINE-A", "LINE-B", "LINE-C"]
    inspector_map = {
        "LINE-A": ["INS-01", "INS-02"],
        "LINE-B": ["INS-03", "INS-04"],
        "LINE-C": ["INS-05"],
    }

    rows = []
    for item_id, nominal, usl, lsl in items:
        tolerance = usl - lsl
        # 標準偏差をアイテムごとに変える（Cpkのバラつきを演出）
        sigma = tolerance / random.uniform(4.0, 8.0)
        # 平均値を少しずらす（偏りのある工程を再現）
        mean_shift = random.uniform(-tolerance * 0.1, tolerance * 0.1)

        for i in range(n_per_item):
            # 測定値を正規分布で生成
            value = random.gauss(nominal + mean_shift, sigma)
            value = round(value, 4)

            # NG判定
            is_ng = 1 if (value > usl or value < lsl) else 0

            # ランダムにライン・検査員・日時を割り当て
            line = random.choice(line_ids)
            inspector = random.choice(inspector_map[line])
            lot = f"LOT-2026{random.randint(1, 12):02d}-{random.randint(1, 30):02d}-{random.randint(1, 99):02d}"

            # 2026年1月〜3月のランダム日時
            month = random.randint(1, 3)
            day = random.randint(1, 28)
            hour = random.randint(8, 17)
            minute = random.randint(0, 59)
            dt = f"2026-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"

            rows.append((item_id, line, inspector, lot, value, dt, is_ng))

    conn.executemany(
        "INSERT INTO measurements "
        "(item_id, line_id, inspector_id, lot_number, measured_value, measured_at, is_ng) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)", rows
    )
    conn.commit()
    logger.info(f"測定データ {len(rows)} 件投入完了")


def verify_data(conn: sqlite3.Connection) -> None:
    """データ件数を確認する"""
    tables = ["products", "inspection_items", "lines", "inspectors", "measurements"]
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info(f"  {table}: {count} 件")


def main() -> None:
    """メイン処理"""
    # 既存DBがあれば削除して作り直す
    if DB_PATH.exists():
        DB_PATH.unlink()
        logger.info("既存DB削除")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        create_schema(conn)
        insert_master_data(conn)
        generate_measurements(conn, n_per_item=500)
        verify_data(conn)
        logger.info(f"DB作成完了: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
