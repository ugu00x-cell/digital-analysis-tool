"""
鬼速PDCAダッシュボード - Streamlit版
タスク管理・読書記録・日報の3機能を1画面で管理
"""

import logging
import json
import datetime
from pathlib import Path
import streamlit as st

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# データ保存先
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


# ─── データ永続化 ─────────────────────────────────────────
def load_json(filename: str, default: dict | list) -> dict | list:
    """JSONファイルからデータを読み込む"""
    filepath = DATA_DIR / filename
    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning(f"{filename} の読み込みに失敗、デフォルト値を使用")
    return default


def save_json(filename: str, data: dict | list) -> None:
    """データをJSONファイルに保存"""
    filepath = DATA_DIR / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ─── セッション初期化 ────────────────────────────────────
def init_session() -> None:
    """session_stateの初期化（ファイルから復元）"""
    if "tasks" not in st.session_state:
        st.session_state.tasks = load_json("tasks.json", [
            {"text": "サンプルタスク", "priority": "中", "done": False, "time": "1h"},
        ])
    if "reflection" not in st.session_state:
        st.session_state.reflection = ""
    if "next_action" not in st.session_state:
        st.session_state.next_action = ""
    if "books" not in st.session_state:
        st.session_state.books = load_json("books.json", [
            {"title": "鬼速PDCA", "total_pages": 230, "sessions": []},
        ])
    if "reports" not in st.session_state:
        st.session_state.reports = load_json("reports.json", [])


def save_all() -> None:
    """全データをファイルに保存"""
    save_json("tasks.json", st.session_state.tasks)
    save_json("books.json", st.session_state.books)
    save_json("reports.json", st.session_state.reports)
    logger.info("データを保存しました")


# ─── タスク管理タブ ──────────────────────────────────────
def render_task_tab() -> None:
    """タスク管理タブを描画"""
    tasks = st.session_state.tasks
    done_count = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    # P: 計画
    st.markdown("### 🅿️ 計画 — 今日のタスク")

    if total > 0:
        st.progress(done_count / total, text=f"完了率: {done_count}/{total} ({done_count * 100 // total}%)")

    # タスク追加フォーム
    col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
    with col1:
        new_task = st.text_input("タスク", placeholder="タスクを入力...", label_visibility="collapsed")
    with col2:
        new_priority = st.selectbox("優先度", ["高", "中", "低"], index=1, label_visibility="collapsed")
    with col3:
        new_time = st.text_input("時間", placeholder="例:1h", label_visibility="collapsed")
    with col4:
        if st.button("➕ 追加", use_container_width=True):
            if new_task.strip():
                tasks.append({"text": new_task, "priority": new_priority, "done": False, "time": new_time})
                save_all()
                st.rerun()

    # タスク一覧（優先度順）
    priority_order = {"高": 0, "中": 1, "低": 2}
    sorted_tasks = sorted(enumerate(tasks), key=lambda x: priority_order.get(x[1]["priority"], 9))

    # 優先度バッジの色
    priority_colors = {"高": "🔴", "中": "🟡", "低": "⚪"}

    for idx, task in sorted_tasks:
        col_check, col_badge, col_text, col_time, col_del = st.columns([0.5, 0.5, 5, 1, 0.5])
        with col_check:
            checked = st.checkbox("done", value=task["done"], key=f"task_{idx}", label_visibility="collapsed")
            if checked != task["done"]:
                tasks[idx]["done"] = checked
                save_all()
                st.rerun()
        with col_badge:
            st.write(priority_colors.get(task["priority"], "⚪"))
        with col_text:
            style = "~~" if task["done"] else ""
            st.write(f"{style}{task['text']}{style}")
        with col_time:
            if task["time"]:
                st.caption(task["time"])
        with col_del:
            if st.button("×", key=f"del_{idx}"):
                tasks.pop(idx)
                save_all()
                st.rerun()

    st.divider()

    # C: 振り返り
    st.markdown("### 🔍 検証 — 振り返り（夕方3分）")
    st.session_state.reflection = st.text_area(
        "振り返り", value=st.session_state.reflection,
        placeholder="できたこと・できなかった理由・気づき...",
        label_visibility="collapsed", height=100
    )

    # A: 調整
    st.markdown("### 🔄 調整 — 明日への改善")
    st.session_state.next_action = st.text_area(
        "改善", value=st.session_state.next_action,
        placeholder="明日変えること・続けること...",
        label_visibility="collapsed", height=100
    )


# ─── 読書記録タブ ────────────────────────────────────────
def render_reading_tab() -> None:
    """読書記録タブを描画"""
    books = st.session_state.books

    # P: 本の追加
    st.markdown("### 🅿️ 計画 — 読書リスト")
    col1, col2, col3 = st.columns([4, 2, 1])
    with col1:
        new_title = st.text_input("本のタイトル", placeholder="本のタイトル", label_visibility="collapsed")
    with col2:
        new_pages = st.number_input("総ページ数", min_value=1, value=200, label_visibility="collapsed")
    with col3:
        if st.button("📚 追加", use_container_width=True):
            if new_title.strip():
                books.append({"title": new_title, "total_pages": new_pages, "sessions": []})
                save_all()
                st.rerun()

    if not books:
        st.info("本を追加してください")
        return

    # 本の選択
    book_titles = [b["title"] for b in books]
    selected_idx = st.radio("本を選択", range(len(books)), format_func=lambda i: book_titles[i], horizontal=True)
    book = books[selected_idx]

    st.divider()

    # D: 読書セッション記録
    st.markdown(f"### 📖 実行 — 「{book['title']}」の読書セッション")

    # 進捗バー
    read_pages = sum(s["pages"] for s in book["sessions"])
    total = book["total_pages"]
    pct = min(100, int(read_pages / total * 100)) if total > 0 else 0
    st.progress(pct / 100, text=f"読了: {read_pages}/{total}ページ ({pct}%)")

    # セッション追加
    col1, col2, col3 = st.columns([2, 4, 1])
    with col1:
        session_pages = st.number_input("今日読んだページ数", min_value=0, value=0, label_visibility="collapsed")
    with col2:
        session_memo = st.text_input("メモ", placeholder="3行メモ（気づき）", label_visibility="collapsed")
    with col3:
        if st.button("📝 記録", use_container_width=True):
            if session_pages > 0:
                book["sessions"].append({
                    "date": datetime.date.today().isoformat(),
                    "pages": session_pages,
                    "memo": session_memo
                })
                save_all()
                st.rerun()

    # セッション履歴
    if book["sessions"]:
        for s in reversed(book["sessions"]):
            st.markdown(f"**{s['date']}** — +{s['pages']}p　{s.get('memo', '')}")
    else:
        st.caption("まだ記録がありません")

    st.divider()

    # C: 曜日チェック
    st.markdown("### 🔍 検証 — 今週の読書チェック")
    days = ["月", "火", "水", "木", "金", "土", "日"]
    cols = st.columns(7)
    for i, day in enumerate(days):
        with cols[i]:
            st.checkbox(day, key=f"day_{selected_idx}_{i}")


# ─── 日報タブ ────────────────────────────────────────────
def render_report_tab() -> None:
    """日報タブを描画"""
    reports = st.session_state.reports

    # 新規作成
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📄 新規日報", use_container_width=True):
            reports.append({
                "date": datetime.date.today().isoformat(),
                "goal": "", "tasks": "",
                "done_good": "", "done_bad": "",
                "cause": "", "insight": "",
                "next": "", "keep": ""
            })
            save_all()
            st.rerun()

    if not reports:
        st.info("「新規日報」を押して日報を作成してください")
        return

    # 日報選択
    with col1:
        report_dates = [r["date"] for r in reports]
        selected_idx = st.selectbox("日報を選択", range(len(reports)),
                                     format_func=lambda i: report_dates[i],
                                     index=len(reports) - 1)
    r = reports[selected_idx]

    # P/D/C/A 入力（2カラムレイアウト）
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 🅿️ 計画")
        r["goal"] = st.text_input("今日のゴール", value=r["goal"], key="rp_goal")
        r["tasks"] = st.text_area("優先タスク", value=r["tasks"], height=80, key="rp_tasks")

        st.markdown("### 🔍 検証")
        r["cause"] = st.text_area("できなかった原因", value=r["cause"], height=80, key="rp_cause")
        r["insight"] = st.text_area("気づき", value=r["insight"], height=80, key="rp_insight")

    with col_right:
        st.markdown("### ▶️ 実行")
        r["done_good"] = st.text_area("できたこと", value=r["done_good"], height=80, key="rp_good")
        r["done_bad"] = st.text_area("できなかったこと", value=r["done_bad"], height=80, key="rp_bad")

        st.markdown("### 🔄 調整")
        r["next"] = st.text_input("明日の最優先", value=r["next"], key="rp_next")
        r["keep"] = st.text_area("継続すること", value=r["keep"], height=80, key="rp_keep")

    # 保存 & コピー
    col_save, col_copy = st.columns(2)
    with col_save:
        if st.button("💾 保存", use_container_width=True):
            save_all()
            st.success("保存しました！")

    with col_copy:
        # 日報テキスト生成
        report_text = f"""【日報】{r['date']}

■ P（今日の計画）
・ゴール：{r['goal']}
・優先タスク：{r['tasks']}

■ D（実行したこと）
・できたこと：{r['done_good']}
・できなかったこと：{r['done_bad']}

■ C（振り返り）
・原因：{r['cause']}
・気づき：{r['insight']}

■ A（明日への調整）
・明日の優先：{r['next']}
・継続すること：{r['keep']}"""
        st.code(report_text, language=None)


# ─── メインアプリ ────────────────────────────────────────
def main() -> None:
    """メインアプリ"""
    st.set_page_config(
        page_title="鬼速PDCA ダッシュボード",
        page_icon="🚀",
        layout="wide"
    )

    # ヘッダー
    st.markdown("""
    <div style="background:#1a1a2e;padding:16px 24px;border-radius:12px;margin-bottom:24px">
        <h1 style="color:white;margin:0;font-size:24px">
            🚀 鬼速PDCA <span style="color:#e94560;font-size:14px">ダッシュボード</span>
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # セッション初期化
    init_session()

    # タブ
    tab1, tab2, tab3 = st.tabs(["📋 タスク管理", "📚 読書記録", "📝 日報"])

    with tab1:
        render_task_tab()
    with tab2:
        render_reading_tab()
    with tab3:
        render_report_tab()

    # サイドバー：保存ボタン
    with st.sidebar:
        st.markdown("### ⚙️ 設定")
        if st.button("💾 全データ保存", use_container_width=True):
            save_all()
            st.success("保存完了！")
        st.caption(f"データ保存先: {DATA_DIR}")
        st.caption(f"最終アクセス: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
