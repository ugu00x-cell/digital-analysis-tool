"""
Stage2 機械学習ベースしきい値のテスト

正常系2・異常系2・境界値1
"""

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

from threshold_analysis.stage2_ml_train import (
    get_anomaly_scores,
    train_isolation_forest,
    train_ocsvm,
)
from threshold_analysis.stage2_ml_evaluate import (
    scores_to_rms_thresholds,
    scores_to_score_thresholds,
)


class TestIsolationForest:
    """IsolationForest学習のテスト"""

    def test_normal_train_and_score(self) -> None:
        """正常系: 学習後に正常データのスコアが高い"""
        rng = np.random.default_rng(42)
        normal = rng.normal(0, 1, size=(200, 3))
        model, scaler = train_isolation_forest(normal)
        scores = get_anomaly_scores(model, scaler, normal)
        # 正常データの平均スコアは正の値（異常ではない）
        assert np.mean(scores) > -0.5

    def test_normal_anomaly_detected(self) -> None:
        """正常系: 異常データのスコアが正常データより低い"""
        rng = np.random.default_rng(42)
        normal = rng.normal(0, 0.1, size=(200, 3))
        anomaly = rng.normal(5, 0.1, size=(20, 3))
        model, scaler = train_isolation_forest(normal)

        normal_scores = get_anomaly_scores(model, scaler, normal)
        anomaly_scores = get_anomaly_scores(model, scaler, anomaly)
        # 異常データの平均スコアが正常データより低い
        assert np.mean(anomaly_scores) < np.mean(normal_scores)

    def test_error_single_feature(self) -> None:
        """異常系: 1特徴量でも学習できる"""
        data = np.array([[1.0], [1.1], [0.9], [1.05], [0.95]] * 10)
        model, scaler = train_isolation_forest(data)
        scores = get_anomaly_scores(model, scaler, data)
        assert len(scores) == len(data)

    def test_error_few_samples(self) -> None:
        """異常系: 少数サンプル(10件)でも学習できる"""
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=(10, 5))
        model, scaler = train_isolation_forest(data)
        scores = get_anomaly_scores(model, scaler, data)
        assert len(scores) == 10

    def test_boundary_high_dimensional(self) -> None:
        """境界値: 高次元(50特徴量)でも動作する"""
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=(100, 50))
        model, scaler = train_isolation_forest(data)
        scores = get_anomaly_scores(model, scaler, data)
        assert len(scores) == 100


class TestOneClassSVM:
    """One-Class SVM学習のテスト"""

    def test_normal_train_and_score(self) -> None:
        """正常系: 学習後に正常データのスコアが正の値"""
        rng = np.random.default_rng(42)
        normal = rng.normal(0, 1, size=(100, 3))
        model, scaler = train_ocsvm(normal)
        scores = get_anomaly_scores(model, scaler, normal)
        # 大半の正常データのスコアが正
        assert np.mean(scores > 0) > 0.8

    def test_normal_anomaly_separation(self) -> None:
        """正常系: 異常データと正常データのスコアが分離する"""
        rng = np.random.default_rng(42)
        normal = rng.normal(0, 0.1, size=(100, 3))
        anomaly = rng.normal(3, 0.1, size=(20, 3))
        model, scaler = train_ocsvm(normal)

        normal_scores = get_anomaly_scores(model, scaler, normal)
        anomaly_scores = get_anomaly_scores(model, scaler, anomaly)
        assert np.mean(anomaly_scores) < np.mean(normal_scores)

    def test_error_minimum_samples(self) -> None:
        """異常系: 最小サンプル数でもエラーにならない"""
        data = np.array([[1.0, 2.0], [1.1, 2.1], [0.9, 1.9]])
        model, scaler = train_ocsvm(data)
        scores = get_anomaly_scores(model, scaler, data)
        assert len(scores) == 3


class TestScoreConversion:
    """スコア→しきい値変換のテスト"""

    def test_normal_rms_thresholds_order(self) -> None:
        """正常系: RMSしきい値がcaution <= warning <= dangerの順"""
        # 十分なサンプル数でパーセンタイル差が出るようにする
        scores = np.linspace(0.5, -0.5, 10000)
        rms = np.linspace(0.1, 2.0, 10000)
        c, w, d = scores_to_rms_thresholds(scores, rms)
        assert c <= w <= d

    def test_normal_score_thresholds(self) -> None:
        """正常系: スコアしきい値がcaution > warning > dangerの順"""
        normal_scores = np.linspace(0.0, 1.0, 1000)
        c, w, d = scores_to_score_thresholds(normal_scores)
        # 5%ile > 1%ile > 0.1%ile
        assert c > w > d

    def test_boundary_identical_scores(self) -> None:
        """境界値: 全スコアが同一値でもエラーにならない"""
        scores = np.ones(100) * 0.3
        rms = np.ones(100) * 0.5
        c, w, d = scores_to_rms_thresholds(scores, rms)
        assert c == w == d == 0.5
