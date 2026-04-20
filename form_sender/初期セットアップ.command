#!/bin/bash
echo "========================================"
echo "  営業フォーム自動送信ツール 初期セットアップ"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/3] 必要なライブラリをインストールしています..."
echo "      （数分かかる場合があります）"
echo ""
python3 -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo ""
    echo "[エラー] ライブラリのインストールに失敗しました。"
    echo "Pythonがインストールされているか確認してください。"
    echo "https://www.python.org/downloads/"
    echo ""
    read -p "Enterキーを押して終了..."
    exit 1
fi
echo ""

echo "[2/3] ブラウザエンジンをインストールしています..."
echo "      （初回は数分かかります）"
echo ""
python3 -m playwright install chromium
if [ $? -ne 0 ]; then
    echo ""
    echo "[エラー] ブラウザエンジンのインストールに失敗しました。"
    echo ""
    read -p "Enterキーを押して終了..."
    exit 1
fi
echo ""

echo "[3/3] 設定ファイルを準備しています..."
if [ ! -f .env ]; then
    echo "OPENAI_API_KEY=sk-your-api-key-here" > .env
    echo ".envファイルを作成しました。"
else
    echo ".envファイルは既に存在します。スキップしました。"
fi
echo ""

echo "========================================"
echo "  セットアップが完了しました！"
echo "========================================"
echo ""
echo "次のステップ："
echo "  1. .env ファイルを開き、OpenAI APIキーを設定"
echo "     （なくても基本動作します）"
echo "  2. 起動.command をダブルクリックしてツールを起動"
echo ""
read -p "Enterキーを押して終了..."
