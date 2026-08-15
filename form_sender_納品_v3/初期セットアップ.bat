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

REM === [0/4] Python の存在確認 ===
echo [0/4] Python の確認中...
where py > nul 2>&1
if %errorlevel% neq 0 (
    where python > nul 2>&1
    if %errorlevel% neq 0 (
        echo Python が見つかりません。自動インストールを試みます...
        echo.

        where winget > nul 2>&1
        if %errorlevel% neq 0 (
            echo [エラー] winget が利用できないため、自動インストールできません。
            echo 以下から手動でインストールしてください:
            echo https://www.python.org/downloads/
            echo ※ インストール時に「Add Python to PATH」にチェックを入れてください
            pause
            exit /b 1
        )

        echo winget で Python 3.13 をインストールします（数分かかります）...
        winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
        if %errorlevel% neq 0 (
            echo [エラー] Python の自動インストールに失敗しました。
            echo 手動でインストールしてください: https://www.python.org/downloads/
            pause
            exit /b 1
        )

        echo.
        echo ========================================
        echo   Python のインストールが完了しました
        echo ========================================
        echo PATH 反映のため、このウィンドウを閉じて
        echo 再度「初期セットアップ.bat」をダブルクリックしてください。
        echo.
        pause
        exit /b 0
    )
)
echo Python 確認OK
echo.

REM === [1/4] ライブラリインストール ===
echo [1/4] ライブラリをインストールしています...
echo.
py -m pip install --upgrade pip > nul 2>&1
py -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [エラー] ライブラリのインストールに失敗しました。
    pause
    exit /b 1
)
echo.

REM === [2/4] Playwright ブラウザインストール ===
echo [2/4] ブラウザエンジンをインストールしています...
echo       （初回は数分かかります）
echo.
py -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo [エラー] ブラウザエンジンのインストールに失敗。
    pause
    exit /b 1
)
echo.

REM === [3/4] 設定ファイル準備 ===
echo [3/4] 設定ファイルを準備しています...
if not exist "%~dp0.env" (
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" > nul
        echo .env ファイルを作成しました。
    )
) else (
    echo .env ファイルは既に存在します。
)
echo.

REM === [4/4] 完了 ===
echo ========================================
echo   セットアップ完了！
echo ========================================
echo.
echo 次のステップ:
echo   1. 「起動.bat」をダブルクリックしてツール起動
echo   2. 設定画面で API キー（Gemini・2Captcha）を入力
echo.
popd
pause
