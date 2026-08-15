@echo off
pushd "%~dp0"

if not exist "%~dp0requirements.txt" (
    echo.
    echo [エラー] ZIPを展開してから実行してください。
    echo.
    echo 手順: ZIPを右クリック → すべて展開 → フォルダ内のこのファイルを実行
    echo.
    pause
    exit /b 1
)

title 初期セットアップ
echo ========================================
echo   営業フォーム自動送信ツール 初期セットアップ
echo ========================================
echo.

echo [1/3] ライブラリをインストールしています...
echo.
py -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [エラー] インストール失敗。Pythonを確認してください。
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
echo.

echo [2/3] ブラウザエンジンをインストールしています...
echo.
py -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo [エラー] ブラウザエンジンのインストール失敗。
    pause
    exit /b 1
)
echo.

echo [3/3] 設定ファイルを準備しています...
if not exist "%~dp0.env" (
    echo OPENAI_API_KEY=sk-your-api-key-here> "%~dp0.env"
    echo .envファイルを作成しました。
) else (
    echo .envファイルは既に存在します。
)
echo.

echo ========================================
echo   セットアップ完了！
echo ========================================
echo.
echo 次のステップ:
echo   1. .envファイルにOpenAI APIキーを設定（任意）
echo   2. 起動.bat をダブルクリック
echo.
popd
pause
