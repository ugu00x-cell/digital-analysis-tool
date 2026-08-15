# AI News Monitor - Docker Image

FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# システムパッケージ更新
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーション ファイルをコピー
COPY . .

# ログディレクトリを作成
RUN mkdir -p logs data

# 非rootユーザーで実行
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# デーモンモードで起動
CMD ["python", "main.py", "--daemon"]
