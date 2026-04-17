#!/usr/bin/env bash
# ================================================================
# クレカ明細×発注表 消込ツール (Mac/Linux用シェルスクリプト)
#
# 使い方:
#   1. input/ フォルダに bakuraku_*.csv と orders_*.csv を置く
#   2. chmod +x run.sh （初回のみ）
#   3. ./run.sh
#
# 引数でCSVを明示指定することもできる:
#   ./run.sh --bakuraku path/to/b.csv --orders path/to/o.csv
# ================================================================

set -e

# このスクリプトがある場所の1つ上（プロジェクトルート）に移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Python実行コマンドを決定
# 優先順: py (Windows/Git Bash) → python3 (Mac/Linux) → python
# Windows のストアstub（WindowsApps配下）はスキップする
_find_python() {
    for cmd in py python3 python; do
        local path
        path=$(command -v "$cmd" 2>/dev/null || true)
        if [ -z "$path" ]; then
            continue
        fi
        # Windows App Installer の stub は実体が無いので除外
        case "$path" in
            */WindowsApps/*) continue ;;
        esac
        echo "$cmd"
        return 0
    done
    return 1
}

PY=$(_find_python) || {
    echo "[エラー] python / python3 / py のいずれも見つかりません" >&2
    exit 1
}

# 絵文字対策でUTF-8を明示
export PYTHONIOENCODING=utf-8

"$PY" -m card_reconciliation "$@"
