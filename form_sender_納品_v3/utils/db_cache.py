"""DB操作 - フォーム構造キャッシュの管理（学習用）

送信成功/失敗の結果をドメイン単位でキャッシュし、
次回以降のフォーム解析精度を自動で改善する。
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from utils.db import _conn

logger = logging.getLogger(__name__)

# 信頼性判定の閾値
DEFAULT_MIN_SUCCESS = 3
DEFAULT_MAX_FAIL_RATIO = 0.3


def get_form_cache(domain: str) -> Optional[dict]:
    """ドメインのフォーム構造キャッシュを取得する

    Args:
        domain: ドメイン名（例: www.example.com）

    Returns:
        キャッシュデータ辞書、未キャッシュならNone
    """
    conn = _conn()
    row = conn.execute(
        "SELECT form_url, field_mapping, success_count, "
        "fail_count, last_status FROM form_cache WHERE domain = ?",
        (domain,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "form_url": row["form_url"],
        "field_mapping": json.loads(row["field_mapping"]),
        "success_count": row["success_count"],
        "fail_count": row["fail_count"],
        "last_status": row["last_status"],
    }


def save_form_cache(
    domain: str, form_url: str, mapping: dict, success: bool,
    html_signature: str = "",
) -> None:
    """フォーム構造をキャッシュに保存・更新する

    成功時のみmappingを上書きし、失敗時はカウントのみ加算する。
    これにより「最も良いマッピング」が常に保持される。

    Args:
        domain: ドメイン名
        form_url: フォームページのURL
        mapping: フィールドマッピング辞書
        success: 送信成功したかどうか
        html_signature: フォームのHTML署名（クロスサイト学習用）
    """
    conn = _conn()
    mapping_json = json.dumps(mapping, ensure_ascii=False)
    now = datetime.now().isoformat()
    status = "success" if success else "fail"

    if success:
        # 成功時：マッピングを更新 + success_count加算
        conn.execute(
            """INSERT INTO form_cache
            (domain, form_url, field_mapping, success_count, fail_count,
             last_status, html_signature, updated_at)
            VALUES (?, ?, ?, 1, 0, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                field_mapping = excluded.field_mapping,
                form_url = excluded.form_url,
                success_count = success_count + 1,
                last_status = excluded.last_status,
                html_signature = excluded.html_signature,
                updated_at = excluded.updated_at""",
            (domain, form_url, mapping_json, status, html_signature, now),
        )
    else:
        # 失敗時：マッピングは変えずfail_count加算
        conn.execute(
            """INSERT INTO form_cache
            (domain, form_url, field_mapping, success_count, fail_count,
             last_status, html_signature, updated_at)
            VALUES (?, ?, ?, 0, 1, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                fail_count = fail_count + 1,
                last_status = excluded.last_status,
                updated_at = excluded.updated_at""",
            (domain, form_url, mapping_json, status, html_signature, now),
        )

    conn.commit()
    conn.close()
    logger.info("キャッシュ更新: %s → %s", domain, status)


def is_cache_reliable(
    cache: dict,
    min_success: int = DEFAULT_MIN_SUCCESS,
    max_fail_ratio: float = DEFAULT_MAX_FAIL_RATIO,
) -> bool:
    """キャッシュの信頼性を判定する

    成功回数が閾値以上かつ失敗率が閾値以下なら信頼できる。
    サイトリニューアル等で失敗が増えると自動的にFalseになり、
    再解析が走る設計。

    Args:
        cache: get_form_cacheの返却辞書
        min_success: 最低成功回数（デフォルト3）
        max_fail_ratio: 最大失敗率（デフォルト0.3）

    Returns:
        信頼できればTrue
    """
    sc = cache.get("success_count", 0)
    fc = cache.get("fail_count", 0)
    total = sc + fc

    # 成功回数が不足
    if sc < min_success:
        return False

    # 失敗率チェック
    ratio = fc / total if total > 0 else 0
    return ratio <= max_fail_ratio


def get_cache_stats() -> dict:
    """キャッシュ統計を取得する

    Returns:
        {"total_cached": int, "reliable_count": int}
    """
    conn = _conn()
    rows = conn.execute(
        "SELECT success_count, fail_count FROM form_cache"
    ).fetchall()
    conn.close()

    total = len(rows)
    reliable = sum(
        1 for r in rows
        if is_cache_reliable({
            "success_count": r["success_count"],
            "fail_count": r["fail_count"],
        })
    )

    return {"total_cached": total, "reliable_count": reliable}


def delete_form_cache(domain: str) -> None:
    """指定ドメインのキャッシュを削除する

    Args:
        domain: ドメイン名
    """
    conn = _conn()
    conn.execute("DELETE FROM form_cache WHERE domain = ?", (domain,))
    conn.commit()
    conn.close()
    logger.info("キャッシュ削除: %s", domain)


def cleanup_stale_cache(days: int = 180) -> int:
    """古い未使用キャッシュを削除する

    成功回数0かつ指定日数以上経過したエントリを削除。

    Args:
        days: 保持日数（デフォルト180日）

    Returns:
        削除件数
    """
    conn = _conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur = conn.execute(
        "DELETE FROM form_cache "
        "WHERE success_count = 0 AND updated_at < ?",
        (cutoff,),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        logger.info("古いキャッシュ削除: %d件", deleted)
    return deleted


# === クロスサイト学習 ===

# CMS/プラグインのクラス名シグネチャ
_CMS_CLASS_PREFIXES = [
    "wpcf7", "mw_wp_form", "mwform", "smf-", "snow-monkey",
    "gform", "ginput", "formrun", "hp4u",
]


def compute_html_signature(form) -> str:
    """フォームのCSS class名からHTML署名を生成する

    CMS/プラグイン固有のクラス名を検出し、署名文字列として返す。
    署名が一致する異なるドメインのフォームは同じ構造を持つと推定できる。

    Args:
        form: BeautifulSoupのform要素

    Returns:
        署名文字列（例: "wpcf7"）、検出できなければ空文字
    """
    # form要素とその子孫のclass属性を収集
    all_classes = []
    form_classes = form.get("class", [])
    if isinstance(form_classes, list):
        all_classes.extend(form_classes)

    for child in form.find_all(True):
        child_classes = child.get("class", [])
        if isinstance(child_classes, list):
            all_classes.extend(child_classes)

    class_str = " ".join(all_classes).lower()

    # 既知のCMSプレフィックスを検索
    for prefix in _CMS_CLASS_PREFIXES:
        if prefix in class_str:
            return prefix

    return ""


def get_cache_by_signature(signature: str) -> Optional[dict]:
    """HTML署名が一致する他ドメインのキャッシュを検索する

    クロスサイト学習の核心。同じCMS/プラグインを使うサイト間で
    成功したマッピングを共有する。

    Args:
        signature: compute_html_signatureで生成した署名

    Returns:
        最も信頼性の高いキャッシュデータ、なければNone
    """
    if not signature:
        return None

    conn = _conn()
    row = conn.execute(
        "SELECT form_url, field_mapping, success_count, fail_count "
        "FROM form_cache "
        "WHERE html_signature = ? AND success_count >= 2 "
        "ORDER BY success_count DESC LIMIT 1",
        (signature,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    logger.info(
        "クロスサイトキャッシュ発見: 署名=%s, 成功=%d",
        signature, row["success_count"],
    )
    return {
        "form_url": row["form_url"],
        "field_mapping": json.loads(row["field_mapping"]),
        "success_count": row["success_count"],
        "fail_count": row["fail_count"],
    }
