"""
Stage 3: LSTM-AutoEncoder 学習モジュール

正常データのシーケンスでLSTM-AEを学習する
Early Stoppingとバリデーション分割を含む
"""

import logging

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from threshold_analysis.stage3_lstm_ae_model import (
    LSTMAutoEncoder,
    create_sequences,
)
from threshold_analysis.utils.data_loader import (
    ALL_DATASETS,
    get_feature_columns,
    load_dataset,
)

logger = logging.getLogger(__name__)

# デフォルトのシーケンス長（小データセットは自動調整）
DEFAULT_SEQ_LENGTH = 30
MIN_SEQ_LENGTH = 5


def _determine_seq_length(n_samples: int) -> int:
    """データ数に応じてシーケンス長を自動決定する

    Args:
        n_samples: 正常データのサンプル数

    Returns:
        適切なシーケンス長
    """
    if n_samples < MIN_SEQ_LENGTH * 3:
        seq_len = max(MIN_SEQ_LENGTH, n_samples // 3)
        logger.warning(f"データ数少({n_samples}件) -> seq_length={seq_len}")
        return seq_len
    if n_samples < DEFAULT_SEQ_LENGTH * 3:
        seq_len = n_samples // 3
        logger.info(f"データ数やや少({n_samples}件) -> seq_length={seq_len}")
        return seq_len
    return DEFAULT_SEQ_LENGTH


def train_lstm_ae(
    normal_features: np.ndarray,
    input_dim: int,
    seq_length: int = DEFAULT_SEQ_LENGTH,
    epochs: int = 100,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    validation_split: float = 0.2,
    patience: int = 10,
) -> tuple[LSTMAutoEncoder, StandardScaler, int]:
    """正常データのシーケンスでLSTM-AEを学習する

    Args:
        normal_features: 正常データの特徴量 (n_samples, n_features)
        input_dim: 入力次元数
        seq_length: シーケンス長
        epochs: 最大エポック数
        batch_size: バッチサイズ
        learning_rate: 学習率
        validation_split: バリデーション割合
        patience: Early Stoppingの許容エポック数

    Returns:
        (学習済みモデル, スケーラー, 実際のシーケンス長)
    """
    # 特徴量のスケーリング
    scaler = StandardScaler()
    scaled = scaler.fit_transform(normal_features)

    # シーケンス長の自動調整
    seq_length = _determine_seq_length(len(scaled))

    # シーケンス化
    sequences = create_sequences(scaled, seq_length)
    if len(sequences) < 3:
        logger.error(f"シーケンス数が不足: {len(sequences)}件")
        raise ValueError("学習に十分なシーケンス数がありません")

    # 学習/バリデーション分割
    n_val = max(1, int(len(sequences) * validation_split))
    n_train = len(sequences) - n_val
    train_seq = torch.FloatTensor(sequences[:n_train])
    val_seq = torch.FloatTensor(sequences[n_train:])

    train_loader = DataLoader(
        TensorDataset(train_seq), batch_size=batch_size, shuffle=True,
    )

    # デバイス設定
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"学習デバイス: {device}")

    # モデル初期化
    model = LSTMAutoEncoder(
        input_dim=input_dim, seq_length=seq_length,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()

    # 学習ループ（Early Stopping付き）
    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(epochs):
        # 学習フェーズ
        model.train()
        train_loss = 0.0
        for (batch,) in train_loader:
            batch = batch.to(device)
            reconstructed = model(batch)
            loss = criterion(reconstructed, batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch)
        train_loss /= n_train

        # バリデーションフェーズ
        model.eval()
        with torch.no_grad():
            val_batch = val_seq.to(device)
            val_reconstructed = model(val_batch)
            val_loss = criterion(val_reconstructed, val_batch).item()

        # Early Stopping判定
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1

        if (epoch + 1) % 20 == 0:
            logger.info(
                f"  Epoch {epoch+1}/{epochs}: "
                f"train_loss={train_loss:.6f} val_loss={val_loss:.6f}"
            )

        if patience_counter >= patience:
            logger.info(f"  Early Stopping at epoch {epoch+1}")
            break

    # ベストモデルを復元
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    logger.info(
        f"LSTM-AE 学習完了: {n_train}シーケンス, "
        f"seq_length={seq_length}, best_val_loss={best_val_loss:.6f}"
    )

    return model, scaler, seq_length


def run_stage3_train(
    dataset_name: str,
) -> tuple[LSTMAutoEncoder, StandardScaler, int]:
    """指定データセットでLSTM-AEを学習する

    Args:
        dataset_name: データセット名

    Returns:
        (学習済みモデル, スケーラー, シーケンス長)
    """
    logger.info(f"=== Stage3 Train: {dataset_name} ===")
    normal_df, _ = load_dataset(dataset_name)
    feature_cols = get_feature_columns(dataset_name)
    normal_features = normal_df[feature_cols].values

    return train_lstm_ae(
        normal_features,
        input_dim=len(feature_cols),
    )


def run_stage3_train_all() -> dict[str, tuple]:
    """4データセット全てでLSTM-AEを学習する

    Returns:
        {データセット名: (model, scaler, seq_length)}
    """
    results = {}
    for ds in ALL_DATASETS:
        results[ds] = run_stage3_train(ds)
    return results
