"""
UCI Telco Customer Churn: 特徴量重要度の算出

Optunaで最適化したLightGBMパラメータでモデルを学習し、
特徴量重要度（gain基準・split基準の両方）を表示する。
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

# 前回のOptuna最適化結果（churn_tune_optuna.py実行結果より）
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


def build_importance_table(
    X_train: pd.DataFrame, y_train: pd.Series, feature_names: list[str]
) -> pd.DataFrame:
    """gain基準・split基準それぞれでモデルを学習し、重要度を1つの表にまとめる"""
    split_model = lgb.LGBMClassifier(**BEST_PARAMS, random_state=42, verbose=-1, importance_type='split')
    split_model.fit(X_train, y_train)

    gain_model = lgb.LGBMClassifier(**BEST_PARAMS, random_state=42, verbose=-1, importance_type='gain')
    gain_model.fit(X_train, y_train)

    df = pd.DataFrame({
        'feature': feature_names,
        'importance_split': split_model.feature_importances_,
        'importance_gain': gain_model.feature_importances_,
    })
    df['importance_gain_pct'] = df['importance_gain'] / df['importance_gain'].sum() * 100
    return df.sort_values('importance_gain', ascending=False).reset_index(drop=True)


def main() -> None:
    """モデルを学習し、特徴量重要度の表を表示する"""
    print("=" * 80)
    print("LightGBM（Optuna最適化後）特徴量重要度")
    print("=" * 80)

    df = load_data(DATA_PATH)
    X, y = preprocess(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    result_df = build_importance_table(X_train, y_train, list(X_train.columns))

    print("\n【特徴量重要度（gain基準・降順）】")
    print(result_df.to_string(index=False, float_format='%.2f'))
    print("=" * 80)

    logger.info(f"重要度トップ3: {result_df['feature'].head(3).tolist()}")


if __name__ == '__main__':
    main()
