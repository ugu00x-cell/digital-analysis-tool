"""
Stage 3: LSTM-AutoEncoderモデル定義

正常データの時系列パターンを学習し、
再構成誤差が大きい区間を異常と判定する
"""

import logging

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class LSTMEncoder(nn.Module):
    """LSTMエンコーダー: 入力シーケンスを潜在表現に圧縮する"""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        latent_dim: int = 16,
        n_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim, hidden_dim, n_layers,
            batch_first=True, dropout=dropout if n_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(hidden_dim, latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """エンコード: (batch, seq_len, input_dim) -> (batch, latent_dim)"""
        _, (h_n, _) = self.lstm(x)
        # 最終層の隠れ状態を使用
        latent = self.fc(h_n[-1])
        return latent


class LSTMDecoder(nn.Module):
    """LSTMデコーダー: 潜在表現から入力シーケンスを再構成する"""

    def __init__(
        self,
        latent_dim: int = 16,
        hidden_dim: int = 64,
        output_dim: int = 10,
        seq_length: int = 30,
        n_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.seq_length = seq_length
        self.fc = nn.Linear(latent_dim, hidden_dim)
        self.lstm = nn.LSTM(
            hidden_dim, hidden_dim, n_layers,
            batch_first=True, dropout=dropout if n_layers > 1 else 0.0,
        )
        self.output = nn.Linear(hidden_dim, output_dim)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """デコード: (batch, latent_dim) -> (batch, seq_len, output_dim)"""
        # 潜在表現をシーケンス長に展開
        h = self.fc(z).unsqueeze(1).repeat(1, self.seq_length, 1)
        out, _ = self.lstm(h)
        reconstructed = self.output(out)
        return reconstructed


class LSTMAutoEncoder(nn.Module):
    """LSTM-AutoEncoder: 正常パターンの学習と再構成誤差による異常検知

    Encoder: LSTM(input_dim -> hidden_dim -> latent_dim)
    Decoder: LSTM(latent_dim -> hidden_dim -> input_dim)
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        latent_dim: int = 16,
        seq_length: int = 30,
        n_layers: int = 2,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.encoder = LSTMEncoder(
            input_dim, hidden_dim, latent_dim, n_layers, dropout,
        )
        self.decoder = LSTMDecoder(
            latent_dim, hidden_dim, input_dim, seq_length, n_layers, dropout,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """順伝播: 入力と同じ形状の再構成結果を返す"""
        z = self.encoder(x)
        reconstructed = self.decoder(z)
        return reconstructed


def create_sequences(
    features: np.ndarray,
    seq_length: int = 30,
) -> np.ndarray:
    """特徴量配列をスライディングウィンドウでシーケンス化する

    Args:
        features: 特徴量配列 (n_samples, n_features)
        seq_length: シーケンス長

    Returns:
        シーケンス配列 (n_sequences, seq_length, n_features)
    """
    n_samples = len(features)
    if n_samples < seq_length:
        # データ不足時はシーケンス長を調整
        logger.warning(
            f"データ数({n_samples})がseq_length({seq_length})未満。"
            f"seq_length={n_samples}に調整"
        )
        seq_length = n_samples

    sequences = []
    for i in range(n_samples - seq_length + 1):
        sequences.append(features[i:i + seq_length])

    return np.array(sequences)


def calc_reconstruction_error(
    model: LSTMAutoEncoder,
    sequences: torch.Tensor,
    batch_size: int = 64,
) -> np.ndarray:
    """各シーケンスの再構成誤差(MSE)を算出する

    Args:
        model: 学習済みLSTM-AEモデル
        sequences: 入力シーケンス (n_sequences, seq_length, n_features)
        batch_size: バッチサイズ

    Returns:
        各シーケンスの再構成誤差配列
    """
    model.eval()
    errors = []
    device = next(model.parameters()).device

    with torch.no_grad():
        for i in range(0, len(sequences), batch_size):
            batch = sequences[i:i + batch_size].to(device)
            reconstructed = model(batch)
            # シーケンスごとのMSE
            mse = torch.mean((batch - reconstructed) ** 2, dim=(1, 2))
            errors.extend(mse.cpu().numpy())

    return np.array(errors)
