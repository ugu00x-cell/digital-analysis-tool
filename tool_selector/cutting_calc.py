"""
切削条件計算エンジン
切削理論式に基づき、推奨切削条件・工具寿命・加工時間を算出する
"""

import logging
import math
from dataclasses import dataclass
from tool_db import MATERIALS, TOOL_DB

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


@dataclass
class CuttingCondition:
    """算出された切削条件を格納するデータクラス"""
    tool: dict               # 選定工具情報
    tool_diameter: float      # 使用工具径 [mm]
    spindle_rpm: int          # 主軸回転数 [rpm]
    cutting_speed: float      # 切削速度 [m/min]
    feed_per_tooth: float     # 1刃あたり送り [mm/tooth]
    feed_rate: float          # テーブル送り速度 [mm/min]
    axial_depth: float        # 軸方向切込み量 ap [mm]
    radial_depth: float       # 径方向切込み量 ae [mm]
    n_passes: int             # 加工パス回数
    estimated_life_min: float # 予想工具寿命 [分]
    mrr: float                # 材料除去率 MRR [cm³/min]
    notes: list[str]          # 注意事項


def select_tool_diameter(target_diameter: float, tool: dict) -> float | None:
    """加工径に最適な工具径を選定する（加工径以下の最大径）"""
    # エンドミルは加工径以下の工具径を使う
    candidates = [d for d in tool["diameters"] if d <= target_diameter]
    if not candidates:
        return None
    return max(candidates)


def find_best_tools(
    material_key: str, target_diameter: float
) -> list[tuple[dict, float]]:
    """材料と加工径に適合する工具を検索し、工具径と共に返す"""
    results: list[tuple[dict, float]] = []
    for tool in TOOL_DB:
        # 材料適合チェック
        if material_key not in tool["materials"]:
            continue
        # 工具径の選定
        d = select_tool_diameter(target_diameter, tool)
        if d is None:
            continue
        results.append((tool, d))

    # 専用工具を優先（対応材料が少ない＝専用度が高い）
    results.sort(key=lambda x: len(x[0]["materials"]))
    return results


def calc_spindle_rpm(Vc: float, diameter: float) -> int:
    """切削速度 [m/min] と工具径 [mm] から主軸回転数を算出する
    N = (1000 × Vc) / (π × D)
    """
    rpm = (1000 * Vc) / (math.pi * diameter)
    return int(rpm)


def calc_cutting_speed(rpm: int, diameter: float) -> float:
    """回転数と工具径から実際の切削速度を逆算する
    Vc = (π × D × N) / 1000
    """
    return (math.pi * diameter * rpm) / 1000


def calc_feed_rate(fz: float, flutes: int, rpm: int) -> float:
    """テーブル送り速度を算出する
    Vf = fz × z × N
    """
    return fz * flutes * rpm


def estimate_tool_life(
    tool: dict, material: dict, Vc_actual: float
) -> float:
    """テイラーの工具寿命式に基づき工具寿命を推定する
    簡易版: T = T_base × life_factor × (Vc_ref / Vc_actual)^n
    n = 0.25（超硬工具の典型値）
    """
    # 基準切削速度（推奨範囲の中央値）
    Vc_ref = sum(material["Vc_range"]) / 2
    # テイラーの指数（超硬工具）
    n = 0.25
    # 寿命 [分]
    life = (
        tool["life_base_min"]
        * material["life_factor"]
        * (Vc_ref / max(Vc_actual, 1)) ** (1 / n)
    )
    return max(life, 5.0)  # 最低5分


def calculate_conditions(
    material_name: str,
    target_diameter: float,
    depth: float,
    max_spindle_rpm: int,
) -> list[CuttingCondition]:
    """入力条件から最適な切削条件を計算する"""
    logger.info(f"計算開始: {material_name}, 加工径{target_diameter}mm, 深さ{depth}mm")

    # 材料データ取得
    material = MATERIALS.get(material_name)
    if material is None:
        logger.error(f"材料が見つかりません: {material_name}")
        return []

    # 適合工具を検索
    tool_list = find_best_tools(material["key"], target_diameter)
    if not tool_list:
        logger.warning("適合する工具が見つかりません")
        return []

    results: list[CuttingCondition] = []

    for tool, tool_d in tool_list:
        # 推奨切削速度（材料の推奨範囲の中央値 × 工具ブースト）
        Vc_mid = sum(material["Vc_range"]) / 2 * tool["Vc_boost"]

        # 主軸回転数を算出
        rpm = calc_spindle_rpm(Vc_mid, tool_d)

        # 主軸最大回転数で制限
        rpm = min(rpm, max_spindle_rpm)

        # 実際の切削速度を逆算
        Vc_actual = calc_cutting_speed(rpm, tool_d)

        # 1刃あたり送り量（材料の推奨範囲の中央値を基準に径補正）
        fz_base = sum(material["fz_range"]) / 2
        # 小径工具は送り量を下げる（径10mm基準で線形補正）
        fz = fz_base * min(tool_d / 10.0, 1.0)
        fz = max(fz, material["fz_range"][0])

        # テーブル送り速度
        feed_rate = calc_feed_rate(fz, tool["flutes"], rpm)

        # 軸方向切込み量（工具径に対する比率）
        ap_ratio = sum(material["ap_ratio"]) / 2
        ap = tool_d * ap_ratio
        # 加工深さが浅い場合は1パスで加工
        ap = min(ap, depth)

        # 径方向切込み量
        ae_ratio = sum(material["ae_ratio"]) / 2
        ae = tool_d * ae_ratio

        # パス回数
        n_passes = max(1, math.ceil(depth / ap))

        # 工具寿命推定
        life = estimate_tool_life(tool, material, Vc_actual)

        # 材料除去率 MRR [cm³/min] = ap × ae × Vf / 1000
        mrr = (ap * ae * feed_rate) / 1000

        # 注意事項（材料共通 + 条件別）
        notes = list(material["notes"])
        if rpm >= max_spindle_rpm * 0.95:
            notes.append("⚠ 主軸回転数が上限に近いです。切削速度が理想より低い可能性があります。")
        if n_passes > 5:
            notes.append(f"加工深さが深いため{n_passes}パスになります。工具突き出し長さに注意。")
        if tool_d < target_diameter * 0.3:
            notes.append("工具径が加工径に対して小さいため、加工時間が長くなります。")

        condition = CuttingCondition(
            tool=tool,
            tool_diameter=tool_d,
            spindle_rpm=rpm,
            cutting_speed=round(Vc_actual, 1),
            feed_per_tooth=round(fz, 4),
            feed_rate=round(feed_rate, 1),
            axial_depth=round(ap, 2),
            radial_depth=round(ae, 2),
            n_passes=n_passes,
            estimated_life_min=round(life, 1),
            mrr=round(mrr, 2),
            notes=notes,
        )
        results.append(condition)

    logger.info(f"計算完了: {len(results)}件の工具候補")
    return results
