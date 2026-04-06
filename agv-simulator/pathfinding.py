"""重み付きA*アルゴリズムによる経路探索モジュール。"""

import heapq
from typing import Optional

import numpy as np


# 移動方向（上下左右＋斜め）
DIRECTIONS = [
    (-1, 0), (1, 0), (0, -1), (0, 1),
    (-1, -1), (-1, 1), (1, -1), (1, 1),
]


def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    """ユークリッド距離によるヒューリスティック関数。

    Args:
        a: 現在位置 (row, col)
        b: ゴール位置 (row, col)

    Returns:
        推定コスト
    """
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def a_star(
    cost_map: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> Optional[tuple[list[tuple[int, int]], float]]:
    """重み付きA*アルゴリズムで最短経路を計算する。

    Args:
        cost_map: 各セルの移動コスト（2D配列）
        start: スタート位置 (row, col)
        goal: ゴール位置 (row, col)

    Returns:
        (経路のセルリスト, 総コスト) のタプル。経路が見つからない場合はNone
    """
    rows, cols = cost_map.shape

    # 優先度キュー: (f_score, counter, position)
    # counterは同じf_scoreの場合の比較用
    counter = 0
    open_set = [(0.0, counter, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}

    while open_set:
        _, _, current = heapq.heappop(open_set)

        # ゴールに到達
        if current == goal:
            path = _reconstruct_path(came_from, current)
            return path, g_score[current]

        for dr, dc in DIRECTIONS:
            neighbor = (current[0] + dr, current[1] + dc)

            # 範囲外チェック
            if not (0 <= neighbor[0] < rows and 0 <= neighbor[1] < cols):
                continue

            # 斜め移動のコスト係数（√2倍）
            move_cost = 1.414 if (dr != 0 and dc != 0) else 1.0

            # 移動先セルのコストを加算
            tentative_g = g_score[current] + cost_map[neighbor[0], neighbor[1]] * move_cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + heuristic(neighbor, goal)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    return None


def _reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    """ゴールからスタートまでの経路を復元する。

    Args:
        came_from: 各ノードの親ノード辞書
        current: ゴールノード

    Returns:
        スタートからゴールまでの経路リスト
    """
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
