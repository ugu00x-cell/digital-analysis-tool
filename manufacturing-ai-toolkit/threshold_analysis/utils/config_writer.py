"""
threshold_config.json の出力モジュール

全手法のしきい値を統合してJSON出力する
"""

import json
import logging
from pathlib import Path
from typing import Any

from threshold_analysis.models.threshold_result import ThresholdSet

logger = logging.getLogger(__name__)


def build_config(
    all_thresholds: list[ThresholdSet],
    recommended: dict[str, str],
) -> dict[str, Any]:
    """全手法のしきい値を統合した設定辞書を生成する

    Args:
        all_thresholds: 全データセット×全手法のThresholdSetリスト
        recommended: {データセット名: 推奨手法名}

    Returns:
        設定辞書
    """
    config: dict[str, Any] = {}

    for ts in all_thresholds:
        ds = ts.dataset
        if ds not in config:
            config[ds] = {}

        config[ds][ts.method] = {
            "caution": round(ts.caution, 6),
            "warning": round(ts.warning, 6),
            "danger": round(ts.danger, 6),
            "method_params": ts.metadata,
        }

    # 推奨手法を追加
    for ds, method in recommended.items():
        if ds in config:
            config[ds]["recommended"] = method

    return config


def write_config(
    config: dict[str, Any],
    output_path: Path,
) -> None:
    """設定辞書をJSONファイルに出力する

    Args:
        config: 設定辞書
        output_path: 出力先パス
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(f"しきい値設定ファイルを出力: {output_path}")
