"""
工具選定AI モック — Streamlit UI
材料・形状・加工方法を入力すると最適な工具と切削条件を提案する
"""

import logging
import streamlit as st
from cutting_calc import calculate_conditions
from tool_db import MATERIALS

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


def render_header() -> None:
    """ヘッダーを描画する"""
    st.markdown("""
    <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);
                padding:20px 24px;border-radius:12px;margin-bottom:24px">
        <h1 style="color:white;margin:0;font-size:26px">
            🔧 工具選定AI
            <span style="color:#4FC3F7;font-size:14px;margin-left:12px">
                エンドミル加工 条件提案システム
            </span>
        </h1>
        <p style="color:#90CAF9;margin:8px 0 0;font-size:13px">
            材料・加工径・深さを入力すると、最適な工具と切削条件を提案します
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_input_form() -> tuple[str, float, float, int] | None:
    """入力フォームを描画し、入力値を返す"""
    st.markdown("### 📝 加工条件を入力")

    col1, col2 = st.columns(2)

    with col1:
        material = st.selectbox(
            "材料の種類",
            options=list(MATERIALS.keys()),
            help="加工する材料を選択してください"
        )
        diameter = st.number_input(
            "加工径 [mm]",
            min_value=1.0, max_value=100.0, value=10.0, step=1.0,
            help="ポケットや溝の加工径"
        )

    with col2:
        depth = st.number_input(
            "加工深さ [mm]",
            min_value=0.5, max_value=100.0, value=5.0, step=0.5,
            help="仕上がりの加工深さ"
        )
        max_rpm = st.number_input(
            "主軸最大回転数 [rpm]",
            min_value=1000, max_value=30000, value=10000, step=1000,
            help="使用する機械の主軸最大回転数"
        )

    # 材料情報の表示
    mat = MATERIALS[material]
    with st.expander(f"📋 {material} の材料情報"):
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("硬度", f"{mat['hardness']} HB")
        col_b.metric("被削性", f"{mat['machinability']:.2f}")
        col_c.metric("推奨Vc", f"{mat['Vc_range'][0]}〜{mat['Vc_range'][1]} m/min")

    if st.button("🔍 工具を選定する", use_container_width=True, type="primary"):
        return material, diameter, depth, max_rpm
    return None


def render_result(result, rank: int) -> None:
    """1件の工具提案結果をカード形式で表示する"""
    tool = result.tool

    # ランク別の色
    colors = {1: "#4CAF50", 2: "#2196F3", 3: "#FF9800"}
    color = colors.get(rank, "#757575")
    badge = {1: "🥇 最推奨", 2: "🥈 推奨", 3: "🥉 代替"}
    badge_text = badge.get(rank, f"#{rank}")

    st.markdown(f"""
    <div style="border-left:4px solid {color};padding:12px 16px;
                background:#f8f9fa;border-radius:0 8px 8px 0;margin-bottom:16px">
        <span style="background:{color};color:white;padding:2px 10px;
                     border-radius:4px;font-size:12px;font-weight:700">
            {badge_text}
        </span>
        <span style="font-size:16px;font-weight:700;margin-left:8px">
            {tool['maker']} {tool['series']}
        </span>
        <span style="color:#888;font-size:13px;margin-left:8px">
            {tool['model']}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # 工具情報と切削条件を2カラムで表示
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🔧 工具情報**")
        info_data = {
            "メーカー": tool["maker"],
            "シリーズ": tool["series"],
            "型番": tool["model"],
            "使用径": f"φ{result.tool_diameter} mm",
            "刃数": f"{tool['flutes']} 枚",
            "コーティング": tool["coating"],
            "ねじれ角": f"{tool['helix_angle']}°",
            "参考価格": f"¥{tool['price_range'][0]:,}〜¥{tool['price_range'][1]:,}",
        }
        for k, v in info_data.items():
            st.markdown(f"- **{k}**: {v}")

    with col2:
        st.markdown("**⚙️ 推奨切削条件**")
        cond_data = {
            "切削速度 Vc": f"{result.cutting_speed} m/min",
            "主軸回転数 N": f"{result.spindle_rpm:,} rpm",
            "1刃送り fz": f"{result.feed_per_tooth} mm/tooth",
            "テーブル送り Vf": f"{result.feed_rate:,} mm/min",
            "軸方向切込み ap": f"{result.axial_depth} mm",
            "径方向切込み ae": f"{result.radial_depth} mm",
            "加工パス回数": f"{result.n_passes} 回",
        }
        for k, v in cond_data.items():
            st.markdown(f"- **{k}**: {v}")

    # メトリクス
    m1, m2, m3 = st.columns(3)
    m1.metric("🕐 予想工具寿命", f"{result.estimated_life_min:.0f} 分")
    m2.metric("📊 材料除去率 MRR", f"{result.mrr} cm³/min")
    m3.metric("🔄 パス回数", f"{result.n_passes} 回")

    # 注意事項
    if result.notes:
        with st.expander("⚠️ 注意事項"):
            for note in result.notes:
                st.markdown(f"- {note}")

    st.markdown("---")


def render_formula_reference() -> None:
    """切削理論式のリファレンスをサイドバーに表示する"""
    with st.sidebar:
        st.markdown("### 📐 切削理論式")
        st.latex(r"N = \frac{1000 \times V_c}{\pi \times D}")
        st.caption("N: 回転数, Vc: 切削速度, D: 工具径")

        st.latex(r"V_f = f_z \times z \times N")
        st.caption("Vf: 送り速度, fz: 1刃送り, z: 刃数")

        st.latex(r"MRR = a_p \times a_e \times V_f")
        st.caption("MRR: 材料除去率, ap: 軸方向切込み, ae: 径方向切込み")

        st.markdown("---")
        st.markdown("### 工具寿命（テイラーの式）")
        st.latex(r"V_c \times T^n = C")
        st.caption("T: 工具寿命, n: 指数(超硬≈0.25), C: 定数")

        st.markdown("---")
        st.caption("💡 モックデータを使用しています")
        st.caption("実際の加工では必ず工具メーカーの推奨条件を確認してください")


def main() -> None:
    """メインアプリ"""
    st.set_page_config(
        page_title="工具選定AI",
        page_icon="🔧",
        layout="wide"
    )

    render_header()
    render_formula_reference()

    # 入力フォーム
    input_result = render_input_form()

    if input_result is None:
        # 初期画面のガイド
        st.markdown("""
        <div style="text-align:center;padding:40px;color:#888">
            <p style="font-size:48px;margin:0">🔧</p>
            <p style="font-size:16px">上の入力欄に加工条件を入力して<br>
            「工具を選定する」ボタンを押してください</p>
        </div>
        """, unsafe_allow_html=True)
        return

    material, diameter, depth, max_rpm = input_result

    # 切削条件計算
    with st.spinner("工具を選定中..."):
        results = calculate_conditions(material, diameter, depth, max_rpm)

    if not results:
        st.error("適合する工具が見つかりませんでした。加工径を確認してください。")
        return

    # 結果表示
    st.markdown(f"### 🎯 提案結果（{len(results)}件）")
    st.markdown(f"**条件**: {material} / 加工径φ{diameter}mm / 深さ{depth}mm / 最大{max_rpm:,}rpm")
    st.markdown("---")

    for i, result in enumerate(results):
        render_result(result, rank=i + 1)


if __name__ == "__main__":
    main()
