"""
しきい値・評価結果を格納するデータクラス

全ステージで共通のデータ構造を定義する
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ThresholdSet:
    """1データセット・1手法のしきい値セット"""

    method: str       # "fixed_ratio", "sigma", "percentile", "mad", "if", "ocsvm", "lstm_ae"
    dataset: str      # "cwru", "nasa", "xjtu_sy", "femto"
    caution: float    # 注意しきい値
    warning: float    # 警告しきい値
    danger: float     # 危険しきい値
    metadata: dict[str, Any] = field(default_factory=dict)  # 手法固有の追加情報


@dataclass
class EvaluationResult:
    """しきい値の評価結果"""

    method: str                    # 手法名
    dataset: str                   # データセット名
    false_alarm_rate: float        # 正常データでの誤報率(%)
    detection_rate_late: float     # 後半区間での検出率(%)
    sigma_caution: float           # cautionが正常平均から何σか
    sigma_warning: float           # warningが正常平均から何σか
    sigma_danger: float            # dangerが正常平均から何σか
    first_detection_pct: float     # 初回検出の寿命%地点（-1=該当なし）
