---
title: "製造業のAGV経路最適化をPythonで実装してみた"
emoji: "🤖"
type: "tech"
topics: ["Python", "製造業", "AGV", "アルゴリズム", "Streamlit"]
published: false
---

## はじめに

きっかけはイオンの清掃ロボットだった。

通路を自動で掃除しているロボットが、人とすれ違うたびに停止し、数秒待ってから動き出す。1回の停止は数秒でも、フロア全体で見れば相当なタイムロスになっているはずだ。

これ、工場のAGV（無人搬送車）でもまったく同じことが起きている。品質管理部で10年働いてきた経験上、AGVが人を検知して停止→再起動を繰り返すロスは、現場では「仕方ないもの」として見過ごされがちだ。

でも「止まってから考える」のではなく「止まらなくて済むルートを最初から選ぶ」ことはできないだろうか。時間帯ごとの人の流れを予測して、混雑エリアを避ける経路を計算する——そんなシミュレーターをPythonで作ってみた。

## 課題の整理

工場内のAGVが抱える典型的な問題を整理する。

**現状：事後対応型の回避**
- 人を検知 → 停止 → 一定時間待機 → 再起動 or 迂回
- 停止のたびに搬送サイクルタイムが悪化
- 朝の出勤ラッシュ、昼休み、夕方の退勤時に停止頻度が跳ね上がる

**あるべき姿：予測型の経路選択**
- 時間帯ごとの人流パターンを事前に把握
- 混雑エリアのコストを高く設定し、最初から避ける経路を計算
- 停止回数を減らし、搬送効率を上げる

つまり「人がいたら止まる」から「人がいそうな場所を通らない」への転換だ。

## 実装方針

以下の構成で実装した。

- **10×10のグリッドマップ**で工場フロアを表現
- **時間帯別の人流密度**（朝・昼・夕方の3パターン）を確率的に生成
- **重み付きA\*アルゴリズム**で、人が多いセルほどコストが高くなる経路計算
- **Streamlit**でヒートマップと経路をリアルタイム可視化

ファイル構成は3つに分けた。

```
agv-simulator/
├── app.py            # Streamlit可視化
├── pathfinding.py    # 重み付きA*アルゴリズム
└── map_generator.py  # 時間帯別の人流データ生成
```

## コード解説

### map_generator.py：時間帯別の人流データ

時間帯ごとに混雑パターンが異なる密度マップを生成する。密度は0.0〜1.0の範囲で、これを移動コストに変換する。

```python
def generate_density_map(time_period: int, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    base_density = {0: 0.3, 1: 0.5, 2: 0.4}[time_period]
    density = rng.uniform(0, base_density, (GRID_SIZE, GRID_SIZE))

    if time_period == 0:
        # 朝：入口付近（左側）が混雑
        density[4:6, 0:4] += rng.uniform(0.3, 0.6, (2, 4))
    elif time_period == 1:
        # 昼：中央エリア（休憩所想定）が混雑
        density[3:7, 3:7] += rng.uniform(0.3, 0.5, (4, 4))
    else:
        # 夕方：出口付近（右側）が混雑
        density[4:6, 6:10] += rng.uniform(0.3, 0.6, (2, 4))

    return np.clip(density, 0.0, 1.0)
```

ポイントは密度からコストへの変換。二乗関数で「少し人がいる程度ならほぼ影響なし、密集すると急激にコスト増」という現実に近い特性を表現している。

```python
def density_to_cost(density, base_cost=1.0, max_penalty=10.0):
    return base_cost + (max_penalty - base_cost) * (density ** 2)
```

### pathfinding.py：重み付きA*アルゴリズム

通常のA\*に「セルごとの移動コスト」を組み込んだ版。上下左右＋斜め8方向の移動に対応し、斜め移動は√2倍のコストがかかる。

```python
def a_star(cost_map, start, goal):
    open_set = [(0.0, 0, start)]
    g_score = {start: 0.0}

    while open_set:
        _, _, current = heapq.heappop(open_set)
        if current == goal:
            return _reconstruct_path(came_from, current), g_score[current]

        for dr, dc in DIRECTIONS:
            neighbor = (current[0] + dr, current[1] + dc)
            move_cost = 1.414 if (dr != 0 and dc != 0) else 1.0
            tentative_g = g_score[current] + cost_map[neighbor] * move_cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                heapq.heappush(open_set, (tentative_g + heuristic(neighbor, goal), ...))
```

ヒューリスティック関数にはユークリッド距離を使用。これにより斜め移動も自然に評価される。

### app.py：Streamlitで可視化

左に人流密度ヒートマップ＋AGV経路（赤線）、右にセルごとの移動コストマップを並べて表示する。サイドバーで時間帯・スタート/ゴール位置・混雑ペナルティ倍率を調整できる。

```python
# ヒートマップ + 経路の描画
im1 = ax1.imshow(density, cmap="YlOrRd", vmin=0, vmax=1)
ax1.plot(path_cols, path_rows, "-o", linewidth=2.5, markersize=5, color="red")
ax1.plot(start[1], start[0], "s", color="lime", markersize=14)   # スタート
ax1.plot(goal[1], goal[0], "*", color="blue", markersize=18)     # ゴール
```

人がいない場合の理想コストとの差分を「タイムロス」として数値化し、人流による影響を定量的に把握できるようにした。

## デモ結果

時間帯を切り替えると、混雑エリアの変化に応じてAGVの経路が動的に変わる。

- **朝（7:00-10:00）**：左側の入口付近を避け、マップ上部を迂回する経路を選択
- **昼（11:00-14:00）**：中央の休憩エリアを大きく避け、外周を通るルートに変化
- **夕方（16:00-19:00）**：右側の出口付近を避け、マップ下部経由でゴールに到達

タイムロスは昼が最も大きく、中央に広がる混雑の影響範囲が広いことがわかる。これは実際の工場でも昼休み前後の搬送効率低下として体感されている事象と一致する。

## 今後の展望

今回は静的な確率モデルだが、発展の余地は大きい。

- **実センサーデータとの統合**：M5StickCのToFセンサーで実際の人流を計測し、密度マップをリアルタイム更新
- **複数AGVへの拡張**：AGV同士の干渉を考慮した協調経路計画（MAPF問題）
- **予知保全との組み合わせ**：搬送ルートの偏りから床面の摩耗予測、AGVバッテリー消耗の最適化
- **強化学習の導入**：時間帯パターンの自動学習による適応的経路選択

## まとめ

「人がいたら止まる」を「人がいそうな場所を最初から避ける」に変えるだけで、AGVの搬送効率は改善できる。今回の実装はシンプルな10×10グリッドだが、考え方は実ラインにそのまま応用できる。

製造業の現場には、こういう「ちょっとした最適化」のネタが転がっている。清掃ロボットの挙動を見て「これ工場でも同じだな」と思えるのは、現場を知っているエンジニアの強みだ。

現実ほど面白いデータセットはないし、現場ほど面白いゲームフィールドもない。
