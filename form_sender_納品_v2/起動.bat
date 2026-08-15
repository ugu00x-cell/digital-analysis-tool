@echo off
pushd "%~dp0"

if not exist "%~dp0app.py" (
    echo.
    echo [エラー] ZIPを展開してから実行してください。
    echo.
    echo 手順: ZIPを右クリック → すべて展開 → フォルダ内のこのファイルを実行
    echo.
    pause
    exit /b 1
)

title 営業フォーム自動送信ツール
echo ========================================
echo   営業フォーム自動送信ツール 起動中...
echo ========================================
echo.
echo ブラウザを開いています...
start http://localhost:8502
echo.
echo サーバーを起動しています...
echo.
echo ※ この画面は閉じないでください
echo ※ 終了するときはこの画面を閉じてください
echo.
py -m streamlit run "%~dp0app.py" --server.headless true --server.port 8502
popd
pause
