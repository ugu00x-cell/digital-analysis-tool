"""
Kaggle Playground Series S6E3 - Customer Churn Prediction (v2 final)
Optunaで見つけた最良パラメータで最終学習のみ実行する軽量版
"""

import logging
import gc
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# サービス系カラム
SERVICE_COLS = [
    'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
    'TechSupport', 'StreamingTV', 'StreamingMovies',
]

# カテゴリ変数カラム
CAT_COLS = [
    'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
    'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
    'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
    'PaperlessBilling', 'PaymentMethod',
]


def load_data(train_path: str, test_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """学習データとテストデータを読み込む"""
    logger.info("データ読み込み開始")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    logger.info(f"train: {train.shape}, test: {test.shape}")
    return train, test


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """特徴量エンジニアリング：交互作用・比率・集約特徴量を追加"""
    # 使用量×単価（tenure × MonthlyCharges）
    df['tenure_x_monthly'] = df['tenure'] * df['MonthlyCharges']

    # 月平均支払額（TotalCharges / tenure）※ tenure=0 の新規顧客はMonthlyChargesで代替
    df['avg_charge_per_month'] = np.where(
        df['tenure'] > 0,
        df['TotalCharges'] / df['tenure'],
        df['MonthlyCharges']
    )

    # 月あたり平均支出（tenure+1で割る版も残す）
    df['avg_monthly_spend'] = df['TotalCharges'] / (df['tenure'] + 1)

    # 直近の支出比率
    df['monthly_ratio'] = df['MonthlyCharges'] / (df['TotalCharges'] + 1)

    # Contract を数値化（Month-to-month=0, One year=1, Two year=2）
    contract_map = {'Month-to-month': 0, 'One year': 1, 'Two year': 2}
    df['contract_num'] = df['Contract'].map(contract_map)

    # サービス加入数の合計（Yes の数をカウント）
    df['service_count'] = (df[SERVICE_COLS] == 'Yes').sum(axis=1)

    # 高齢者×契約形態（既存）
    df['senior_x_contract'] = (
        df['SeniorCitizen'].astype(str) + '_' + df['Contract'].astype(str)
    )
    return df


def preprocess(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, list[str], list[str]]:
    """前処理：特徴量追加 + カテゴリをcategory型に変換"""
    logger.info("前処理開始")

    y = (train['Churn'] == 'Yes').astype(int).values

    # TotalChargesの型変換
    for df in [train, test]:
        if df['TotalCharges'].dtype == object:
            df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')

    # 特徴量追加
    train = add_features(train)
    test = add_features(test)

    all_cat_cols = CAT_COLS + ['senior_x_contract']
    feature_cols = [c for c in train.columns if c not in ['id', 'Churn']]

    # カテゴリ変数をcategory型に変換
    for col in all_cat_cols:
        combined_cat = pd.CategoricalDtype(
            categories=pd.concat([train[col], test[col]]).unique()
        )
        train[col] = train[col].astype(combined_cat)
        test[col] = test[col].astype(combined_cat)

    X_train = train[feature_cols].copy()
    X_test = test[feature_cols].copy()

    # 欠損値を中央値で埋める
    num_cols = X_train.select_dtypes(include='number').columns
    for col in num_cols:
        if X_train[col].isnull().any():
            median_val = X_train[col].median()
            X_train[col] = X_train[col].fillna(median_val)
            X_test[col] = X_test[col].fillna(median_val)

    cat_feature_names = [c for c in all_cat_cols if c in feature_cols]
    logger.info(f"特徴量数: {len(feature_cols)}（うちカテゴリ: {len(cat_feature_names)}）")
    logger.info("前処理完了")
    return X_train, y, X_test, feature_cols, cat_feature_names


def train_final(
    X_train: pd.DataFrame,
    y: np.ndarray,
    X_test: pd.DataFrame,
    cat_features: list[str],
    n_splits: int = 5,
) -> np.ndarray:
    """Optunaの最良パラメータで5-Fold学習"""
    logger.info(f"最終学習開始（{n_splits}-Fold CV）")

    # Optunaで最良だったパラメータ（Trial 45: AUC=0.916304, 3-Fold）
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'verbose': -1,
        'n_jobs': -1,
        'random_state': 42,
        'learning_rate': 0.03,
        'num_leaves': 48,
        'max_depth': 8,
        'min_child_samples': 30,
        'subsample': 0.75,
        'colsample_bytree': 0.7,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
    }

    oof_preds = np.zeros(len(X_train))
    test_preds = np.zeros(len(X_test))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_train, y)):
        logger.info(f"--- Fold {fold + 1}/{n_splits} ---")

        dtrain = lgb.Dataset(
            X_train.iloc[train_idx], label=y[train_idx],
            categorical_feature=cat_features
        )
        dval = lgb.Dataset(
            X_train.iloc[val_idx], label=y[val_idx],
            categorical_feature=cat_features, reference=dtrain
        )

        model = lgb.train(
            params, dtrain, num_boost_round=2000, valid_sets=[dval],
            callbacks=[lgb.early_stopping(100), lgb.log_evaluation(200)],
        )

        oof_preds[val_idx] = model.predict(X_train.iloc[val_idx])
        fold_auc = roc_auc_score(y[val_idx], oof_preds[val_idx])
        logger.info(f"Fold {fold + 1} AUC: {fold_auc:.6f}")

        test_preds += model.predict(X_test) / n_splits

        # メモリ解放
        del dtrain, dval, model
        gc.collect()

    overall_auc = roc_auc_score(y, oof_preds)
    logger.info(f"Overall CV AUC: {overall_auc:.6f}")
    return test_preds


def create_submission(
    test_ids: pd.Series, predictions: np.ndarray, output_path: str
) -> None:
    """submission.csvを作成"""
    submission = pd.DataFrame({'id': test_ids, 'Churn': predictions})
    submission.to_csv(output_path, index=False)
    logger.info(f"submission保存完了: {output_path} ({len(submission)}行)")


def main() -> None:
    """メイン処理"""
    train, test = load_data('data/train.csv', 'data/test.csv')
    X_train, y, X_test, feature_cols, cat_features = preprocess(train, test)

    # メモリ節約：元データ解放
    test_ids = test['id'].copy()
    del train
    gc.collect()

    test_preds = train_final(X_train, y, X_test, cat_features)
    create_submission(test_ids, test_preds, 'submission_v3.csv')
    logger.info("全処理完了！")


if __name__ == '__main__':
    main()
