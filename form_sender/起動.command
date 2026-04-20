#!/bin/bash
echo "========================================"
echo "  営業フォーム自動送信ツール 起動中..."
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/2] ブラウザを開いています..."
open http://localhost:8502 2>/dev/null || xdg-open http://localhost:8502 2>/dev/null
echo ""

echo "[2/2] サーバーを起動しています..."
echo ""
echo "※ この画面は閉じないでください"
echo "※ 終了するときは Ctrl+C を押してください"
echo ""
python3 -m streamlit run app.py --server.headless true --server.port 8502
