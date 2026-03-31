"""
Kaggle Playground Series S6E3 - Customer Churn Prediction (v2)
改善版：特徴量エンジニアリング + カテゴリネイティブ + Optunaチューニング
"""

import logging
import pandas as pd
import numpy as np
import lightgbm as lgb
import optuna
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

# Optunaのログを抑制（進捗はloggerで出す）
optuna.logging.set_verbosity(optuna.logging.WARNING)

# サービス系カラム（Yes/Noのもの）
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
    # 利用期間 × 月額料金
    df['tenure_x_monthly'] = df['tenure'] * df['MonthlyCharges']

    # 月あたり平均支出
    df['avg_monthly_spend'] = df['TotalCharges'] / (df['tenure'] + 1)

    # 直近の支出比率（月額が全体に占める割合）
    df['monthly_ratio'] = df['MonthlyCharges'] / (df['TotalCharges'] + 1)

    # サービス利用数（Yes のカウント）
    df['service_count'] = (df[SERVICE_COLS] == 'Yes').sum(axis=1)

    # 高齢者 × 契約形態
    df['senior_x_contract'] = (
        df['SeniorCitizen'].astype(str) + '_' + df['Contract'].astype(str)
    )

    return df


def preprocess(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, list[str], list[str]]:
    """前処理：特徴量追加 + カテゴリをcategory型に変換"""
    logger.info("前処理開始")

    # ターゲットを数値化
    y = (train['Churn'] == 'Yes').astype(int).values

    # TotalChargesの型変換（空白文字対策）
    for df in [train, test]:
        if df['TotalCharges'].dtype == object:
            df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')

    # 特徴量エンジニアリング（サービスカウントはカテゴリ変換前に実行）
    train = add_features(train)
    test = add_features(test)

    # 全カテゴリカラム（新規追加分含む）
    all_cat_cols = CAT_COLS + ['senior_x_contract']

    # id, Churn を除外した特徴量カラム
    feature_cols = [c for c in train.columns if c not in ['id', 'Churn']]

    # カテゴリ変数をcategory型に変換（LightGBMネイティブ対応）
    for col in all_cat_cols:
        combined_cat = pd.CategoricalDtype(
            categories=pd.concat([train[col], test[col]]).unique()
        )
        train[col] = train[col].astype(combined_cat)
        test[col] = test[col].astype(combined_cat)

    X_train = train[feature_cols].copy()
    X_test = test[feature_cols].copy()

    # 欠損値を中央値で埋める（数値列のみ）
    num_cols = X_train.select_dtypes(include='number').columns
    for col in num_cols:
        if X_train[col].isnull().any():
            median_val = X_train[col].median()
            X_train[col] = X_train[col].fillna(median_val)
            X_test[col] = X_test[col].fillna(median_val)

    # カテゴリカラム名リスト（LightGBMに渡す用）
    cat_feature_names = [c for c in all_cat_cols if c in feature_cols]

    logger.info(f"特徴量数: {len(feature_cols)}（うちカテゴリ: {len(cat_feature_names)}）")
    logger.info(f"追加特徴量: tenure_x_monthly, avg_monthly_spend, monthly_ratio, service_count, senior_x_contract")
    logger.info("前処理完了")
    return X_train, y, X_test, feature_cols, cat_feature_names


def cv_score(
    params: dict,
    X_train: pd.DataFrame,
    y: np.ndarray,
    cat_features: list[str],
    n_splits: int = 5,
) -> float:
    """指定パラメータでCV AUCを計算（Optuna用）"""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    oof_preds = np.zeros(len(X_train))

    for train_idx, val_idx in skf.split(X_train, y):
        dtrain = lgb.Dataset(
            X_train.iloc[train_idx], label=y[train_idx],
            categorical_feature=cat_features
        )
        dval = lgb.Dataset(
            X_train.iloc[val_idx], label=y[val_idx],
            categorical_feature=cat_features, reference=dtrain
        )
        model = lgb.train(
            params, dtrain, num_boost_round=1000, valid_sets=[dval],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
        )
        oof_preds[val_idx] = model.predict(X_train.iloc[val_idx])

    return roc_auc_score(y, oof_preds)


def optimize_params(
    X_train: pd.DataFrame,
    y: np.ndarray,
    cat_features: list[str],
    n_trials: int = 50,
) -> dict:
    """Optunaでハイパーパラメータを最適化"""
    logger.info(f"Optuna最適化開始（{n_trials}トライアル）")

    def objective(trial: optuna.Trial) -> float:
        """Optunaの目的関数"""
        params = {
            'objective': 'binary',
            'metric': 'auc',
            'verbose': -1,
            'n_jobs': -1,
            'random_state': 42,
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'num_leaves': trial.suggest_int('num_leaves', 16, 128),
            'max_depth': trial.suggest_int('max_depth', 3, 12),
            'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        }
        auc = cv_score(params, X_train, y, cat_features, n_splits=3)
        logger.info(f"  Trial {trial.number}: AUC={auc:.6f}")
        return auc

    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=n_trials)

    best = study.best_params
    logger.info(f"最良AUC: {study.best_value:.6f}")
    logger.info(f"最良パラメータ: {best}")
    return best


def train_final(
    best_params: dict,
    X_train: pd.DataFrame,
    y: np.ndarray,
    X_test: pd.DataFrame,
    cat_features: list[str],
    n_splits: int = 5,
) -> np.ndarray:
    """最適パラメータで5-Fold学習し、テスト予測を生成"""
    logger.info(f"最終学習開始（{n_splits}-Fold CV）")

    # 固定パラメータとマージ
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'verbose': -1,
        'n_jobs': -1,
        'random_state': 42,
        **best_params,
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

    # 前処理（特徴量エンジニアリング含む）
    X_train, y, X_test, feature_cols, cat_features = preprocess(train, test)

    # Optunaでハイパーパラメータ最適化（3-Fold × 50トライアル）
    best_params = optimize_params(X_train, y, cat_features, n_trials=50)

    # 最適パラメータで5-Fold学習
    test_preds = train_final(best_params, X_train, y, X_test, cat_features)

    # submission作成
    create_submission(test['id'], test_preds, 'submission_v2.csv')

    logger.info("全処理完了！")


if __name__ == '__main__':
    main()
