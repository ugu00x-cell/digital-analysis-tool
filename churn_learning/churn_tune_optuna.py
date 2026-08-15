"""
UCI Telco Customer Churn: LightGBM ハイパーパラメータ最適化（Optuna）

5-fold Stratified CVでAUCを最大化するLightGBMのパラメータをOptunaで探索し、
デフォルトパラメータとの性能差をテストデータで比較する。
"""

import logging

import lightgbm as lgb
import optuna
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

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
optuna.logging.set_verbosity(optuna.logging.WARNING)

N_TRIALS = 50
N_SPLITS = 5


def cv_auc(params: dict, X: pd.DataFrame, y: pd.Series) -> float:
    """5-fold Stratified CVでAUCの平均を算出する"""
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=42)
    scores = []
    for train_idx, valid_idx in skf.split(X, y):
        model = lgb.LGBMClassifier(**params, random_state=42, verbose=-1)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        proba = model.predict_proba(X.iloc[valid_idx])[:, 1]
        scores.append(roc_auc_score(y.iloc[valid_idx], proba))
    return sum(scores) / len(scores)


def objective(trial: optuna.Trial, X: pd.DataFrame, y: pd.Series) -> float:
    """Optunaの探索対象パラメータを定義し、CV AUCを返す"""
    params = {
        'n_estimators': 300,
        'num_leaves': trial.suggest_int('num_leaves', 8, 128),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 100),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
        'bagging_freq': 1,
        'lambda_l1': trial.suggest_float('lambda_l1', 1e-8, 10.0, log=True),
        'lambda_l2': trial.suggest_float('lambda_l2', 1e-8, 10.0, log=True),
    }
    return cv_auc(params, X, y)


def evaluate_on_test(
    params: dict, X_train: pd.DataFrame, y_train: pd.Series,
    X_test: pd.DataFrame, y_test: pd.Series, label: str,
) -> dict:
    """指定パラメータでテストデータのAUC・F1を評価する"""
    model = lgb.LGBMClassifier(**params, random_state=42, verbose=-1)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    pred = model.predict(X_test)
    result = {
        'label': label,
        'AUC': roc_auc_score(y_test, proba),
        'F1': f1_score(y_test, pred, zero_division=0),
    }
    logger.info(f"{label}: AUC={result['AUC']:.4f} F1={result['F1']:.4f}")
    return result


def main() -> None:
    """Optunaでチューニングし、デフォルトパラメータとテストAUCを比較する"""
    print("=" * 80)
    print(f"LightGBM ハイパーパラメータ最適化（Optuna, {N_TRIALS} trials）")
    print("=" * 80)

    df = load_data(DATA_PATH)
    X, y = preprocess(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"Optuna探索開始: {N_TRIALS} trials, {N_SPLITS}-fold CV")
    study = optuna.create_study(direction='maximize')
    study.optimize(lambda trial: objective(trial, X_train, y_train), n_trials=N_TRIALS)

    logger.info(f"最良CV AUC: {study.best_value:.4f}")
    logger.info(f"最良パラメータ: {study.best_params}")

    default_params = {'n_estimators': 300, 'max_depth': 4, 'learning_rate': 0.05}
    best_params = {**study.best_params, 'n_estimators': 300}

    results = [
        evaluate_on_test(default_params, X_train, y_train, X_test, y_test, 'デフォルト'),
        evaluate_on_test(best_params, X_train, y_train, X_test, y_test, 'Optuna最適化後'),
    ]

    print("\n" + "=" * 80)
    print("【最良パラメータ】")
    print("=" * 80)
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 80)
    print("【テストデータでの比較】")
    print("=" * 80)
    print(pd.DataFrame(results).to_string(index=False, float_format='%.4f'))
    print("=" * 80)


if __name__ == '__main__':
    main()
