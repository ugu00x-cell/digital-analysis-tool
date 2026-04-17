"""
`python -m card_reconciliation` で実行したときのエントリポイント。

main.py の main() を呼び出すだけの薄いラッパ。
"""
import sys

from card_reconciliation.main import main

if __name__ == "__main__":
    sys.exit(main())
