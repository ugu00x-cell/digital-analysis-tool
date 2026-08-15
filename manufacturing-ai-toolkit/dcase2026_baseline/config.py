"""
DCASE 2026 Task 2 Bearing ベースライン設定
"""

from pathlib import Path

# データパス
BASE_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path("./dev_Bearing")
TRAIN_DIR = DATA_ROOT / "train"
TEST_DIR = DATA_ROOT / "test"
OUTPUT_DIR = BASE_DIR / "output"

# 合成データ用（dev_Bearingが無い場合のフォールバック）
SYNTHETIC_DIR = BASE_DIR / "synthetic_data"

# 音声パラメータ
SAMPLE_RATE = 16000
DURATION_SEC = 10.0
N_SAMPLES = int(SAMPLE_RATE * DURATION_SEC)

# メルスペクトログラム
N_FFT = 1024
HOP_LENGTH = 512
N_MELS = 128
FMAX = 8000

# Dense AE用（旧バージョン互換）
N_FRAMES = 5
INPUT_DIM = N_MELS * N_FRAMES

# CNN AE用パッチ設定（MobileNetV2向け）
PATCH_MELS = 128       # 周波数方向（メル次元）
PATCH_FRAMES = 64      # 時間方向フレーム数
PATCH_STRIDE = 32      # 時間方向のずらし幅（オーバーラップあり）

# CNN AEモデル
LATENT_DIM = 128       # ボトルネック次元（CNN用に拡大）
EPOCHS = 80            # GPU利用なので延長して収束させる
BATCH_SIZE = 128       # GPU memory許容量内で大きめにして安定化
LEARNING_RATE = 3e-4   # GPU環境で少し強めに学習
VALIDATION_SPLIT = 0.1
EARLY_STOP_PATIENCE = 10

# 乱数シード
RANDOM_SEED = 42
