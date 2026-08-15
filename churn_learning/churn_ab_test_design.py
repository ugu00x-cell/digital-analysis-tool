"""
UCI Telco Customer Churn: 擬似A/Bテスト設計とROI試算

高リスクセグメントに対する介入（無料テクニカルサポート等）の
効果検証に必要なサンプルサイズと、ROIの損益分岐点を試算する。
実データでのA/B実施はできないため、パラメータを振った設計シミュレーションとする。
"""

import logging

import pandas as pd
from scipy.stats import norm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- セグメントの前提（churn_risk_segments.pyの出力より） ---
BASELINE_CHURN_RATE = 0.764  # 高リスク上位10%の実解約率
SEGMENT_MONTHLY_CHARGE_USD = 81.1  # 高リスク層の平均月額（原データはUSD建て）
USD_TO_JPY = 150  # 円換算レート（概算）
SEGMENT_MONTHLY_CHARGE = SEGMENT_MONTHLY_CHARGE_USD * USD_TO_JPY  # 円換算後の月額

# --- 検定の前提 ---
ALPHA = 0.05
POWER = 0.80

# --- ROI試算の前提（要調整：実コストが判明したら差し替える） ---
COST_PER_CUSTOMER_PER_MONTH = 500  # 無料サポート提供コスト（円/月/人）
TEST_DURATION_MONTHS = 3  # テスト期間
RETENTION_VALUE_MONTHS = 12  # 1人引き止められた場合の見込み継続月数（保守的に1年）


def required_sample_size(p1: float, mde: float, alpha: float, power: float) -> int:
    """2群比率の差の検定に必要な1群あたりのサンプルサイズを求める"""
    p2 = p1 - mde
    p_pool = (p1 + p2) / 2
    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)

    numerator = (
        z_alpha * (2 * p_pool * (1 - p_pool)) ** 0.5
        + z_beta * (p1 * (1 - p1) + p2 * (1 - p2)) ** 0.5
    ) ** 2
    denominator = (p1 - p2) ** 2
    return int(numerator / denominator) + 1


def roi_simulation(n_per_group: int, mde: float) -> dict:
    """1群あたりのサンプルサイズとMDEから、ROIの損益分岐点を試算する"""
    total_cost = COST_PER_CUSTOMER_PER_MONTH * TEST_DURATION_MONTHS * n_per_group
    expected_retained = n_per_group * mde
    revenue_per_retained = SEGMENT_MONTHLY_CHARGE * RETENTION_VALUE_MONTHS
    expected_revenue_gain = expected_retained * revenue_per_retained
    roi = (expected_revenue_gain - total_cost) / total_cost if total_cost > 0 else float('nan')

    return {
        'n_per_group': n_per_group,
        '介入コスト(円)': total_cost,
        '想定引き止め人数': round(expected_retained, 1),
        '想定売上維持額(円)': round(expected_revenue_gain),
        'ROI(倍)': round(roi, 2),
    }


def breakeven_mde(cost_per_customer_per_month: float, retention_value_per_month: float) -> float:
    """ROI=0となる損益分岐MDEを求める（サンプルサイズnには依存しない）"""
    cost_per_customer_total = cost_per_customer_per_month * TEST_DURATION_MONTHS
    revenue_per_retained = retention_value_per_month * RETENTION_VALUE_MONTHS
    return cost_per_customer_total / revenue_per_retained


def breakeven_sensitivity_table() -> pd.DataFrame:
    """介入コストを変えた場合に損益分岐MDEがどう動くかの感度表を作る"""
    cost_patterns = [200, 500, 1000, 2000, 3000]  # 円/月/人
    rows = []
    for cost in cost_patterns:
        be_mde = breakeven_mde(cost, SEGMENT_MONTHLY_CHARGE)
        rows.append({
            'コスト(円/月/人)': cost,
            '損益分岐MDE(pt)': f"{be_mde:.1%}",
            '現実的か': '楽に黒字' if be_mde < 0.05 else ('要検討' if be_mde < 0.20 else '厳しい'),
        })
    return pd.DataFrame(rows)


def main() -> None:
    """MDEを複数パターン振って、サンプルサイズとROIの感度分析を行う"""
    print("=" * 90)
    print("擬似A/Bテスト設計: サンプルサイズ計算 & ROI感度分析")
    print("=" * 90)
    print(f"ベースライン解約率: {BASELINE_CHURN_RATE:.1%} / α={ALPHA} / 検出力={POWER:.0%}")
    print(f"コスト前提: {COST_PER_CUSTOMER_PER_MONTH}円/月/人 × {TEST_DURATION_MONTHS}ヶ月")
    print(f"引き止め価値: {SEGMENT_MONTHLY_CHARGE}円/月 × {RETENTION_VALUE_MONTHS}ヶ月継続を仮定")
    print("=" * 90)

    mde_patterns = [0.05, 0.10, 0.15, 0.20]  # 解約率を何ポイント下げられると仮定するか
    rows = []
    for mde in mde_patterns:
        n = required_sample_size(BASELINE_CHURN_RATE, mde, ALPHA, POWER)
        result = roi_simulation(n, mde)
        result['MDE(pt)'] = f"{mde:.0%}"
        rows.append(result)
        logger.info(f"MDE={mde:.0%}: 必要n={n}, ROI={result['ROI(倍)']}")

    result_df = pd.DataFrame(rows)[['MDE(pt)', 'n_per_group', '介入コスト(円)', '想定引き止め人数', '想定売上維持額(円)', 'ROI(倍)']]
    print("\n【MDE別 サンプルサイズ & ROI感度分析】")
    print(result_df.to_string(index=False))

    be_mde = breakeven_mde(COST_PER_CUSTOMER_PER_MONTH, SEGMENT_MONTHLY_CHARGE)
    logger.info(f"損益分岐MDE: {be_mde:.2%}（現在のコスト前提: {COST_PER_CUSTOMER_PER_MONTH}円/月）")
    print(f"\n【損益分岐点】現在のコスト前提でのROI=0となるMDE: {be_mde:.2%}")
    print("→ これより大きい解約率改善が見込めれば黒字、下回れば赤字")

    print("\n【コスト別 損益分岐MDE感度分析】")
    print(breakeven_sensitivity_table().to_string(index=False))
    print("=" * 90)


if __name__ == '__main__':
    main()
