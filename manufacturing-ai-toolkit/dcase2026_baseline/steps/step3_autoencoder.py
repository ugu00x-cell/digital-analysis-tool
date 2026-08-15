"""
Step 3: MobileNetV2ベースCNN AutoEncoder

メルスペクトログラムを2D画像として扱い、
事前学習済みMobileNetV2をエンコーダーとして使用する

入力: (B, 1, PATCH_MELS=128, PATCH_FRAMES=64)
       → 3チャネルにブロードキャスト → MobileNetV2の入力にする
出力: (B, 1, 128, 64) 再構成スペクトログラム

非対称AE構成:
  Encoder: MobileNetV2 (ImageNet事前学習) + ボトルネック
  Decoder: ConvTranspose2dの段階的アップサンプリング
"""

import logging
import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

from dcase2026_baseline.config import (
    BATCH_SIZE,
    EARLY_STOP_PATIENCE,
    EPOCHS,
    LATENT_DIM,
    LEARNING_RATE,
    OUTPUT_DIR,
    PATCH_FRAMES,
    PATCH_MELS,
    RANDOM_SEED,
    VALIDATION_SPLIT,
)

logger = logging.getLogger(__name__)


class MobileNetEncoder(nn.Module):
    """MobileNetV2をエンコーダーとして使用する

    ImageNet事前学習重みを利用し、メルスペクトログラム
    （3チャネルにブロードキャスト）から特徴抽出する
    """

    def __init__(self, latent_dim: int = LATENT_DIM) -> None:
        super().__init__()
        # 事前学習済みMobileNetV2の特徴抽出層のみ使用
        weights = MobileNet_V2_Weights.IMAGENET1K_V1
        backbone = mobilenet_v2(weights=weights)
        self.features = backbone.features  # (B, 1280, H/32, W/32)

        # PATCH_MELS=128, PATCH_FRAMES=64の入力で
        # 出力は (B, 1280, 4, 2)
        self.pool = nn.AdaptiveAvgPool2d((4, 2))
        self.bottleneck = nn.Sequential(
            nn.Flatten(),
            nn.Linear(1280 * 4 * 2, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Linear(512, latent_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """順伝播

        Args:
            x: (B, 3, PATCH_MELS, PATCH_FRAMES) — 3ch化済み入力

        Returns:
            (B, latent_dim) 潜在表現
        """
        feat = self.features(x)
        feat = self.pool(feat)
        z = self.bottleneck(feat)
        return z


class ConvDecoder(nn.Module):
    """ConvTranspose2dベースのデコーダー

    潜在表現から元のメルスペクトログラム形状を復元する
    """

    def __init__(
        self,
        latent_dim: int = LATENT_DIM,
        out_mels: int = PATCH_MELS,
        out_frames: int = PATCH_FRAMES,
    ) -> None:
        super().__init__()
        self.out_mels = out_mels
        self.out_frames = out_frames

        # 潜在表現を初期特徴マップに展開
        # 開始サイズ: (256, 4, 2) → 最終 (1, 128, 64) を目指す
        self.fc = nn.Sequential(
            nn.Linear(latent_dim, 256 * 4 * 2),
            nn.BatchNorm1d(256 * 4 * 2),
            nn.ReLU(inplace=True),
        )

        # ConvTranspose段階: 各段でH×Wを2倍にする
        # (256,4,2) → (128,8,4) → (64,16,8) → (32,32,16) → (16,64,32) → (1,128,64)
        self.deconv = nn.Sequential(
            nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1),
            nn.BatchNorm2d(128), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1),
            nn.BatchNorm2d(64), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1),
            nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(32, 16, 4, stride=2, padding=1),
            nn.BatchNorm2d(16), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(16, 1, 4, stride=2, padding=1),
        )

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """順伝播: 潜在表現 -> (B, 1, 128, 64)"""
        h = self.fc(z).view(-1, 256, 4, 2)
        out = self.deconv(h)
        return out


class MobileNetAutoEncoder(nn.Module):
    """MobileNetV2 + ConvTranspose のオートエンコーダー

    入力: (B, 1, 128, 64) 単チャネルメルスペクトログラム
    内部: 3チャネルにブロードキャスト → MobileNetV2エンコード
    出力: (B, 1, 128, 64) 再構成
    """

    def __init__(self, latent_dim: int = LATENT_DIM) -> None:
        super().__init__()
        self.encoder = MobileNetEncoder(latent_dim)
        self.decoder = ConvDecoder(latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """順伝播

        Args:
            x: (B, 1, 128, 64) 単チャネル入力

        Returns:
            (B, 1, 128, 64) 再構成
        """
        # 単チャネル -> 3チャネルにブロードキャスト（ImageNet向け）
        x_3ch = x.repeat(1, 3, 1, 1)
        z = self.encoder(x_3ch)
        return self.decoder(z)


# ════════════════════════════════════════════════════════════
# 学習
# ════════════════════════════════════════════════════════════


def _normalize_patches(
    patches: np.ndarray,
) -> tuple[np.ndarray, StandardScaler]:
    """パッチを標準化する

    各メル次元ごとに平均0・分散1にスケーリング
    （周波数特性を保ちつつ全体スケールを揃える）

    Args:
        patches: (n_patches, mels, frames)

    Returns:
        (標準化済みパッチ, スケーラー)
    """
    n, mels, frames = patches.shape
    # メル次元ごとに統計量算出（時間方向はまとめて扱う）
    flat = patches.transpose(0, 2, 1).reshape(-1, mels)  # (n*frames, mels)
    scaler = StandardScaler()
    flat_scaled = scaler.fit_transform(flat)
    scaled = flat_scaled.reshape(n, frames, mels).transpose(0, 2, 1)
    return scaled.astype(np.float32), scaler


def apply_normalization(
    patches: np.ndarray, scaler: StandardScaler,
) -> np.ndarray:
    """学習済みスケーラーでパッチを標準化する"""
    n, mels, frames = patches.shape
    flat = patches.transpose(0, 2, 1).reshape(-1, mels)
    flat_scaled = scaler.transform(flat)
    scaled = flat_scaled.reshape(n, frames, mels).transpose(0, 2, 1)
    return scaled.astype(np.float32)


def train_autoencoder(
    patches: np.ndarray,
) -> tuple[MobileNetAutoEncoder, StandardScaler]:
    """MobileNetV2ベースのCNN AEを学習する

    Args:
        patches: 正常データのパッチ (n_patches, PATCH_MELS, PATCH_FRAMES)

    Returns:
        (学習済みモデル, スケーラー)
    """
    torch.manual_seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    # 標準化
    scaled, scaler = _normalize_patches(patches)
    # (N, mels, frames) -> (N, 1, mels, frames)
    tensor = torch.FloatTensor(scaled).unsqueeze(1)

    # 学習/検証分割
    n_val = max(1, int(len(tensor) * VALIDATION_SPLIT))
    indices = np.arange(len(tensor))
    np.random.shuffle(indices)
    train_idx = indices[n_val:]
    val_idx = indices[:n_val]

    train_x = tensor[train_idx]
    val_x = tensor[val_idx]

    train_loader = DataLoader(
        TensorDataset(train_x),
        batch_size=BATCH_SIZE, shuffle=True,
        num_workers=0, pin_memory=True,
    )

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu",
    )
    logger.info(f"学習デバイス: {device}")
    logger.info(
        f"学習パッチ数: {len(train_idx)}, "
        f"検証パッチ数: {len(val_idx)}"
    )

    model = MobileNetAutoEncoder().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=EPOCHS,
    )
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    patience_counter = 0
    best_state = None

    for epoch in range(EPOCHS):
        # 学習フェーズ
        model.train()
        train_loss = 0.0
        for (batch,) in train_loader:
            batch = batch.to(device, non_blocking=True)
            reconstructed = model(batch)
            loss = criterion(reconstructed, batch)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(batch)
        train_loss /= len(train_idx)
        scheduler.step()

        # 検証フェーズ（バッチ分割でメモリ節約）
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for i in range(0, len(val_x), BATCH_SIZE):
                vb = val_x[i:i + BATCH_SIZE].to(device, non_blocking=True)
                vr = model(vb)
                val_loss += criterion(vr, vb).item() * len(vb)
        val_loss /= len(val_x)

        # Early Stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            best_state = {
                k: v.detach().cpu().clone()
                for k, v in model.state_dict().items()
            }
        else:
            patience_counter += 1

        if (epoch + 1) % 1 == 0:
            logger.info(
                f"Epoch {epoch+1}/{EPOCHS}: "
                f"train_loss={train_loss:.6f} "
                f"val_loss={val_loss:.6f} "
                f"lr={scheduler.get_last_lr()[0]:.2e}"
            )

        if patience_counter >= EARLY_STOP_PATIENCE:
            logger.info(f"Early Stopping at epoch {epoch+1}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    logger.info(f"学習完了: best_val_loss={best_val_loss:.6f}")

    return model, scaler


def save_model(
    model: MobileNetAutoEncoder,
    scaler: StandardScaler,
    output_dir: Path = OUTPUT_DIR,
) -> None:
    """学習済みモデルとスケーラーを保存する"""
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / "autoencoder.pt")
    with open(output_dir / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    logger.info(f"モデル保存: {output_dir}")


def run_step3(
    patches: np.ndarray,
) -> tuple[MobileNetAutoEncoder, StandardScaler]:
    """Step 3を実行する（CNN版）

    Args:
        patches: 学習用2Dパッチ

    Returns:
        (学習済みモデル, スケーラー)
    """
    logger.info("=" * 60)
    logger.info("Step 3: MobileNetV2ベース CNN AutoEncoder学習")
    logger.info("=" * 60)

    model, scaler = train_autoencoder(patches)
    save_model(model, scaler)

    return model, scaler
