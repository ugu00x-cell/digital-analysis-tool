"""
UCI Telco Customer Churn: 4モデル比較（統計学習用）

ロジスティック回帰・ランダムフォレスト・XGBoost・LightGBMの
4種類の分類モデルを同一の前処理データで学習し、
AUC・F1・Precision・Recallで性能を比較する。
"""

import logging

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_PATH = "data/WA_Fn-UseC_-Telco-Customer-Churn.csv"

# One-Hotエンコードするカテゴリカル列（2値かつYes/No系はLabelEncodeでもよいが統一してOne-Hot）
CATEGORICAL_COLS = [
    'gender', 'Partner', 'Dependents', 'PhoneService', 'MultipleLines',
    'InternetService', 'OnlineSecurity', 'OnlineBackup', 'DeviceProtection',
    'TechSupport', 'StreamingTV', 'StreamingMovies', 'Contract',
    'PaperlessBilling', 'PaymentMethod',
]
NUMERIC_COLS = ['tenure', 'MonthlyCharges', 'TotalCharges', 'SeniorCitizen']


def load_data(path: str) -> pd.DataFrame:
    """CSVを読み込む"""
    logger.info(f"データ読み込み開始: {path}")
    df = pd.read_csv(path)
    logger.info(f"読み込み完了: {df.shape}")
    return df


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """欠損値処理・エンコーディング・正規化を行い、特徴量Xと目的変数yを返す"""
    df = df.copy()

    # TotalChargesは空白文字が混じっているため数値変換し、欠損はMonthlyChargesで補完
    df['TotalCharges'] = pd.to_numeric(df['TotalCharges'], errors='coerce')
    missing_count = df['TotalCharges'].isna().sum()
    logger.info(f"TotalCharges欠損値: {missing_count}件 → MonthlyChargesで補完")
    df['TotalCharges'] = df['TotalCharges'].fillna(df['MonthlyCharges'])

    # 目的変数をYes=1, No=0に変換
    y = (df['Churn'] == 'Yes').astype(int)

    # カテゴリカル変数をLabelEncoding（木系モデルとの相性を優先。線形モデル側はスケーリングで補正）
    df_enc = df.copy()
    for col in CATEGORICAL_COLS:
        df_enc[col] = LabelEncoder().fit_transform(df_enc[col].astype(str))

    feature_cols = CATEGORICAL_COLS + NUMERIC_COLS
    X = df_enc[feature_cols]

    logger.info(f"特徴量準備完了: X={X.shape}, 陽性率={y.mean():.3f}")
    return X, y


def evaluate_model(name: str, y_true: pd.Series, y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    """AUC・F1・Precision・Recallを算出して辞書で返す"""
    result = {
        'model': name,
        'AUC': roc_auc_score(y_true, y_proba),
        'F1': f1_score(y_true, y_pred, zero_division=0),
        'Precision': precision_score(y_true, y_pred, zero_division=0),
        'Recall': recall_score(y_true, y_pred, zero_division=0),
    }
    logger.info(
        f"{name}: AUC={result['AUC']:.4f} F1={result['F1']:.4f} "
        f"Precision={result['Precision']:.4f} Recall={result['Recall']:.4f}"
    )
    return result


def run_baseline(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """常に多数派クラス(No)を予測するダミー分類器を比較の基準線として評価する"""
    dummy = DummyClassifier(strategy='most_frequent')
    dummy.fit(X_train, y_train)
    y_pred = dummy.predict(X_test)
    y_proba = dummy.predict_proba(X_test)[:, 1]
    return evaluate_model('Baseline(Dummy)', y_test, y_pred, y_proba)


def run_logistic_regression(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """ロジスティック回帰で学習・評価する（スケーリングを適用）"""
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)
    y_pred = model.predict(X_test_scaled)
    y_proba = model.predict_proba(X_test_scaled)[:, 1]
    return evaluate_model('LogisticRegression', y_test, y_pred, y_proba)


def run_random_forest(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """ランダムフォレストで学習・評価する"""
    model = RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return evaluate_model('RandomForest', y_test, y_pred, y_proba)


def run_xgboost(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """XGBoostで学習・評価する"""
    model = xgb.XGBClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        eval_metric='auc', random_state=42,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return evaluate_model('XGBoost', y_test, y_pred, y_proba)


def run_lightgbm(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame, y_test: pd.Series
) -> dict:
    """LightGBMで学習・評価する"""
    model = lgb.LGBMClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        random_state=42, verbose=-1,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return evaluate_model('LightGBM', y_test, y_pred, y_proba)


def main() -> None:
    """4モデルを比較し、結果表を表示する"""
    print("=" * 80)
    print("UCI Telco Customer Churn: 4モデル比較")
    print("=" * 80)

    df = load_data(DATA_PATH)
    X, y = preprocess(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"train={X_train.shape}, test={X_test.shape}")

    results = [
        run_baseline(X_train, y_train, X_test, y_test),
        run_logistic_regression(X_train, y_train, X_test, y_test),
        run_random_forest(X_train, y_train, X_test, y_test),
        run_xgboost(X_train, y_train, X_test, y_test),
        run_lightgbm(X_train, y_train, X_test, y_test),
    ]

    result_df = pd.DataFrame(results).sort_values('AUC', ascending=False)
    print("\n" + "=" * 80)
    print("【比較結果（AUC降順）】")
    print("=" * 80)
    print(result_df.to_string(index=False, float_format='%.4f'))
    print("=" * 80)


if __name__ == '__main__':
    main()
