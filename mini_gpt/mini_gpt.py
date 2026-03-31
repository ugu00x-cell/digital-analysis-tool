"""
ミニGPT - 数分で学習できる最小構成のGPT
使い方:
  1. data.txt にテキストデータを置く
  2. python mini_gpt.py
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import os

# =====================
# 設定（ここを変えてOK）
# =====================
DATA_FILE   = "data.txt"     # テキストデータ
BATCH_SIZE  = 64             # バッチサイズ
BLOCK_SIZE  = 128            # 一度に見るトークン数
N_EMBD      = 256            # 埋め込み次元
N_HEAD      = 8              # アテンションヘッド数
N_LAYER     = 6              # Transformerの層数
DROPOUT     = 0.1
LEARNING_RATE = 3e-4
MAX_ITERS   = 3000           # 学習ステップ数（増やすと精度UP）
EVAL_EVERY  = 500            # 何ステップごとにlossを表示
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"

print(f"使用デバイス: {DEVICE}")

# =====================
# データ読み込み
# =====================
if not os.path.exists(DATA_FILE):
    # サンプルデータ（data.txtがない場合）
    sample = "吾輩は猫である。名前はまだない。どこで生れたかとんと見当がつかぬ。\n" * 200
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(sample)
    print(f"{DATA_FILE} がないのでサンプルデータを生成しました")

with open(DATA_FILE, encoding="utf-8") as f:
    text = f.read()

print(f"テキスト長: {len(text):,} 文字")

# =====================
# 文字レベルトークナイザー
# =====================
chars = sorted(set(text))
vocab_size = len(chars)
print(f"語彙数: {vocab_size} 文字")

stoi = {c: i for i, c in enumerate(chars)}
itos = {i: c for i, c in enumerate(chars)}
encode = lambda s: [stoi[c] for c in s]
decode = lambda l: "".join([itos[i] for i in l])

# =====================
# データ分割
# =====================
data = torch.tensor(encode(text), dtype=torch.long)
n = int(0.9 * len(data))
train_data = data[:n]
val_data   = data[n:]

def get_batch(split):
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
    def __init__(self, head_size):
        super().__init__()
        self.key   = nn.Linear(N_EMBD, head_size, bias=False)
        self.query = nn.Linear(N_EMBD, head_size, bias=False)
        self.value = nn.Linear(N_EMBD, head_size, bias=False)
        self.register_buffer("tril", torch.tril(torch.ones(BLOCK_SIZE, BLOCK_SIZE)))
        self.dropout = nn.Dropout(DROPOUT)

    def forward(self, x):
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
    def __init__(self, num_heads, head_size):
        super().__init__()
        self.heads = nn.ModuleList([Head(head_size) for _ in range(num_heads)])
        self.proj  = nn.Linear(N_EMBD, N_EMBD)
        self.dropout = nn.Dropout(DROPOUT)

    def forward(self, x):
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

    def forward(self, x):
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

    def forward(self, x):
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

    def forward(self, idx, targets=None):
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

    def generate(self, idx, max_new_tokens):
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
print(f"パラメータ数: {params:,}")

optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

@torch.no_grad()
def estimate_loss():
    model.eval()
    losses = {}
    for split in ["train", "val"]:
        ls = []
        for _ in range(20):
            x, y = get_batch(split)
            _, loss = model(x, y)
            ls.append(loss.item())
        losses[split] = sum(ls) / len(ls)
    model.train()
    return losses

print("\n学習開始！")
for step in range(MAX_ITERS):
    if step % EVAL_EVERY == 0:
        losses = estimate_loss()
        print(f"step {step:4d}  train loss: {losses['train']:.4f}  val loss: {losses['val']:.4f}")

    x, y = get_batch("train")
    _, loss = model(x, y)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

print("\n学習完了！")

# =====================
# 文章生成
# =====================
print("\n--- 生成テスト ---")
context = torch.zeros((1, 1), dtype=torch.long, device=DEVICE)
generated = model.generate(context, max_new_tokens=200)
print(decode(generated[0].tolist()))

# モデル保存
torch.save(model.state_dict(), "mini_gpt.pt")
print("\nモデルを mini_gpt.pt に保存しました")
