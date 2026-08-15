"""
M5Stack CoreS3 SPIFFS → PCダウンロードツール

使い方:
  1. CoreS3をUSBで接続
  2. python download_spiffs.py
  3. spiffs_dump/ にファイルが展開される

仕組み:
  esptoolでSPIFFSパーティションを丸ごと読み出し → mkspiffs で展開
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CoreS3 16MB flash の SPIFFS パーティション位置（default_16MB.csv 準拠）
SPIFFS_OFFSET = 0x00C90000
SPIFFS_SIZE   = 0x00360000  # 3,538,944 bytes

OUTPUT_DIR = Path("spiffs_dump")
DUMP_FILE  = Path("spiffs_raw.bin")


def find_com_port() -> str:
    """接続中のCOMポートを自動検出する。

    Returns:
        str: COMポート名
    """
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description.lower()
        if "usb" in desc and "bluetooth" not in desc:
            logger.info(f"検出ポート: {p.device} ({p.description})")
            return p.device
    raise RuntimeError("CoreS3が見つかりません。USB接続を確認してください。")


def find_esptool() -> str:
    """esptoolのパスを検索する。

    Returns:
        str: esptoolの実行パス
    """
    # PlatformIOのesptool
    pio_esptool = Path.home() / ".platformio/packages/tool-esptoolpy/esptool.py"
    if pio_esptool.exists():
        return f"python \"{pio_esptool}\""

    # PATHにあるか
    try:
        subprocess.run(["esptool.py", "--help"],
                       capture_output=True, check=True)
        return "esptool.py"
    except FileNotFoundError:
        pass

    # pip installされたesptool
    try:
        subprocess.run(["python", "-m", "esptool", "--help"],
                       capture_output=True, check=True)
        return "python -m esptool"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    raise RuntimeError(
        "esptoolが見つかりません。"
        "pip install esptool を実行してください。"
    )


def download_spiffs(port: str, esptool: str) -> None:
    """SPIFFSパーティションをダンプする。

    Args:
        port: COMポート名
        esptool: esptoolの実行コマンド
    """
    cmd = (
        f"{esptool} --chip esp32s3 --port {port} "
        f"read_flash {SPIFFS_OFFSET} {SPIFFS_SIZE} {DUMP_FILE}"
    )
    logger.info(f"SPIFFS読み出し中... ({SPIFFS_SIZE / 1024:.0f}KB)")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(result.stderr)
        raise RuntimeError("SPIFFS読み出し失敗")
    logger.info("SPIFFS読み出し完了")


def extract_files() -> list:
    """ダンプファイルからCSVを抽出する（簡易パーサー）。

    Returns:
        list: 抽出されたファイルパスのリスト
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    with open(DUMP_FILE, "rb") as f:
        data = f.read()

    # CSVヘッダ "timestamp_us,ax,ay,az" を探す
    header = b"timestamp_us,ax,ay,az"
    files_found = []
    pos = 0

    while True:
        idx = data.find(header, pos)
        if idx == -1:
            break

        # ヘッダの前にファイル名がある可能性を探す
        # SPIFFSのデータ部分を抽出（NULLバイトまで）
        end = data.find(b'\xff\xff\xff\xff', idx)
        if end == -1:
            end = len(data)

        csv_data = data[idx:end]
        # NULLバイトで切る
        null_pos = csv_data.find(b'\x00')
        if null_pos > 0:
            csv_data = csv_data[:null_pos]

        # テキストとしてデコード
        try:
            text = csv_data.decode('ascii', errors='ignore')
            lines = [l for l in text.split('\n') if l.strip()]
            if len(lines) > 1:
                out_name = f"vibration_{len(files_found) + 1}.csv"
                out_path = OUTPUT_DIR / out_name
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines) + '\n')
                files_found.append(out_path)
                logger.info(
                    f"抽出: {out_name} ({len(lines) - 1} samples)"
                )
        except Exception as e:
            logger.warning(f"デコード失敗: {e}")

        pos = idx + len(header) + 1

    return files_found


def main() -> None:
    """メイン処理。"""
    logger.info("=" * 50)
    logger.info("SPIFFS ダウンロードツール")
    logger.info("=" * 50)

    try:
        port = find_com_port()
        esptool = find_esptool()

        download_spiffs(port, esptool)
        files = extract_files()

        if files:
            logger.info(f"\n{len(files)} 個のCSVを抽出しました:")
            for f in files:
                logger.info(f"  → {f}")
            logger.info(
                f"\n解析コマンド:\n"
                f"  python analyze_vibration.py {files[0]}"
            )
        else:
            logger.warning("CSVファイルが見つかりませんでした")

        # ダンプファイル削除
        if DUMP_FILE.exists():
            DUMP_FILE.unlink()

    except Exception as e:
        logger.error(f"エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
