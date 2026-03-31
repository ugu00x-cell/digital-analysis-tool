"""
Kaggle Playground Series S6E3 - Customer Churn Prediction
LightGBMによる二値分類（評価指標: ROC AUC）
"""

import logging
import pandas as pd
import numpy as np
import lightgbm as lgb
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


def load_data(train_path: str, test_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """学習データとテストデータを読み込む"""
    logger.info("データ読み込み開始")
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    logger.info(f"train: {train.shape}, test: {test.shape}")
    return train, test


def run_eda(df: pd.DataFrame) -> None:
    """簡易EDA：データ型・欠損値・ターゲット分布を確認"""
    logger.info("=== EDA開始 ===")

    # データ型と欠損値
    logger.info(f"カラム数: {len(df.columns)}")
    logger.info(f"欠損値:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
    if df.isnull().sum().sum() == 0:
        logger.info("欠損値なし")

    # データ型の内訳
    logger.info(f"数値型: {df.select_dtypes(include='number').columns.tolist()}")
    logger.info(f"カテゴリ型: {df.select_dtypes(include='object').columns.tolist()}")

    # ターゲット分布
    if 'Churn' in df.columns:
        churn_counts = df['Churn'].value_counts()
        logger.info(f"Churn分布:\n{churn_counts}")
        logger.info(f"Churn率: {(df['Churn'] == 'Yes').mean():.4f}")

    logger.info("=== EDA完了 ===")


def preprocess(
    train: pd.DataFrame, test: pd.DataFrame
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, list[str]]:
    """前処理：ターゲット変換＋カテゴリ変数をLabel Encoding"""
    logger.info("前処理開始")

    # ターゲットを数値化（Yes=1, No=0）
    y = (train['Churn'] == 'Yes').astype(int).values

    # id と Churn を除いた特徴量カラム
    feature_cols = [c for c in train.columns if c not in ['id', 'Churn']]

    # TotalChargesに空白文字が混入している場合の対処
    for df in [train, test]:
        if df['TotalCharges'].dtype == object:
            df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')

    # カテゴリ変数をLabel Encoding
    label_encoders: dict[str, LabelEncoder] = {}
    cat_cols = train[feature_cols].select_dtypes(include='object').columns.tolist()
    logger.info(f"Label Encoding対象: {cat_cols}")

    for col in cat_cols:
        le = LabelEncoder()
        # train と test を結合してfit（未知ラベル対策）
        combined = pd.concat([train[col], test[col]], axis=0).astype(str)
        le.fit(combined)
        train[col] = le.transform(train[col].astype(str))
        test[col] = le.transform(test[col].astype(str))
        label_encoders[col] = le

    # 欠損値を中央値で埋める
    X_train = train[feature_cols].copy()
    X_test = test[feature_cols].copy()
    for col in feature_cols:
        if X_train[col].isnull().any():
            median_val = X_train[col].median()
            X_train[col].fillna(median_val, inplace=True)
            X_test[col].fillna(median_val, inplace=True)

    logger.info(f"特徴量数: {len(feature_cols)}")
    logger.info("前処理完了")
    return X_train, y, X_test, feature_cols


def train_lightgbm(
    X_train: pd.DataFrame,
    y: np.ndarray,
    X_test: pd.DataFrame,
    n_splits: int = 5
) -> np.ndarray:
    """StratifiedKFold + LightGBMで予測確率を生成"""
    logger.info(f"LightGBM学習開始（{n_splits}-Fold CV）")

    # ハイパーパラメータ
    params = {
        'objective': 'binary',
        'metric': 'auc',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'max_depth': -1,
        'min_child_samples': 20,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'verbose': -1,
        'n_jobs': -1,
        'random_state': 42,
    }

    # OOF予測とテスト予測の格納先
    oof_preds = np.zeros(len(X_train))
    test_preds = np.zeros(len(X_test))

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    for fold, (train_idx, val_idx) in enumerate(skf.split(X_train, y)):
        logger.info(f"--- Fold {fold + 1}/{n_splits} ---")

        X_tr = X_train.iloc[train_idx]
        y_tr = y[train_idx]
        X_val = X_train.iloc[val_idx]
        y_val = y[val_idx]

        # LightGBM用データセット
        dtrain = lgb.Dataset(X_tr, label=y_tr)
        dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

        # 学習
        model = lgb.train(
            params,
            dtrain,
            num_boost_round=1000,
            valid_sets=[dval],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50),
                lgb.log_evaluation(period=100),
            ],
        )

        # バリデーション予測
        oof_preds[val_idx] = model.predict(X_val)
        fold_auc = roc_auc_score(y_val, oof_preds[val_idx])
        logger.info(f"Fold {fold + 1} AUC: {fold_auc:.6f}")

        # テスト予測（Fold平均）
        test_preds += model.predict(X_test) / n_splits

    # 全体のCV AUC
    overall_auc = roc_auc_score(y, oof_preds)
    logger.info(f"Overall CV AUC: {overall_auc:.6f}")

    return test_preds


def create_submission(
    test_ids: pd.Series, predictions: np.ndarray, output_path: str
) -> None:
    """submission.csvを作成"""
    submission = pd.DataFrame({
        'id': test_ids,
        'Churn': predictions
    })
    submission.to_csv(output_path, index=False)
    logger.info(f"submission保存完了: {output_path} ({len(submission)}行)")


def main() -> None:
    """メイン処理"""
    # データ読み込み
    train, test = load_data('data/train.csv', 'data/test.csv')

    # EDA
    run_eda(train)

    # 前処理
    X_train, y, X_test, feature_cols = preprocess(train, test)

    # LightGBM学習・予測
    test_preds = train_lightgbm(X_train, y, X_test)

    # submission作成
    create_submission(test['id'], test_preds, 'submission.csv')

    logger.info("全処理完了！")


if __name__ == '__main__':
    main()
