"""
全ステージ統合比較スクリプト

Stage1(統計) / Stage2(ML) / Stage3(DL) の結果を横並び比較し、
データセットごとに最適手法を選定する
"""

import logging
from pathlib import Path

from threshold_analysis.models.threshold_result import (
    EvaluationResult,
    ThresholdSet,
)
from threshold_analysis.stage1_statistical import run_stage1_all
from threshold_analysis.stage2_ml_evaluate import run_stage2_all
from threshold_analysis.utils.config_writer import build_config, write_config
from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    extract_rms,
    load_dataset,
)
from threshold_analysis.utils.evaluation import (
    compare_methods,
    evaluate_thresholds,
    select_recommended,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("threshold_analysis")


def _run_stage3_safe() -> dict | None:
    """Stage3を実行する（torch未インストール時はスキップ）"""
    try:
        from threshold_analysis.stage3_lstm_ae_evaluate import run_stage3_all
        return run_stage3_all()
    except ImportError:
        logger.warning("torchが未インストールのためStage3をスキップします")
        return None


def run_all_stages() -> tuple[
    list[ThresholdSet], list[EvaluationResult],
]:
    """全ステージ x 全データセットを実行する

    Returns:
        (全ThresholdSetリスト, 全EvaluationResultリスト)
    """
    all_ts: list[ThresholdSet] = []
    all_ev: list[EvaluationResult] = []

    # --- Stage1: 統計ベース ---
    logger.info("=" * 60)
    logger.info("Stage1: 統計ベースしきい値")
    logger.info("=" * 60)
    stage1_results = run_stage1_all()

    for ds in ALL_DATASETS:
        normal_df, full_df = load_dataset(ds)
        normal_rms = extract_rms(normal_df, ds)
        full_rms = extract_rms(full_df, ds)
        is_labeled = ds == "cwru"

        for ts in stage1_results[ds]:
            ev = evaluate_thresholds(ts, normal_rms, full_rms, is_labeled)
            all_ts.append(ts)
            all_ev.append(ev)

    # --- Stage2: 機械学習 ---
    logger.info("=" * 60)
    logger.info("Stage2: 機械学習ベースしきい値")
    logger.info("=" * 60)
    stage2_results = run_stage2_all()

    for ds in ALL_DATASETS:
        for ts, ev in stage2_results[ds]:
            all_ts.append(ts)
            all_ev.append(ev)

    # --- Stage3: ディープラーニング ---
    logger.info("=" * 60)
    logger.info("Stage3: LSTM-AutoEncoderベースしきい値")
    logger.info("=" * 60)
    stage3_results = _run_stage3_safe()

    if stage3_results is not None:
        for ds in ALL_DATASETS:
            ts, ev = stage3_results[ds]
            all_ts.append(ts)
            all_ev.append(ev)

    return all_ts, all_ev


def print_comparison_report(
    comparison_df: "pd.DataFrame",  # noqa: F821
    recommended: dict[str, str],
) -> None:
    """比較レポートをコンソール出力する"""
    import pandas as pd

    print("\n" + "=" * 90)
    print("  3段階しきい値 手法比較レポート")
    print("=" * 90)

    for ds in ALL_DATASETS:
        ds_df = comparison_df[comparison_df["dataset"] == ds]
        rec = recommended.get(ds, "")
        print(f"\n--- {ds.upper()} (推奨: {rec}) ---")
        # 推奨手法にマークをつける
        display = ds_df.copy()
        display["rec"] = display["method"].apply(
            lambda m: " *" if m == rec else "",
        )
        print(
            display.to_string(
                index=False,
                columns=[
                    "method", "sigma_caution", "false_alarm_%",
                    "detection_%", "first_detect_%", "rec",
                ],
            ),
        )

    print("\n" + "=" * 90)
    print("  * = 推奨手法 (誤報率<5% かつ 検出率最大)")
    print("=" * 90)


def main() -> None:
    """メイン処理"""
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(
                OUTPUT_DIR / "app.log", encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )

    logger.info("3段階しきい値 統合比較 開始")

    # 全ステージ実行
    all_ts, all_ev = run_all_stages()

    # 比較テーブル生成
    comparison_df = compare_methods(all_ev)

    # データセットごとに推奨手法を選定
    recommended = {}
    for ds in ALL_DATASETS:
        ds_evals = [ev for ev in all_ev if ev.dataset == ds]
        recommended[ds] = select_recommended(ds_evals)
        logger.info(f"[推奨] {ds}: {recommended[ds]}")

    # threshold_config.json出力
    config = build_config(all_ts, recommended)
    write_config(config, OUTPUT_DIR / "threshold_config.json")

    # 比較レポート出力
    print_comparison_report(comparison_df, recommended)

    # CSVも出力
    csv_path = OUTPUT_DIR / "comparison_report.csv"
    comparison_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info(f"比較レポートCSV出力: {csv_path}")

    logger.info("3段階しきい値 統合比較 完了")


if __name__ == "__main__":
    main()
