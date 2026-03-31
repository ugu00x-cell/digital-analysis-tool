"""
Cpk管理DB 実践クエリ10問
SQLiteで品質管理データを分析する練習用スクリプト
各クエリを順番に実行し、結果を表示する
"""

import logging
import sqlite3
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

# ─── 10問のクエリ定義 ────────────────────────────────────
QUERIES: list[dict] = [
    # ── Q1: 基本SELECT ──
    {
        "title": "Q1【基本】全製品の一覧を取得",
        "hint": "SELECT * で全カラムを取得する基本形",
        "sql": """
SELECT *
FROM products;
"""
    },

    # ── Q2: JOIN ──
    {
        "title": "Q2【JOIN】検査項目と製品名を結合して一覧表示",
        "hint": "JOINで2テーブルを結合し、公差幅も計算する",
        "sql": """
SELECT
    p.product_name    AS 製品名,
    i.item_name       AS 検査項目,
    i.nominal         AS 基準値,
    i.lower_spec      AS LSL,
    i.upper_spec      AS USL,
    ROUND(i.upper_spec - i.lower_spec, 3) AS 公差幅
FROM inspection_items i
JOIN products p ON i.product_id = p.product_id
ORDER BY p.product_id, i.item_id;
"""
    },

    # ── Q3: 集約 ──
    {
        "title": "Q3【GROUP BY】検査項目ごとの測定件数・平均・標準偏差",
        "hint": "AVG, COUNT, 標準偏差はSQLiteではカスタム計算が必要",
        "sql": """
SELECT
    i.item_name                           AS 検査項目,
    COUNT(*)                              AS 測定件数,
    ROUND(AVG(m.measured_value), 4)       AS 平均値,
    ROUND(MIN(m.measured_value), 4)       AS 最小値,
    ROUND(MAX(m.measured_value), 4)       AS 最大値
FROM measurements m
JOIN inspection_items i ON m.item_id = i.item_id
GROUP BY i.item_name
ORDER BY i.item_name;
"""
    },

    # ── Q4: NG率 ──
    {
        "title": "Q4【条件集約】検査項目ごとのNG率を算出",
        "hint": "SUM(CASE WHEN ...)でNG件数を数えてNG率を計算",
        "sql": """
SELECT
    i.item_name                                       AS 検査項目,
    COUNT(*)                                          AS 総数,
    SUM(CASE WHEN m.is_ng = 1 THEN 1 ELSE 0 END)    AS NG件数,
    ROUND(
        100.0 * SUM(CASE WHEN m.is_ng = 1 THEN 1 ELSE 0 END) / COUNT(*),
        2
    )                                                 AS NG率_pct
FROM measurements m
JOIN inspection_items i ON m.item_id = i.item_id
GROUP BY i.item_name
ORDER BY NG率_pct DESC;
"""
    },

    # ── Q5: Cp/Cpk計算 ──
    {
        "title": "Q5【応用】検査項目ごとのCp・Cpkを計算",
        "hint": "Cp = (USL-LSL)/(6σ), Cpk = min((USL-μ)/3σ, (μ-LSL)/3σ)",
        "sql": """
WITH stats AS (
    SELECT
        i.item_id,
        i.item_name,
        i.upper_spec                        AS usl,
        i.lower_spec                        AS lsl,
        AVG(m.measured_value)               AS mu,
        -- SQLiteにSTDDEVがないので手計算
        SQRT(
            AVG(m.measured_value * m.measured_value)
            - AVG(m.measured_value) * AVG(m.measured_value)
        )                                   AS sigma
    FROM measurements m
    JOIN inspection_items i ON m.item_id = i.item_id
    GROUP BY i.item_id
)
SELECT
    item_name                                              AS 検査項目,
    ROUND(mu, 4)                                           AS 平均値,
    ROUND(sigma, 5)                                        AS 標準偏差,
    ROUND((usl - lsl) / (6 * sigma), 3)                   AS Cp,
    ROUND(
        MIN(
            (usl - mu) / (3 * sigma),
            (mu - lsl) / (3 * sigma)
        ), 3
    )                                                      AS Cpk,
    CASE
        WHEN MIN((usl - mu) / (3 * sigma), (mu - lsl) / (3 * sigma)) >= 1.33
        THEN '◎ 良好'
        WHEN MIN((usl - mu) / (3 * sigma), (mu - lsl) / (3 * sigma)) >= 1.00
        THEN '○ 許容'
        ELSE '× 要改善'
    END                                                    AS 判定
FROM stats
ORDER BY Cpk ASC;
"""
    },

    # ── Q6: ラインごと比較 ──
    {
        "title": "Q6【GROUP BY応用】ラインごとのNG率を比較",
        "hint": "どのラインで品質問題が多いか特定する",
        "sql": """
SELECT
    l.line_name                                        AS ライン,
    l.location                                         AS 拠点,
    COUNT(*)                                           AS 測定件数,
    SUM(m.is_ng)                                       AS NG件数,
    ROUND(100.0 * SUM(m.is_ng) / COUNT(*), 2)         AS NG率_pct
FROM measurements m
JOIN lines l ON m.line_id = l.line_id
GROUP BY l.line_id
ORDER BY NG率_pct DESC;
"""
    },

    # ── Q7: 月別トレンド ──
    {
        "title": "Q7【日付関数】月ごとのNG率トレンド",
        "hint": "strftime('%Y-%m', ...)で月単位に集約する",
        "sql": """
SELECT
    strftime('%Y-%m', m.measured_at)                    AS 年月,
    COUNT(*)                                           AS 測定件数,
    SUM(m.is_ng)                                       AS NG件数,
    ROUND(100.0 * SUM(m.is_ng) / COUNT(*), 2)         AS NG率_pct
FROM measurements m
GROUP BY strftime('%Y-%m', m.measured_at)
ORDER BY 年月;
"""
    },

    # ── Q8: 検査員パフォーマンス ──
    {
        "title": "Q8【3テーブルJOIN】検査員ごとの担当件数とNG検出率",
        "hint": "検査員・ライン・測定の3テーブルを結合",
        "sql": """
SELECT
    ins.inspector_name                                 AS 検査員,
    l.line_name                                        AS 所属ライン,
    COUNT(*)                                           AS 担当件数,
    SUM(m.is_ng)                                       AS NG検出数,
    ROUND(100.0 * SUM(m.is_ng) / COUNT(*), 2)         AS NG率_pct
FROM measurements m
JOIN inspectors ins ON m.inspector_id = ins.inspector_id
JOIN lines l ON ins.line_id = l.line_id
GROUP BY ins.inspector_id
ORDER BY 担当件数 DESC;
"""
    },

    # ── Q9: サブクエリ ──
    {
        "title": "Q9【サブクエリ】Cpkが1.33未満（要改善）の項目に絞って測定値を確認",
        "hint": "WITH句のCpk計算結果をサブクエリで使う",
        "sql": """
WITH cpk_calc AS (
    SELECT
        i.item_id,
        i.item_name,
        i.upper_spec AS usl,
        i.lower_spec AS lsl,
        AVG(m.measured_value) AS mu,
        SQRT(
            AVG(m.measured_value * m.measured_value)
            - AVG(m.measured_value) * AVG(m.measured_value)
        ) AS sigma
    FROM measurements m
    JOIN inspection_items i ON m.item_id = i.item_id
    GROUP BY i.item_id
)
SELECT
    item_name  AS 検査項目,
    ROUND((usl - lsl) / (6 * sigma), 3) AS Cp,
    ROUND(MIN((usl - mu) / (3 * sigma), (mu - lsl) / (3 * sigma)), 3) AS Cpk,
    ROUND(mu, 4) AS 平均値,
    ROUND(sigma, 5) AS 標準偏差
FROM cpk_calc
WHERE MIN((usl - mu) / (3 * sigma), (mu - lsl) / (3 * sigma)) < 1.33
ORDER BY Cpk ASC;
"""
    },

    # ── Q10: 総合レポート ──
    {
        "title": "Q10【総合】製品×検査項目の品質サマリレポート",
        "hint": "製品・検査項目・Cpk・NG率を1つのレポートにまとめる",
        "sql": """
WITH item_stats AS (
    SELECT
        i.item_id,
        i.product_id,
        i.item_name,
        i.upper_spec AS usl,
        i.lower_spec AS lsl,
        COUNT(*)                              AS n,
        AVG(m.measured_value)                 AS mu,
        SQRT(
            AVG(m.measured_value * m.measured_value)
            - AVG(m.measured_value) * AVG(m.measured_value)
        )                                     AS sigma,
        SUM(m.is_ng)                          AS ng_count
    FROM measurements m
    JOIN inspection_items i ON m.item_id = i.item_id
    GROUP BY i.item_id
)
SELECT
    p.product_name                                           AS 製品名,
    s.item_name                                              AS 検査項目,
    s.n                                                      AS 測定数,
    ROUND(s.mu, 4)                                           AS 平均値,
    ROUND(s.sigma, 5)                                        AS σ,
    ROUND((s.usl - s.lsl) / (6 * s.sigma), 3)               AS Cp,
    ROUND(
        MIN(
            (s.usl - s.mu) / (3 * s.sigma),
            (s.mu - s.lsl) / (3 * s.sigma)
        ), 3
    )                                                        AS Cpk,
    s.ng_count                                               AS NG件数,
    ROUND(100.0 * s.ng_count / s.n, 2)                      AS NG率,
    CASE
        WHEN MIN((s.usl - s.mu) / (3 * s.sigma), (s.mu - s.lsl) / (3 * s.sigma)) >= 1.33
        THEN '◎'
        WHEN MIN((s.usl - s.mu) / (3 * s.sigma), (s.mu - s.lsl) / (3 * s.sigma)) >= 1.00
        THEN '○'
        ELSE '×'
    END                                                      AS 判定
FROM item_stats s
JOIN products p ON s.product_id = p.product_id
ORDER BY p.product_id, s.item_id;
"""
    },
]


def run_query(conn: sqlite3.Connection, q: dict, index: int) -> None:
    """1つのクエリを実行して結果を表示する"""
    print(f"\n{'='*70}")
    print(f"  {q['title']}")
    print(f"  ヒント: {q['hint']}")
    print(f"{'='*70}")
    print(f"SQL:\n{q['sql'].strip()}")
    print(f"{'-'*70}")

    cursor = conn.execute(q["sql"])
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    # ヘッダー表示
    header = " | ".join(f"{c:>12}" for c in cols)
    print(header)
    print("-" * len(header))

    # データ表示（最大20行）
    for row in rows[:20]:
        print(" | ".join(f"{str(v):>12}" for v in row))

    if len(rows) > 20:
        print(f"  ... 他 {len(rows) - 20} 件")

    print(f"\n  → {len(rows)} 件取得\n")


def main() -> None:
    """全クエリを順番に実行する"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for i, q in enumerate(QUERIES):
            run_query(conn, q, i + 1)
    finally:
        conn.close()
    logger.info("全10クエリ実行完了")


if __name__ == "__main__":
    main()
