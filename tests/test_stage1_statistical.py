"""
Stage1 統計ベースしきい値のテスト

正常系2・異常系2・境界値1
"""

import numpy as np
import pytest

from threshold_analysis.stage1_statistical import (
    calc_fixed_ratio_thresholds,
    calc_mad_thresholds,
    calc_percentile_thresholds,
    calc_sigma_thresholds,
)


class TestSigmaThresholds:
    """平均+Nσ しきい値のテスト"""

    def test_normal_gaussian(self) -> None:
        """正常系: 標準正規分布的データでσしきい値が正しく算出される"""
        rng = np.random.default_rng(42)
        # 平均1.0, 標準偏差0.1のデータ
        data = rng.normal(1.0, 0.1, size=1000)
        result = calc_sigma_thresholds(data, "test", sigma_levels=(2.0, 3.0, 4.0))
        # mean ≒ 1.0, std ≒ 0.1 なので caution ≒ 1.2
        assert abs(result.caution - 1.2) < 0.05
        assert abs(result.warning - 1.3) < 0.05
        assert abs(result.danger - 1.4) < 0.05

    def test_normal_monotonic_order(self) -> None:
        """正常系: caution < warning < danger の順序が保たれる"""
        data = np.array([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        result = calc_sigma_thresholds(data, "test")
        assert result.caution < result.warning < result.danger

    def test_error_constant_data(self) -> None:
        """異常系: 定数データ（std=0）でもエラーにならない"""
        data = np.ones(100)
        result = calc_sigma_thresholds(data, "test")
        # std=0なので全しきい値が平均値と同じ
        assert result.caution == result.warning == result.danger == 1.0

    def test_error_single_value(self) -> None:
        """異常系: 1要素の配列でもエラーにならない"""
        data = np.array([0.5])
        result = calc_sigma_thresholds(data, "test")
        assert result.caution == 0.5

    def test_boundary_large_sigma(self) -> None:
        """境界値: 大きなσレベル(10σ)でも正常動作する"""
        data = np.array([1.0, 1.1, 0.9, 1.05, 0.95])
        result = calc_sigma_thresholds(data, "test", sigma_levels=(10.0, 20.0, 30.0))
        assert result.danger > result.warning > result.caution


class TestPercentileThresholds:
    """パーセンタイル しきい値のテスト"""

    def test_normal_known_distribution(self) -> None:
        """正常系: 0-100の均一分布で95/99/99.9パーセンタイルが正しい"""
        data = np.arange(1001, dtype=float)  # 0~1000
        result = calc_percentile_thresholds(data, "test")
        assert abs(result.caution - 950.0) < 1.0
        assert abs(result.warning - 990.0) < 1.0

    def test_normal_monotonic_order(self) -> None:
        """正常系: caution < warning < danger の順序が保たれる"""
        rng = np.random.default_rng(42)
        data = rng.exponential(1.0, size=1000)
        result = calc_percentile_thresholds(data, "test")
        assert result.caution < result.warning < result.danger

    def test_error_constant_data(self) -> None:
        """異常系: 定数データでも動作する（全しきい値が同じ値）"""
        data = np.ones(100) * 5.0
        result = calc_percentile_thresholds(data, "test")
        assert result.caution == result.warning == result.danger == 5.0

    def test_error_two_values(self) -> None:
        """異常系: 2値データでもエラーにならない"""
        data = np.array([1.0, 2.0])
        result = calc_percentile_thresholds(data, "test")
        assert result.caution >= 1.0

    def test_boundary_high_percentile(self) -> None:
        """境界値: 99.99パーセンタイルでも動作する"""
        data = np.arange(10000, dtype=float)
        result = calc_percentile_thresholds(
            data, "test", percentiles=(99.0, 99.9, 99.99),
        )
        assert result.danger > result.warning > result.caution


class TestMadThresholds:
    """MAD しきい値のテスト"""

    def test_normal_gaussian(self) -> None:
        """正常系: 正規分布データでMADスケールがσに近い値になる"""
        rng = np.random.default_rng(42)
        data = rng.normal(1.0, 0.1, size=10000)
        result = calc_mad_thresholds(data, "test", mad_levels=(3.0, 5.0, 7.0))
        # MAD * 1.4826 ≒ σ ≒ 0.1 なので caution ≒ 1.0 + 3*0.1 = 1.3
        assert abs(result.caution - 1.3) < 0.05

    def test_normal_robust_to_outliers(self) -> None:
        """正常系: 外れ値が混入してもしきい値が大きく変動しない"""
        rng = np.random.default_rng(42)
        data_clean = rng.normal(1.0, 0.1, size=1000)
        # 5%の外れ値を追加
        data_dirty = np.concatenate([data_clean, np.array([10.0] * 50)])

        result_clean = calc_mad_thresholds(data_clean, "clean")
        result_dirty = calc_mad_thresholds(data_dirty, "dirty")

        # MADベースなので外れ値の影響が小さい（σベースだと大きく変動する）
        assert abs(result_clean.caution - result_dirty.caution) < 0.1

    def test_error_constant_data(self) -> None:
        """異常系: 定数データ（MAD=0）でも動作する"""
        data = np.ones(100) * 3.0
        result = calc_mad_thresholds(data, "test")
        # MAD=0なので全しきい値がmedianと同じ
        assert result.caution == 3.0

    def test_error_single_element(self) -> None:
        """異常系: 1要素でもエラーにならない"""
        data = np.array([2.5])
        result = calc_mad_thresholds(data, "test")
        assert result.caution == 2.5

    def test_boundary_skewed_data(self) -> None:
        """境界値: 歪んだ分布（対数正規）でも正常動作する"""
        rng = np.random.default_rng(42)
        data = rng.lognormal(0.0, 0.5, size=1000)
        result = calc_mad_thresholds(data, "test")
        assert result.caution < result.warning < result.danger


class TestFixedRatioThresholds:
    """固定倍率 しきい値のテスト（ベースライン比較用）"""

    def test_normal_default_ratios(self) -> None:
        """正常系: デフォルト倍率(1.2/1.5/2.0)が正しく適用される"""
        data = np.array([1.0, 1.0, 1.0])  # 平均1.0
        result = calc_fixed_ratio_thresholds(data, "test")
        assert abs(result.caution - 1.2) < 1e-6
        assert abs(result.warning - 1.5) < 1e-6
        assert abs(result.danger - 2.0) < 1e-6

    def test_normal_custom_ratios(self) -> None:
        """正常系: カスタム倍率が正しく適用される"""
        data = np.array([2.0, 2.0])  # 平均2.0
        result = calc_fixed_ratio_thresholds(
            data, "test", ratios=(1.1, 1.3, 1.5),
        )
        assert abs(result.caution - 2.2) < 1e-6
        assert abs(result.warning - 2.6) < 1e-6
