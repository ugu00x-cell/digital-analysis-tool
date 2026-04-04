"""スカッと動画 台本品質チェッカー Streamlit UI"""

import logging
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from models.check_result import CheckReport
from services.checker import run_check_fix_loop

# .envからAPIキー読み込み
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def render_header() -> None:
    """ページヘッダーを描画する"""
    st.set_page_config(
        page_title="台本品質チェッカー",
        page_icon="🎬",
        layout="wide",
    )
    st.title("🎬 スカッと動画 台本品質チェッカー")
    st.caption(
        "台本をアップロードすると、8つの観点でAIがチェック＆自動修正します"
    )


def render_check_items() -> None:
    """チェック項目一覧をサイドバーに表示する"""
    st.sidebar.header("📋 チェック項目")
    items = [
        "① 対比描写が同一文内にあるか",
        "② 五感描写があるか",
        "③ 視点のブレがないか",
        "④ 心の声が1シーンに2つ以上ないか",
        "⑤ 同じ内容の繰り返しがないか",
        "⑥ 覚悟シーンに具体物トリガーがあるか",
        "⑦ 悪役の攻撃パターンに変化があるか",
        "⑧ 効果音が適切に入っているか",
    ]
    for item in items:
        st.sidebar.markdown(f"- {item}")
    st.sidebar.divider()
    st.sidebar.info("最大3回ループしてチェック＆修正します")


def render_report(report: CheckReport) -> None:
    """チェック結果を表示する

    Args:
        report: チェック結果レポート
    """
    st.subheader(f"📝 チェック {report.loop_number}回目")

    # スコアのメトリクス
    col1, col2, col3 = st.columns(3)
    col1.metric("合格", f"{report.passed_count}/{len(report.items)}")
    col2.metric("不合格", report.failed_count)
    status = "🎉 全合格！" if report.all_passed else "⚠️ 要修正"
    col3.metric("ステータス", status)

    # 各項目の結果
    for item in report.items:
        if item.passed:
            st.success(f"✅ {item.name}")
        else:
            with st.expander(f"❌ {item.name}", expanded=True):
                st.write(item.details)
                # 問題箇所の引用
                for loc in item.locations:
                    st.code(loc, language=None)

    # 要約コメント
    if report.summary:
        st.info(f"💬 {report.summary}")


def save_results(
    fixed: str, reports: list[CheckReport], filename: str
) -> tuple[Path, Path]:
    """修正版とチェックログをファイルに保存する

    Args:
        fixed: 修正後の台本テキスト
        reports: 全ループのチェック結果
        filename: 元ファイル名（拡張子なし）

    Returns:
        (修正版パス, ログパス)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 修正版保存
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{filename}_fixed_{timestamp}.txt"
    out_path.write_text(fixed, encoding="utf-8")

    # チェックログ保存
    log_dir = Path("check_results")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"{filename}_check_{timestamp}.txt"
    log_text = "\n\n".join(r.to_log_text() for r in reports)
    log_path.write_text(log_text, encoding="utf-8")

    return out_path, log_path


def main() -> None:
    """Streamlitアプリのメイン処理"""
    render_header()
    render_check_items()

    # ファイルアップロード
    uploaded = st.file_uploader(
        "台本ファイルをアップロード",
        type=["txt", "md"],
        help="テキストまたはMarkdown形式の台本ファイル",
    )

    # テキスト直接入力も対応
    with st.expander("📝 テキストを直接入力する場合"):
        text_input = st.text_area(
            "台本テキスト",
            height=300,
            placeholder="ここに台本を貼り付け...",
        )

    # 台本テキストの取得
    script = ""
    filename = "direct_input"
    if uploaded is not None:
        script = uploaded.read().decode("utf-8")
        filename = Path(uploaded.name).stem
        st.success(f"📄 {uploaded.name}（{len(script)}文字）")
    elif text_input:
        script = text_input

    # チェック実行ボタン
    if st.button("🚀 チェック＆修正を開始", type="primary"):
        if not script.strip():
            st.error("台本テキストが空です。ファイルをアップロードするか、テキストを入力してください。")
            return

        # プログレス表示
        progress = st.progress(0, text="チェック中...")

        try:
            fixed, reports = run_check_fix_loop(script)

            # 各ループの結果を表示
            for i, report in enumerate(reports):
                progress.progress(
                    (i + 1) / len(reports),
                    text=f"チェック {report.loop_number}回目 完了",
                )
                render_report(report)
                st.divider()

            progress.progress(1.0, text="完了！")

            # 修正版の表示
            st.subheader("📄 修正版台本")
            st.text_area(
                "修正後",
                value=fixed,
                height=400,
                label_visibility="collapsed",
            )

            # ダウンロードボタン
            st.download_button(
                "📥 修正版をダウンロード",
                data=fixed.encode("utf-8"),
                file_name=f"{filename}_fixed.txt",
                mime="text/plain",
            )

            # ファイル保存
            out_path, log_path = save_results(
                fixed, reports, filename
            )
            st.caption(f"💾 保存先: {out_path} / {log_path}")

        except ValueError as e:
            st.error(f"⚠️ {e}")
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {e}")
            logger.error("チェック処理失敗: %s", e)


if __name__ == "__main__":
    main()
