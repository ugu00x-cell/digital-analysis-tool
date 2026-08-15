"""
DCASE 2026 Challenge Task 2 Bearing ベースライン

教師なし異常音検知パイプライン:
  Step1: データ読み込みと可視化
  Step2: メルスペクトログラム特徴抽出
  Step3: オートエンコーダー学習（正常音のみ）
  Step4: 再構成誤差による異常スコア計算
  Step5: AUC-ROC評価

実行: py -X utf8 -m dcase2026_baseline.main
"""

import logging
from pathlib import Path

from dcase2026_baseline.config import OUTPUT_DIR
from dcase2026_baseline.steps.step1_load_visualize import run_step1
from dcase2026_baseline.steps.step2_feature_extract import run_step2_cnn
from dcase2026_baseline.steps.step3_autoencoder import run_step3
from dcase2026_baseline.steps.step4_anomaly_score import run_step4
from dcase2026_baseline.steps.step5_evaluate import run_step5


def _setup_logging() -> None:
    """ログ設定"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(
                OUTPUT_DIR / "baseline.log", encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    """全ステップを順番に実行する"""
    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 70)
    logger.info("DCASE 2026 Task 2 Bearing ベースライン 開始")
    logger.info("=" * 70)

    # Step 1: データ読み込み
    data = run_step1()

    # Step 2: 2Dパッチ抽出（CNN用）
    train_patches = run_step2_cnn(data["train_files"])

    # Step 3: MobileNetV2ベース CNN AE 学習
    model, scaler = run_step3(train_patches)

    # Step 4: 異常スコア計算
    score_data = run_step4(
        model, scaler,
        data["test_normal"], data["test_anomaly"],
    )

    # Step 5: AUC-ROC評価
    metrics = run_step5(score_data)

    # 結果サマリー
    logger.info("=" * 70)
    logger.info("最終結果サマリー")
    logger.info("=" * 70)
    logger.info(f"AUC-ROC:         {metrics['auc_roc']:.4f}")
    logger.info(f"Partial AUC:     {metrics['partial_auc']:.4f}")
    logger.info(f"正常スコア平均:  {metrics['normal_mean']:.6f}")
    logger.info(f"異常スコア平均:  {metrics['anomaly_mean']:.6f}")
    logger.info(f"スコア差(分離度):{metrics['separation']:.6f}")
    logger.info(f"出力先:          {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
