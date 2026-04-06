"""人流データ生成モジュール。時間帯別の人の出現確率マップを生成する。"""

import numpy as np


# 時間帯定義
TIME_PERIODS = {
    0: "朝（7:00-10:00）",
    1: "昼（11:00-14:00）",
    2: "夕方（16:00-19:00）",
}

# グリッドサイズ
GRID_SIZE = 10


def generate_density_map(time_period: int, seed: int = 42) -> np.ndarray:
    """時間帯に応じた人流密度マップを生成する。

    Args:
        time_period: 時間帯（0=朝, 1=昼, 2=夕方）
        seed: 乱数シード

    Returns:
        10×10の密度マップ（0.0〜1.0）
    """
    rng = np.random.RandomState(seed)

    # ベースの密度（全体的な人の多さ）
    base_density = {0: 0.3, 1: 0.5, 2: 0.4}[time_period]

    # ランダムなベースマップ
    density = rng.uniform(0, base_density, (GRID_SIZE, GRID_SIZE))

    # 時間帯ごとに混雑エリアを追加
    if time_period == 0:
        # 朝：入口付近（左側）と通路（中央横ライン）が混雑
        density[4:6, 0:4] += rng.uniform(0.3, 0.6, (2, 4))
        density[0:3, 0:2] += rng.uniform(0.2, 0.4, (3, 2))
    elif time_period == 1:
        # 昼：中央エリア（休憩所想定）が混雑
        density[3:7, 3:7] += rng.uniform(0.3, 0.5, (4, 4))
        density[2:4, 5:8] += rng.uniform(0.2, 0.4, (2, 3))
    else:
        # 夕方：出口付近（右側）と通路が混雑
        density[4:6, 6:10] += rng.uniform(0.3, 0.6, (2, 4))
        density[7:10, 8:10] += rng.uniform(0.2, 0.4, (3, 2))

    # 0.0〜1.0にクリップ
    return np.clip(density, 0.0, 1.0)


def density_to_cost(density: np.ndarray, base_cost: float = 1.0, max_penalty: float = 10.0) -> np.ndarray:
    """密度マップを移動コストマップに変換する。

    Args:
        density: 人流密度マップ（0.0〜1.0）
        base_cost: 基本移動コスト
        max_penalty: 最大ペナルティ倍率

    Returns:
        コストマップ（base_cost 〜 base_cost * max_penalty）
    """
    # 密度が高いほどコストが指数的に増加
    return base_cost + (max_penalty - base_cost) * (density ** 2)
