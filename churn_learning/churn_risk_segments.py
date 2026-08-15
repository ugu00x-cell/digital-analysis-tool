"""
UCI Telco Customer Churn: リスクセグメント分析

Optuna最適化済みLightGBMで全顧客の解約確率を算出し、
リスク上位層の特徴を集計して施策提案の材料を作る。
"""

import logging

import lightgbm as lgb
import pandas as pd
from sklearn.model_selection import train_test_split

from churn_predict import DATA_PATH, load_data, preprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BEST_PARAMS = {
    'n_estimators': 300,
    'num_leaves': 8,
    'max_depth': 4,
    'learning_rate': 0.015884355738310124,
    'min_child_samples': 38,
    'feature_fraction': 0.5011759794132387,
    'bagging_fraction': 0.7447875537921593,
    'bagging_freq': 1,
    'lambda_l1': 3.239171957619787e-06,
    'lambda_l2': 3.737967554103943e-08,
}

TOP_RISK_PCT = 0.10  # 上位何%を「高リスク層」とみなすか


def score_customers(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame,
) -> pd.Series:
    """テストデータ全件に解約確率スコアを付与する"""
    model = lgb.LGBMClassifier(**BEST_PARAMS, random_state=42, verbose=-1)
    model.fit(X_train, y_train)
    return pd.Series(model.predict_proba(X_test)[:, 1], index=X_test.index, name='churn_proba')


def summarize_segment(df_raw: pd.DataFrame, label: str) -> pd.Series:
    """セグメント内の主要属性を集計する"""
    return pd.Series({
        '件数': len(df_raw),
        '実際の解約率(%)': (df_raw['Churn'] == 'Yes').mean() * 100,
        '平均tenure(月)': df_raw['tenure'].mean(),
        '平均MonthlyCharges': df_raw['MonthlyCharges'].mean(),
        'Month-to-month比率(%)': (df_raw['Contract'] == 'Month-to-month').mean() * 100,
        'OnlineSecurity未加入率(%)': (df_raw['OnlineSecurity'] == 'No').mean() * 100,
        'TechSupport未加入率(%)': (df_raw['TechSupport'] == 'No').mean() * 100,
    }, name=label)


def main() -> None:
    """高リスク層と全体を比較し、施策提案の材料となる表を出力する"""
    print("=" * 80)
    print(f"リスクセグメント分析（上位{int(TOP_RISK_PCT * 100)}%を高リスク層とする）")
    print("=" * 80)

    df = load_data(DATA_PATH)
    X, y = preprocess(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    df_test_raw = df.loc[X_test.index]

    proba = score_customers(X_train, y_train, X_test)
    n_top = int(len(proba) * TOP_RISK_PCT)
    top_risk_idx = proba.sort_values(ascending=False).head(n_top).index

    logger.info(f"高リスク層: {n_top}件 / 全体{len(proba)}件")

    all_summary = summarize_segment(df_test_raw, '全体（テストデータ）')
    top_summary = summarize_segment(df_test_raw.loc[top_risk_idx], f'高リスク上位{int(TOP_RISK_PCT * 100)}%')

    result = pd.concat([all_summary, top_summary], axis=1)
    print("\n【全体 vs 高リスク層の比較】")
    print(result.to_string(float_format='%.1f'))
    print("=" * 80)


if __name__ == '__main__':
    main()
