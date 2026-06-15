"""設定画面 - プロファイル管理・テンプレート管理・送信設定・APIキー"""

import os
from pathlib import Path

import streamlit as st

from utils.db import init_db
from utils.db_profiles import save_profile, get_profiles, delete_profile
from utils.db_templates import save_template, get_templates, delete_template
from utils.db_logs import get_setting, save_setting

# ツールルートディレクトリ（settings.py の2階層上）
_BASE_DIR = Path(__file__).parent.parent


def _write_env_key(env_key: str, value: str) -> None:
    """.envファイルにAPIキーを書き込む（なければ追加、あれば上書き）

    .envファイルが再起動後も読み込まれるため、
    ツールを再インストール・再起動しても設定が維持される。

    Args:
        env_key: 環境変数名（例: GEMINI_API_KEY）
        value: 保存する値
    """
    env_path = _BASE_DIR / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    # 既存行を更新 or 末尾に追加
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{env_key}="):
            new_lines.append(f"{env_key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{env_key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    # 現在のプロセスの環境変数にも即時反映
    os.environ[env_key] = value

init_db()


def _render_profile_form(data: dict, key_prefix: str) -> None:
    """プロファイル入力フォームを描画する

    自動入力する差出人情報を入力する画面。
    フォームによっては姓名・カナが分割されていない場合もあるので、
    両方の入力欄を用意している。
    """
    st.caption(
        "💡 入力した情報がフォームに自動入力されます。"
        "サイトによって項目名が異なるため、できる限り全項目を入力推奨です。"
    )
    nm = st.text_input(
        "プロファイル名（管理用・例:営業A）",
        value=data.get("name", ""),
        key=f"{key_prefix}_name",
        help="このプロファイルの管理用ラベル。送信時には使われません。",
    )
    co = st.text_input(
        "会社名", value=data.get("company", ""), key=f"{key_prefix}_co"
    )
    c1, c2 = st.columns(2)
    with c1:
        ln = st.text_input("姓（例:山田）", value=data.get("last_name", ""), key=f"{key_prefix}_ln")
        lk = st.text_input("姓カナ（例:ヤマダ）", value=data.get("last_kana", ""), key=f"{key_prefix}_lk")
    with c2:
        fn = st.text_input("名（例:太郎）", value=data.get("first_name", ""), key=f"{key_prefix}_fn")
        fk = st.text_input("名カナ（例:タロウ）", value=data.get("first_kana", ""), key=f"{key_prefix}_fk")

    c3, c4 = st.columns(2)
    with c3:
        em = st.text_input("メールアドレス", value=data.get("email", ""), key=f"{key_prefix}_em")
        po = st.text_input(
            "郵便番号（例:1000001）", value=data.get("postal", ""),
            key=f"{key_prefix}_po",
            help="ハイフンあり/なしどちらでもOK。フォームに合わせて自動調整します。",
        )
    with c4:
        ph = st.text_input(
            "電話番号（例:0312345678）", value=data.get("phone", ""),
            key=f"{key_prefix}_ph",
            help="ハイフンあり/なしどちらでもOK。",
        )
    ad = st.text_input(
        "住所（都道府県〜番地までまとめて）",
        value=data.get("address", ""), key=f"{key_prefix}_ad",
        help="都道府県・市区町村・番地が分かれたフォームの場合は、住所全体を入れていただければシステムが自動分割します。",
    )
    name = nm  # 既存コードとの互換性

    if st.button("保存", key=f"{key_prefix}_save"):
        new_data = {
            "name": name, "last_name": ln, "first_name": fn,
            "last_kana": lk, "first_kana": fk, "company": co,
            "email": em, "phone": ph, "postal": po, "address": ad,
        }
        if data.get("id"):
            new_data["id"] = data["id"]
        save_profile(new_data)
        st.success("保存しました")
        st.rerun()


st.header("⚙️ 設定")

# === APIキー ===
st.subheader("🔑 Gemini APIキー")
saved_key = get_setting("gemini_api_key", "")
api_key = st.text_input(
    "Google Gemini APIキー",
    value=st.session_state.get("gemini_api_key", saved_key),
    type="password",
    help="フォーム解析のAI補完に使用。なくても動作します。",
)
st.session_state["gemini_api_key"] = api_key
if st.button("APIキーを保存", key="save_key"):
    save_setting("gemini_api_key", api_key)   # DB に保存
    _write_env_key("GEMINI_API_KEY", api_key) # .env に保存（再起動後も維持）
    st.success("保存しました ✅（再起動・再インストール後も維持されます）")
st.caption("取得: https://aistudio.google.com/app/apikey")

st.divider()

# === 2Captcha APIキー ===
st.subheader("🧩 2Captcha APIキー")
st.caption(
    "CAPTCHA自動解決サービス。未設定時はCAPTCHAサイトをスキップします。"
)
saved_2c = get_setting("two_captcha_api_key", "")
two_captcha_key = st.text_input(
    "2Captcha APIキー",
    value=st.session_state.get("two_captcha_api_key", saved_2c),
    type="password",
    help="2Captchaでアカウント作成・APIキー発行後、ここに入力してください。",
)
st.session_state["two_captcha_api_key"] = two_captcha_key
if st.button("2Captchaキーを保存", key="save_2c_key"):
    save_setting("two_captcha_api_key", two_captcha_key)
    _write_env_key("TWO_CAPTCHA_API_KEY", two_captcha_key)  # .env に保存
    st.success("保存しました ✅（再起動・再インストール後も維持されます）")
st.caption("取得: https://2captcha.com/enterpage")

# 使用状況の表示
from datetime import datetime as _dt
_month_key = f"captcha_solve_count_month_{_dt.now().strftime('%Y%m')}"
_solve_cnt = int(get_setting(_month_key, "0") or "0")
try:
    _spend = float(get_setting("captcha_spend_jpy", "0") or "0")
except ValueError:
    _spend = 0.0
st.info(
    f"📊 今月の解決数: **{_solve_cnt}回** / "
    f"推定費用累計: **{_spend:.1f}円**"
)

st.divider()

# === 送信設定 ===
st.subheader("📊 送信設定")
col_a, col_b = st.columns(2)
with col_a:
    daily = st.number_input(
        "1日あたり送信上限",
        min_value=1, max_value=1000,
        value=int(get_setting("daily_limit", "200")),
    )
with col_b:
    interval = st.number_input(
        "送信間隔（秒）",
        min_value=1, max_value=300,
        value=int(get_setting("send_interval", "10")),
    )
if st.button("送信設定を保存", key="save_send"):
    save_setting("daily_limit", str(daily))
    save_setting("send_interval", str(interval))
    st.success("保存しました")

st.warning(
    "⚠️ 同じネットワーク（Wi-Fi）から複数台同時に動かす場合、"
    "同一IPからのアクセスとなりブロックリスクが高まります。\n\n"
    "複数台で運用する場合は、各端末で異なる回線（モバイル回線等）を"
    "使用することを推奨します。"
)

st.divider()

# === 差出人プロファイル ===
st.subheader("👤 差出人プロファイル")

profiles = get_profiles()
profile_names = [f"{p['id']}: {p['name']}" for p in profiles]

tab_sel, tab_new = st.tabs(["選択・編集", "新規作成"])

with tab_sel:
    if not profiles:
        st.info("プロファイルがありません。新規作成してください。")
    else:
        chosen = st.selectbox("プロファイル選択", profile_names, key="prof_sel")
        if chosen:
            pid = int(chosen.split(":")[0])
            prof = next(p for p in profiles if p["id"] == pid)
            st.session_state["sender"] = prof

            with st.expander("編集", expanded=False):
                _render_profile_form(prof, key_prefix="edit")

            col_d1, col_d2 = st.columns([3, 1])
            with col_d2:
                if st.button("🗑️ 削除", key="del_prof"):
                    delete_profile(pid)
                    st.rerun()

with tab_new:
    _render_profile_form({}, key_prefix="new")

st.divider()

# === テンプレート管理 ===
st.subheader("✉️ テンプレート管理")

templates = get_templates()
tmpl_names = [f"{t['id']}: {t['name']}" for t in templates]

t_sel, t_new = st.tabs(["選択", "新規作成"])

with t_sel:
    if not templates:
        st.info("テンプレートがありません。新規作成してください。")
    else:
        chosen_t = st.selectbox("テンプレート選択", tmpl_names, key="tmpl_sel")
        if chosen_t:
            tid = int(chosen_t.split(":")[0])
            tmpl = next(t for t in templates if t["id"] == tid)
            st.session_state["template"] = tmpl["body"]
            st.text_area("本文プレビュー", value=tmpl["body"], height=200, disabled=True)

            col_t1, col_t2 = st.columns([3, 1])
            with col_t2:
                if st.button("🗑️ 削除", key="del_tmpl"):
                    delete_template(tid)
                    st.rerun()

with t_new:
    t_name = st.text_input("テンプレート名", key="new_tmpl_name")
    t_body = st.text_area(
        "本文（{{company_name}}で企業名置換）",
        height=250, key="new_tmpl_body",
    )
    if st.button("テンプレートを保存", key="save_tmpl"):
        if t_name and t_body:
            save_template(t_name, t_body)
            st.success("保存しました")
            st.rerun()
        else:
            st.warning("名前と本文を入力してください")
