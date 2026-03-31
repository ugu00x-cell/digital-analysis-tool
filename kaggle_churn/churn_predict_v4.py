"""
Kaggle Playground Series S6E3 - Customer Churn Prediction (v4)
LightGBM(GPU) + XGBoost(GPU) アンサンブル
"""

import logging
import gc
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import LabelEncoder

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
    """特徴量エンジニアリング"""
    # 使用量×単価
    df['tenure_x_monthly'] = df['tenure'] * df['MonthlyCharges']

    # 月平均支払額（tenure=0はMonthlyChargesで代替）
    df['avg_charge_per_month'] = np.where(
        df['tenure'] > 0,
        df['TotalCharges'] / df['tenure'],
        df['MonthlyCharges']
    )

    # 月あたり平均支出
    df['avg_monthly_spend'] = df['TotalCharges'] / (df['tenure'] + 1)

    # 直近の支出比率
    df['monthly_ratio'] = df['MonthlyCharges'] / (df['TotalCharges'] + 1)

    # Contract数値化
    contract_map = {'Month-to-month': 0, 'One year': 1, 'Two year': 2}
    df['contract_num'] = df['Contract'].map(contract_map)

    # サービス加入数
    df['service_count'] = (df[SERVICE_COLS] == 'Yes').sum(axis=1)

    # 高齢者×契約形態
    df['senior_x_contract'] = (
        df['SeniorCitizen'].astype(str) + '_' + df['Contract'].astype(str)
    )
    return df


def preprocess(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    """前処理：LightGBM用(category型)とXGBoost用(LabelEncoded)の両方を返す"""
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

    # --- XGBoost用：Label Encoding版を先に作る ---
    train_xgb = train[feature_cols].copy()
    test_xgb = test[feature_cols].copy()
    for col in all_cat_cols:
        le = LabelEncoder()
        combined = pd.concat([train_xgb[col], test_xgb[col]]).astype(str)
        le.fit(combined)
        train_xgb[col] = le.transform(train_xgb[col].astype(str))
        test_xgb[col] = le.transform(test_xgb[col].astype(str))

    # --- LightGBM用：category型版 ---
    for col in all_cat_cols:
        combined_cat = pd.CategoricalDtype(
            categories=pd.concat([train[col], test[col]]).unique()
        )
        train[col] = train[col].astype(combined_cat)
        test[col] = test[col].astype(combined_cat)

    X_train_lgb = train[feature_cols].copy()
    X_test_lgb = test[feature_cols].copy()

    # 欠損値を中央値で埋める（全データフレーム共通）
    num_cols = X_train_lgb.select_dtypes(include='number').columns
    for col in num_cols:
        if X_train_lgb[col].isnull().any():
            median_val = X_train_lgb[col].median()
            X_train_lgb[col] = X_train_lgb[col].fillna(median_val)
            X_test_lgb[col] = X_test_lgb[col].fillna(median_val)
            train_xgb[col] = train_xgb[col].fillna(median_val)
            test_xgb[col] = test_xgb[col].fillna(median_val)

    cat_feature_names = [c for c in all_cat_cols if c in feature_cols]
    logger.info(f"特徴量数: {len(feature_cols)}（うちカテゴリ: {len(cat_feature_names)}）")
    logger.info("前処理完了")

    # LightGBM用データ、XGBoost用データの両方を返す
    return X_train_lgb, y, X_test_lgb, train_xgb, test_xgb, cat_feature_names


def train_lgbm(
    X_train: pd.DataFrame,
    y: np.ndarray,
    X_test: pd.DataFrame,
    cat_features: list[str],
    n_splits: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """LightGBM GPU版で5-Fold学習"""
    logger.info("=== LightGBM (GPU) 学習開始 ===")

    params = {
        'objective': 'binary',
        'metric': 'auc',
        'device': 'gpu',
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
        logger.info(f"LGB Fold {fold + 1}/{n_splits}")
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
        logger.info(f"LGB Fold {fold + 1} AUC: {roc_auc_score(y[val_idx], oof_preds[val_idx]):.6f}")
        test_preds += model.predict(X_test) / n_splits
        del dtrain, dval, model
        gc.collect()

    auc = roc_auc_score(y, oof_preds)
    logger.info(f"LightGBM Overall CV AUC: {auc:.6f}")
    return oof_preds, test_preds


def train_xgb_model(
    X_train: pd.DataFrame,
    y: np.ndarray,
    X_test: pd.DataFrame,
    n_splits: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """XGBoost GPU版で5-Fold学習"""
    logger.info("=== XGBoost (GPU) 学習開始 ===")

    params = {
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'device': 'cuda',
        'tree_method': 'hist',
        'learning_rate': 0.03,
        'max_depth': 8,
        'min_child_weight': 30,
        'subsample': 0.75,
        'colsample_bytree': 0.7,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'random_state': 42,
    }

    oof_preds = np.zeros(len(X_train))
    test_preds = np.zeros(len(X_test))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_train, y)):
        logger.info(f"XGB Fold {fold + 1}/{n_splits}")
        dtrain = xgb.DMatrix(X_train.iloc[train_idx], label=y[train_idx])
        dval = xgb.DMatrix(X_train.iloc[val_idx], label=y[val_idx])
        dtest = xgb.DMatrix(X_test)

        model = xgb.train(
            params, dtrain, num_boost_round=2000,
            evals=[(dval, 'val')],
            early_stopping_rounds=100,
            verbose_eval=200,
        )
        oof_preds[val_idx] = model.predict(dval)
        logger.info(f"XGB Fold {fold + 1} AUC: {roc_auc_score(y[val_idx], oof_preds[val_idx]):.6f}")
        test_preds += model.predict(dtest) / n_splits
        del dtrain, dval, dtest, model
        gc.collect()

    auc = roc_auc_score(y, oof_preds)
    logger.info(f"XGBoost Overall CV AUC: {auc:.6f}")
    return oof_preds, test_preds


def find_best_weight(
    oof_lgb: np.ndarray, oof_xgb: np.ndarray, y: np.ndarray
) -> float:
    """OOF予測を使ってアンサンブルの最適重みを探索"""
    logger.info("アンサンブル最適重み探索中...")
    best_auc = 0.0
    best_w = 0.5
    # 0.0〜1.0を0.05刻みで探索（w = LGBの重み）
    for w in np.arange(0.0, 1.05, 0.05):
        blended = w * oof_lgb + (1 - w) * oof_xgb
        auc = roc_auc_score(y, blended)
        if auc > best_auc:
            best_auc = auc
            best_w = w
    logger.info(f"最適重み: LGB={best_w:.2f}, XGB={1 - best_w:.2f} -> AUC={best_auc:.6f}")
    return best_w


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
    test_ids = test['id'].copy()

    # 前処理（LGB用・XGB用の両方を取得）
    X_train_lgb, y, X_test_lgb, X_train_xgb, X_test_xgb, cat_features = preprocess(train, test)
    del train, test
    gc.collect()

    # LightGBM (GPU)
    oof_lgb, test_lgb = train_lgbm(X_train_lgb, y, X_test_lgb, cat_features)
    del X_train_lgb, X_test_lgb
    gc.collect()

    # GPU VRAM解放（LGB→XGB切り替え時）
    try:
        import torch
        torch.cuda.empty_cache()
        logger.info("CUDA cache cleared")
    except Exception:
        pass

    # XGBoost (GPU)
    oof_xgb, test_xgb = train_xgb_model(X_train_xgb, y, X_test_xgb)
    del X_train_xgb, X_test_xgb
    gc.collect()

    # 最適重みでアンサンブル
    w = find_best_weight(oof_lgb, oof_xgb, y)
    test_preds = w * test_lgb + (1 - w) * test_xgb

    # 個別モデルのsubmissionも保存（比較用）
    create_submission(test_ids, test_lgb, 'submission_v4_lgb.csv')
    create_submission(test_ids, test_xgb, 'submission_v4_xgb.csv')
    create_submission(test_ids, test_preds, 'submission_v4_ensemble.csv')

    logger.info("全処理完了！")


if __name__ == '__main__':
    main()
