"""初期セットアップスクリプト - ライブラリとブラウザエンジンのインストール"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """セットアップのメイン処理"""
    # このスクリプトのあるディレクトリを基準にする
    base_dir = Path(__file__).parent.resolve()
    os.chdir(base_dir)

    print("========================================")
    print("  営業フォーム自動送信ツール 初期セットアップ")
    print("========================================")
    print()
    print(f"作業ディレクトリ: {base_dir}")
    print()

    # [1/3] ライブラリインストール
    req_path = base_dir / "requirements.txt"
    print("[1/3] 必要なライブラリをインストールしています...")
    print("      （数分かかる場合があります）")
    print()

    if not req_path.exists():
        print(f"[エラー] requirements.txt が見つかりません: {req_path}")
        input("Enterキーを押して終了...")
        sys.exit(1)

    ret = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_path)])
    if ret.returncode != 0:
        print()
        print("[エラー] ライブラリのインストールに失敗しました。")
        input("Enterキーを押して終了...")
        sys.exit(1)
    print()

    # [2/3] Playwrightブラウザインストール
    print("[2/3] ブラウザエンジンをインストールしています...")
    print("      （初回は数分かかります）")
    print()
    ret = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    if ret.returncode != 0:
        print()
        print("[エラー] ブラウザエンジンのインストールに失敗しました。")
        input("Enterキーを押して終了...")
        sys.exit(1)
    print()

    # [3/3] .envファイル準備
    print("[3/3] 設定ファイルを準備しています...")
    env_path = base_dir / ".env"
    if not env_path.exists():
        env_path.write_text("OPENAI_API_KEY=sk-your-api-key-here\n", encoding="utf-8")
        print(".envファイルを作成しました。")
    else:
        print(".envファイルは既に存在します。スキップしました。")
    print()

    print("========================================")
    print("  セットアップが完了しました！")
    print("========================================")
    print()
    print("次のステップ：")
    print("  1. .env ファイルを開き、OpenAI APIキーを設定")
    print("     （なくても基本動作します）")
    print("  2. 起動.bat（Mac: 起動.command）をダブルクリックしてツールを起動")
    print()
    input("Enterキーを押して終了...")


if __name__ == "__main__":
    main()
