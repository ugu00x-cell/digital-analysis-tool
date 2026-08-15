"""添付画像のURL/パスからドット絵変換を実行する一時スクリプト"""
import sys
import urllib.request
from pathlib import Path

# まずダウンロード用のURLがあればダウンロード
# なければローカルパスとして扱う
input_arg = sys.argv[1] if len(sys.argv) > 1 else None

if input_arg and input_arg.startswith("http"):
    print(f"Downloading: {input_arg}")
    urllib.request.urlretrieve(input_arg, "ganyu_input.png")
    print("Saved as ganyu_input.png")
else:
    print(f"Using local file: {input_arg}")
