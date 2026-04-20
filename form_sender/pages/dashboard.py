"""ダッシュボード画面 - 送信状況サマリー・送信実行・途中再開

事前チェック（APIキー・プロファイル・CSV）、送信済み除外、
セッション途中再開、リアルタイム進捗、停止ボタンに対応。
"""

import logging
import time
from urllib.parse import urlparse

import streamlit as st

from utils.db import init_db
from utils.db_logs import (
    get_log_stats,
    get_sent_urls,
    get_setting,
    is_url_sent,
    mark_url_sent,
    save_log,
    is_domain_sent_today,
)
from utils.db_progress import (
    create_session,
    update_progress,
    finish_session,
    get_incomplete_session,
    clear_sessions,
)
from utils.form_sender import send_to_company, random_wait

init_db()
logger = logging.getLogger(__name__)

st.header("📊 ダッシュボード")

# --- 統計表示 ---
stats = get_log_stats()

col1, col2, col3, col4 = st.columns(4)
col1.metric("総送信数", stats["total"])
col2.metric("成功数", stats["success"])
col3.metric("成功率", f"{stats['success_rate']:.1f}%")
col4.metric("AI利用成功率", f"{stats['ai_rate']:.1f}%")

st.divider()
st.info(f"📅 今日の送信数: **{stats['today_count']}** 件")

# ステータス内訳
if stats["by_status"]:
    st.subheader("ステータス内訳")
    labels = {
        "success": "✅ 送信成功",
        "captcha": "🔒 CAPTCHA検出",
        "no_form": "❌ フォームなし",
        "timeout": "⏱️ タイムアウト",
        "error": "⚠️ 送信失敗",
        "robots_blocked": "🤖 robots.txt拒否",
        "skip_domain": "🔁 同一ドメイン制限",
    }
    for status, count in stats["by_status"].items():
        label = labels.get(status, status)
        st.write(f"{label}: **{count}** 件")

st.divider()

# --- 事前チェック ---
st.subheader("🔍 事前チェック")

checks_ok = True

# 1. プロファイルチェック
sender = st.session_state.get("sender")
if not sender or not sender.get("email"):
    st.warning("⚠️ 差出人プロファイルが未設定です → 設定画面で登録してください")
    checks_ok = False
else:
    st.success(f"✅ 差出人: {sender.get('name', '未設定')}")

# 2. テンプレートチェック
template = st.session_state.get("template", "")
if not template:
    st.warning("⚠️ 送信テンプレートが未設定です → 設定画面で選択してください")
    checks_ok = False
else:
    st.success(f"✅ テンプレート: {template[:30]}...")

# 3. CSVチェック
if "company_list" not in st.session_state:
    st.warning("⚠️ 企業リストが未読み込みです → リスト管理でCSVをアップロードしてください")
    checks_ok = False
else:
    df = st.session_state["company_list"]
    st.success(f"✅ 企業リスト: {len(df)}件")

# 4. Gemini APIキー（任意）
api_key = st.session_state.get("gemini_api_key", "")
if api_key:
    st.success("✅ Gemini APIキー: 設定済み")
else:
    st.info("ℹ️ Gemini APIキー未設定（AI補完なしで動作します）")

st.divider()

# --- セッション途中再開 ---
incomplete = get_incomplete_session()
if incomplete:
    st.warning(
        f"⚠️ 前回のセッションが途中です "
        f"（{incomplete['current_index']}/{incomplete['total']}件完了）"
    )
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("▶️ 途中から再開", key="resume_session"):
            st.session_state["resume_from"] = incomplete["current_index"]
            st.session_state["resume_session_id"] = incomplete["session_id"]
    with col_r2:
        if st.button("🔄 最初からやり直す", key="clear_session"):
            finish_session(incomplete["session_id"], "cancelled")
            st.rerun()

# --- 送信実行セクション ---
st.subheader("🚀 送信実行")

if not checks_ok:
    st.warning("事前チェックをすべてクリアしてから送信してください")
else:
    df = st.session_state["company_list"]

    # 送信済みURL除外
    sent_urls = get_sent_urls()
    unsent = df[
        (df["ステータス"] == "未送信") &
        (~df["URL"].isin(sent_urls))
    ]

    # 設定値の取得
    daily_limit = int(get_setting("daily_limit", "200"))
    send_interval = int(get_setting("send_interval", "10"))

    if len(unsent) == 0:
        st.info("未送信の企業はありません")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            headless = st.checkbox(
                "ヘッドレスモード（ブラウザ非表示）", value=True
            )
        with col_b:
            dry_run = st.checkbox("ドライラン（送信ボタンを押さない）")

        remaining = max(0, daily_limit - stats["today_count"])
        target = min(len(unsent), remaining)

        st.info(
            f"未送信: **{len(unsent)}**件 / "
            f"1日上限: **{daily_limit}**件 / "
            f"残り枠: **{remaining}**件 / "
            f"送信間隔: **{send_interval}**秒"
        )

        # 途中再開の場合、開始インデックスを調整
        resume_from = st.session_state.pop("resume_from", 0)

        if remaining == 0:
            st.error("🚫 本日の送信上限に達しています")
        elif st.button(
            f"📨 {target}件に送信開始",
            type="primary",
            disabled=target == 0,
        ):
            _run_sending(
                df, unsent, target, headless, dry_run,
                send_interval, resume_from,
            )


def _run_sending(
    df, unsent, target: int, headless: bool,
    dry_run: bool, interval: int, resume_from: int = 0,
) -> None:
    """送信処理を実行する

    Args:
        df: 全企業DataFrame
        unsent: 未送信企業DataFrame
        target: 送信対象件数
        headless: ヘッドレスモード
        dry_run: ドライランモード
        interval: 送信間隔（秒）
        resume_from: 途中再開時の開始インデックス
    """
    sender = st.session_state.get("sender", {})
    body = st.session_state.get("template", "")

    # セッション作成（途中再開でなければ新規）
    sid = st.session_state.pop("resume_session_id", None)
    if not sid:
        sid = create_session(target)

    progress = st.progress(0, text="送信準備中...")
    status_area = st.empty()
    results_area = st.container()

    # 停止フラグ
    stop_col1, stop_col2 = st.columns([3, 1])
    with stop_col2:
        stop_button = st.button("⏹️ 停止", key="stop_sending", type="secondary")

    success_count = 0
    fail_count = 0

    for i, (idx, row) in enumerate(unsent.head(target).iterrows()):
        # 途中再開: 既に処理済みの分をスキップ
        if i < resume_from:
            continue

        # 停止ボタンチェック
        if stop_button or st.session_state.get("_stop_flag"):
            finish_session(sid, "paused")
            status_area.warning(f"⏹️ {i}件目で停止しました")
            st.session_state["_stop_flag"] = False
            break

        company = row["企業名"]
        url = row["URL"]

        # URLが空ならスキップ
        if not url or str(url) == "nan":
            continue

        # 送信済みチェック（二重送信防止）
        if is_url_sent(url):
            logger.info("送信済みスキップ: %s", url)
            continue

        # 同一ドメイン制限チェック
        domain = urlparse(url).netloc
        if is_domain_sent_today(domain):
            df.loc[idx, "ステータス"] = "同一ドメイン制限"
            save_log(url, company, "skip_domain", "同日ドメイン重複")
            with results_area:
                st.write(f"🔁 {company}: 同一ドメイン制限でスキップ")
            continue

        message = body.replace("{{company_name}}", company)

        progress.progress(
            (i + 1) / target,
            text=f"送信中: {company}（{i+1}/{target}）",
        )
        status_area.info(f"🔄 {company} に送信中...")

        result = send_to_company(
            url, company, message, sender, headless, dry_run
        )

        # ステータス反映
        label_map = {
            "success": "送信成功", "captcha": "CAPTCHA",
            "no_form": "フォームなし", "robots_blocked": "robots拒否",
            "error": "送信失敗", "dry_run": "ドライラン完了",
            "skip_spa": "SPA検出", "skip_iframe": "iframeフォーム",
            "skip_file_upload": "ファイル添付必須",
        }
        status_label = label_map.get(result["status"], "送信失敗")
        df.loc[idx, "ステータス"] = status_label
        st.session_state["company_list"] = df

        # DB記録
        mark_url_sent(url, result["status"])
        save_log(
            url, company, result["status"],
            error=result.get("detail", ""),
            retry=result.get("retry_count", 0),
            ai_used=result.get("ai_used", False),
        )

        # 進捗更新
        update_progress(sid, i + 1)

        # カウント
        if result["status"] == "success":
            success_count += 1
        else:
            fail_count += 1

        with results_area:
            icon = "✅" if result["status"] in ("success", "dry_run") else "❌"
            st.write(f"{icon} {company}: {result['detail']}")

        # ウェイト（最終件以外）
        if i < target - 1:
            wait = random_wait(base_interval=interval)
            status_area.info(f"⏳ {wait:.0f}秒待機中...")
            time.sleep(wait)

    # セッション完了
    finish_session(sid, "completed")
    progress.progress(1.0, text="送信完了！")
    status_area.success(
        f"✅ 送信完了 - 成功: {success_count}件 / 失敗: {fail_count}件"
    )
