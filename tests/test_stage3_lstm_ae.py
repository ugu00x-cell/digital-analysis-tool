"""
Stage3 LSTM-AutoEncoderのテスト

正常系2・異常系2・境界値1
"""

import numpy as np
import pytest
import torch

from threshold_analysis.stage3_lstm_ae_model import (
    LSTMAutoEncoder,
    calc_reconstruction_error,
    create_sequences,
)
from threshold_analysis.stage3_lstm_ae_evaluate import errors_to_rms_thresholds


class TestCreateSequences:
    """シーケンス化のテスト"""

    def test_normal_basic(self) -> None:
        """正常系: 基本的なスライディングウィンドウが正しく動作する"""
        data = np.arange(20).reshape(10, 2).astype(float)
        seqs = create_sequences(data, seq_length=3)
        # 10 - 3 + 1 = 8 シーケンス
        assert seqs.shape == (8, 3, 2)
        # 最初のシーケンスが正しい
        np.testing.assert_array_equal(seqs[0], data[:3])

    def test_normal_full_length(self) -> None:
        """正常系: seq_length==データ長で1シーケンスになる"""
        data = np.ones((5, 3))
        seqs = create_sequences(data, seq_length=5)
        assert seqs.shape == (1, 5, 3)

    def test_error_short_data(self) -> None:
        """異常系: データ長 < seq_lengthでも動作する（自動調整）"""
        data = np.ones((3, 2))
        seqs = create_sequences(data, seq_length=10)
        # seq_lengthが3に自動調整されるはず
        assert seqs.shape[1] <= 3

    def test_error_single_sample(self) -> None:
        """異常系: 1サンプルでも動作する"""
        data = np.array([[1.0, 2.0]])
        seqs = create_sequences(data, seq_length=1)
        assert seqs.shape == (1, 1, 2)

    def test_boundary_seq_length_1(self) -> None:
        """境界値: seq_length=1で各サンプルが独立シーケンスになる"""
        data = np.arange(6).reshape(3, 2).astype(float)
        seqs = create_sequences(data, seq_length=1)
        assert seqs.shape == (3, 1, 2)


class TestLSTMAutoEncoder:
    """LSTM-AEモデルのテスト"""

    def test_normal_forward_shape(self) -> None:
        """正常系: 順伝播の出力形状が入力と同じ"""
        model = LSTMAutoEncoder(input_dim=5, seq_length=10)
        x = torch.randn(4, 10, 5)  # (batch=4, seq=10, features=5)
        output = model(x)
        assert output.shape == x.shape

    def test_normal_reconstruction(self) -> None:
        """正常系: 学習後に正常データの再構成誤差が小さい"""
        torch.manual_seed(42)
        model = LSTMAutoEncoder(input_dim=3, seq_length=5)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        criterion = torch.nn.MSELoss()

        # 簡単なパターンを学習
        x = torch.sin(torch.linspace(0, 6, 50)).reshape(10, 5, 1)
        x = x.expand(-1, -1, 3)  # 3特徴量に拡張

        model.train()
        for _ in range(200):
            output = model(x)
            loss = criterion(output, x)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            errors = calc_reconstruction_error(model, x)
        # 再構成誤差がある程度小さくなっていること
        assert np.mean(errors) < 1.0

    def test_error_single_feature(self) -> None:
        """異常系: 1特徴量でも動作する"""
        model = LSTMAutoEncoder(input_dim=1, seq_length=5)
        x = torch.randn(2, 5, 1)
        output = model(x)
        assert output.shape == x.shape

    def test_error_batch_size_1(self) -> None:
        """異常系: バッチサイズ1でも動作する"""
        model = LSTMAutoEncoder(input_dim=3, seq_length=5)
        x = torch.randn(1, 5, 3)
        output = model(x)
        assert output.shape == x.shape

    def test_boundary_large_seq(self) -> None:
        """境界値: 長いシーケンス(100)でも動作する"""
        model = LSTMAutoEncoder(input_dim=3, seq_length=100)
        x = torch.randn(2, 100, 3)
        output = model(x)
        assert output.shape == x.shape


class TestErrorsToRmsThresholds:
    """再構成誤差→RMSしきい値変換のテスト"""

    def test_normal_monotonic(self) -> None:
        """正常系: 誤差とRMSが正相関のときcaution <= warning <= danger"""
        errors = np.linspace(0, 1, 10000)
        rms = np.linspace(0.1, 2.0, 10000)
        c, w, d = errors_to_rms_thresholds(errors, rms)
        assert c <= w <= d

    def test_normal_known_values(self) -> None:
        """正常系: 既知の分布で正しい値が返る"""
        errors = np.arange(100, dtype=float)
        rms = np.arange(100, dtype=float) * 0.1  # 0.0, 0.1, ..., 9.9
        c, w, d = errors_to_rms_thresholds(errors, rms)
        # 95パーセンタイル: rms[95] = 9.5
        assert abs(c - 9.5) < 0.2
