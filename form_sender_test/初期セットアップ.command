#!/bin/bash
echo "========================================"
echo "  営業フォーム自動送信ツール 初期セットアップ"
echo "========================================"
echo ""

cd "$(dirname "$0")"

# === [0/4] Python の存在確認 ===
echo "[0/4] Python の確認中..."
if ! command -v python3 &> /dev/null; then
    echo "Python が見つかりません。自動インストールを試みます..."
    echo ""

    # Homebrew の確認
    if ! command -v brew &> /dev/null; then
        echo "Homebrew が見つかりません。先に Homebrew をインストールします..."
        echo "（パスワードを2回求められます）"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ $? -ne 0 ]; then
            echo ""
            echo "[エラー] Homebrew のインストールに失敗しました。"
            echo "手動で Python をインストールしてください: https://www.python.org/downloads/"
            read -p "Enterキーを押して終了..."
            exit 1
        fi
        # PATH反映
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    echo "Python 3 をインストールします（数分かかります）..."
    brew install python@3.13
    if [ $? -ne 0 ]; then
        echo "[エラー] Python の自動インストールに失敗しました。"
        echo "手動でインストールしてください: https://www.python.org/downloads/"
        read -p "Enterキーを押して終了..."
        exit 1
    fi
fi
echo "Python 確認OK"
echo ""

# === [1/4] ライブラリインストール ===
echo "[1/4] ライブラリをインストールしています..."
echo "      （数分かかる場合があります）"
echo ""
python3 -m pip install --upgrade pip > /dev/null 2>&1
python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "[エラー] ライブラリのインストールに失敗しました。"
    read -p "Enterキーを押して終了..."
    exit 1
fi
echo ""

# === [2/4] Playwright ブラウザインストール ===
echo "[2/4] ブラウザエンジンをインストールしています..."
echo "      （初回は数分かかります）"
echo ""
python3 -m playwright install chromium
if [ $? -ne 0 ]; then
    echo ""
    echo "[エラー] ブラウザエンジンのインストールに失敗しました。"
    read -p "Enterキーを押して終了..."
    exit 1
fi
echo ""

# === [3/4] 設定ファイル準備 ===
echo "[3/4] 設定ファイルを準備しています..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        echo ".env ファイルを作成しました。"
    fi
else
    echo ".env ファイルは既に存在します。"
fi
echo ""

# === [4/4] 完了 ===
echo "========================================"
echo "  セットアップ完了！"
echo "========================================"
echo ""
echo "次のステップ："
echo "  1. 「起動.command」をダブルクリックしてツール起動"
echo "  2. 設定画面で API キー（Gemini・2Captcha）を入力"
echo ""
read -p "Enterキーを押して終了..."
