"""
ミニGPT - 数分で学習できる最小構成のGPT
使い方:
  1. data.txt にテキストデータを置く
  2. python mini_gpt.py
"""

import logging
import os
import time

import sentencepiece as spm
import torch
import torch.nn as nn
import torch.nn.functional as F

# ログ設定（ファイル＋コンソール両方に出力）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('training_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =====================
# GPU確認
# =====================
logger.info(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
if torch.cuda.is_available():
    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

# =====================
# 設定
# =====================
DATA_FILE     = "data.txt"
SP_MODEL_FILE = "sp_model.model"
BATCH_SIZE    = 128
BLOCK_SIZE    = 256  # サブワードは文字より長い単位なので拡大
N_EMBD        = 128
N_HEAD        = 4
N_LAYER       = 4
DROPOUT       = 0.2
LEARNING_RATE = 3e-4
MAX_ITERS     = 3000
EVAL_EVERY    = 100
DEVICE        = "cuda" if torch.cuda.is_available() else "cpu"
EARLY_STOP_PATIENCE = 5  # val lossが何回連続で上がったら停止するか

logger.info(f"使用デバイス: {DEVICE}")
logger.info(f"設定: BATCH={BATCH_SIZE}, BLOCK={BLOCK_SIZE}, EMBD={N_EMBD}, "
            f"HEAD={N_HEAD}, LAYER={N_LAYER}, DROPOUT={DROPOUT}, LR={LEARNING_RATE}")

# =====================
# データ読み込み
# =====================
if not os.path.exists(DATA_FILE):
    sample = "吾輩は猫である。名前はまだない。どこで生れたかとんと見当がつかぬ。\n" * 200
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(sample)
    logger.info(f"{DATA_FILE} がないのでサンプルデータを生成しました")

with open(DATA_FILE, encoding="utf-8") as f:
    text = f.read()

logger.info(f"テキスト長: {len(text):,} 文字")

# =====================
# SentencePieceトークナイザー
# =====================
if not os.path.exists(SP_MODEL_FILE):
    raise FileNotFoundError(
        f"{SP_MODEL_FILE} が見つかりません。先に train_tokenizer.py を実行してください"
    )

sp = spm.SentencePieceProcessor()
sp.load(SP_MODEL_FILE)
vocab_size = sp.get_piece_size()
logger.info(f"語彙数: {vocab_size} サブワード (SentencePiece)")


def encode(s: str) -> list[int]:
    """テキストをトークンIDのリストに変換する"""
    return sp.encode_as_ids(s)


def decode(ids: list[int]) -> str:
    """トークンIDのリストをテキストに復元する"""
    return sp.decode_ids(ids)


# =====================
# データ分割
# =====================
data = torch.tensor(encode(text), dtype=torch.long)
logger.info(f"トークン数: {len(data):,} （文字数の約{len(text)/len(data):.1f}倍圧縮）")
n = int(0.9 * len(data))
train_data = data[:n]
val_data   = data[n:]


def get_batch(split: str) -> tuple[torch.Tensor, torch.Tensor]:
    """学習/検証データからバッチを取得する"""
    d = train_data if split == "train" else val_data
    ix = torch.randint(len(d) - BLOCK_SIZE, (BATCH_SIZE,))
    x = torch.stack([d[i:i+BLOCK_SIZE] for i in ix])
    y = torch.stack([d[i+1:i+BLOCK_SIZE+1] for i in ix])
    return x.to(DEVICE), y.to(DEVICE)


# =====================
# モデル定義
# =====================
class Head(nn.Module):
    """シングルヘッド Self-Attention"""
    def __init__(self, head_size: int):
        super().__init__()
        self.key   = nn.Linear(N_EMBD, head_size, bias=False)
        self.query = nn.Linear(N_EMBD, head_size, bias=False)
        self.value = nn.Linear(N_EMBD, head_size, bias=False)
        self.register_buffer("tril", torch.tril(torch.ones(BLOCK_SIZE, BLOCK_SIZE)))
        self.dropout = nn.Dropout(DROPOUT)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        k = self.key(x)
        q = self.query(x)
        wei = q @ k.transpose(-2, -1) * C**-0.5
        wei = wei.masked_fill(self.tril[:T, :T] == 0, float("-inf"))
        wei = F.softmax(wei, dim=-1)
        wei = self.dropout(wei)
        v = self.value(x)
        return wei @ v


class MultiHeadAttention(nn.Module):
    """マルチヘッド Self-Attention"""
    def __init__(self, num_heads: int, head_size: int):
        super().__init__()
        self.heads = nn.ModuleList([Head(head_size) for _ in range(num_heads)])
        self.proj  = nn.Linear(N_EMBD, N_EMBD)
        self.dropout = nn.Dropout(DROPOUT)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = torch.cat([h(x) for h in self.heads], dim=-1)
        return self.dropout(self.proj(out))


class FeedForward(nn.Module):
    """フィードフォワード層"""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(N_EMBD, 4 * N_EMBD),
            nn.ReLU(),
            nn.Linear(4 * N_EMBD, N_EMBD),
            nn.Dropout(DROPOUT),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class Block(nn.Module):
    """Transformerブロック"""
    def __init__(self):
        super().__init__()
        head_size = N_EMBD // N_HEAD
        self.sa  = MultiHeadAttention(N_HEAD, head_size)
        self.ff  = FeedForward()
        self.ln1 = nn.LayerNorm(N_EMBD)
        self.ln2 = nn.LayerNorm(N_EMBD)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.sa(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x


class MiniGPT(nn.Module):
    """ミニGPT本体"""
    def __init__(self):
        super().__init__()
        self.token_embedding    = nn.Embedding(vocab_size, N_EMBD)
        self.position_embedding = nn.Embedding(BLOCK_SIZE, N_EMBD)
        self.blocks = nn.Sequential(*[Block() for _ in range(N_LAYER)])
        self.ln_f   = nn.LayerNorm(N_EMBD)
        self.head   = nn.Linear(N_EMBD, vocab_size)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        """順伝播。targetsが与えられた場合はlossも返す"""
        B, T = idx.shape
        tok_emb = self.token_embedding(idx)
        pos_emb = self.position_embedding(torch.arange(T, device=DEVICE))
        x = tok_emb + pos_emb
        x = self.blocks(x)
        x = self.ln_f(x)
        logits = self.head(x)

        loss = None
        if targets is not None:
            loss = F.cross_entropy(logits.view(-1, vocab_size), targets.view(-1))
        return logits, loss

    def generate(self, idx: torch.Tensor, max_new_tokens: int) -> torch.Tensor:
        """自己回帰で文章を生成する"""
        for _ in range(max_new_tokens):
            idx_cond = idx[:, -BLOCK_SIZE:]
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :]
            probs  = F.softmax(logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
            idx = torch.cat([idx, next_id], dim=1)
        return idx


# =====================
# 学習
# =====================
model = MiniGPT().to(DEVICE)
params = sum(p.numel() for p in model.parameters())
logger.info(f"パラメータ数: {params:,}")

optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)


@torch.no_grad()
def estimate_loss() -> dict[str, float]:
    """学習/検証データのlossを推定する（20バッチ平均）"""
    model.eval()
    losses: dict[str, float] = {}
    for split in ["train", "val"]:
        ls: list[float] = []
        for _ in range(20):
            x, y = get_batch(split)
            _, loss = model(x, y)
            ls.append(loss.item())
        losses[split] = sum(ls) / len(ls)
    model.train()
    return losses


# Early Stopping用の変数
best_val_loss: float = float('inf')
patience_counter: int = 0
best_step: int = 0
train_start = time.time()

logger.info("=== 学習開始 ===")
for step in range(MAX_ITERS):
    if step % EVAL_EVERY == 0:
        losses = estimate_loss()
        elapsed = time.time() - train_start
        gap = losses['val'] - losses['train']
        logger.info(
            f"step {step:4d}  "
            f"train: {losses['train']:.4f}  "
            f"val: {losses['val']:.4f}  "
            f"gap: {gap:.4f}  "
            f"elapsed: {elapsed:.0f}s"
        )

        # Early Stopping判定
        if losses['val'] < best_val_loss:
            best_val_loss = losses['val']
            best_step = step
            patience_counter = 0
            # ベストモデルを保存
            torch.save(model.state_dict(), "mini_gpt_sp_best.pt")
        else:
            patience_counter += 1
            logger.info(
                f"  ↑ val loss上昇 ({patience_counter}/{EARLY_STOP_PATIENCE}) "
                f"best: {best_val_loss:.4f} at step {best_step}"
            )

        if patience_counter >= EARLY_STOP_PATIENCE:
            logger.info(
                f"=== Early Stopping === "
                f"val lossが{EARLY_STOP_PATIENCE}回連続上昇 "
                f"best step: {best_step}, best val loss: {best_val_loss:.4f}"
            )
            break

    x, y = get_batch("train")
    _, loss = model(x, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

# 最終ロスを記録
total_time = time.time() - train_start
final_losses = estimate_loss()
logger.info(
    f"=== 学習完了 === "
    f"最終 train: {final_losses['train']:.4f}  "
    f"val: {final_losses['val']:.4f}  "
    f"総時間: {total_time:.0f}s ({total_time/60:.1f}min)"
)
logger.info(
    f"ベストモデル: step {best_step}, val loss: {best_val_loss:.4f}"
)

# ベストモデルを読み込んで最終保存
model.load_state_dict(torch.load("mini_gpt_sp_best.pt", map_location=DEVICE, weights_only=True))
torch.save(model.state_dict(), "mini_gpt_sp.pt")
logger.info("ベストモデルを mini_gpt_sp.pt に保存しました")

# =====================
# 文章生成
# =====================
logger.info("--- 生成テスト ---")
model.eval()

prompts = ["吾輩は猫", "主人は時々", "人間というものは", "坊っちゃんは", "先生は私に", "羅生門の下で"]
generated_texts: list[str] = []

for prompt in prompts:
    context = torch.tensor([encode(prompt)], dtype=torch.long, device=DEVICE)
    generated = model.generate(context, max_new_tokens=200)
    text_out = decode(generated[0].tolist())
    generated_texts.append(f"--- プロンプト:「{prompt}」---\n{text_out}\n")
    logger.info(f"プロンプト「{prompt}」: {text_out[:80]}...")

# ファイルに保存
with open("generated_sp.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(generated_texts))
logger.info("生成結果を generated_sp.txt に保存しました")
