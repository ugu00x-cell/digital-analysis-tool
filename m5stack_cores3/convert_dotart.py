"""
ドット絵変換スクリプト - M5Stack CoreS3用（320×240px）

入力画像をドット絵風に減色処理し、BMP/PNG形式で出力する。
BMP形式はCoreS3の液晶にそのまま表示可能。

使い方:
  py convert_dotart.py input.jpg output.bmp
  py convert_dotart.py input.jpg output.bmp --colors 32
  py convert_dotart.py input.jpg output.bmp --colors 16 --pixel-size 4
  py convert_dotart.py input.jpg output.bmp --dither
"""

import argparse
import logging
import sys
from pathlib import Path

from PIL import Image

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('convert_dotart.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CoreS3の液晶サイズ
DISPLAY_WIDTH = 320
DISPLAY_HEIGHT = 240


def load_image(input_path: str) -> Image.Image:
    """入力画像を読み込む。

    Args:
        input_path: 入力画像のファイルパス

    Returns:
        読み込んだPIL Imageオブジェクト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: 画像として読み込めない場合
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    try:
        img = Image.open(input_path)
        img.load()  # 遅延読み込みを即座に実行
        logger.info(f"入力画像: {input_path} ({img.size[0]}×{img.size[1]}, {img.mode})")
        return img
    except Exception as e:
        raise ValueError(f"画像の読み込みに失敗しました: {e}")


def resize_to_display(img: Image.Image) -> Image.Image:
    """画像を320×240pxにリサイズする（アスペクト比を維持して中央クロップ）。

    Args:
        img: 元画像

    Returns:
        320×240pxにリサイズされた画像
    """
    # RGBに変換（RGBA/グレースケール対応）
    if img.mode != 'RGB':
        img = img.convert('RGB')
        logger.info(f"カラーモードをRGBに変換しました")

    # アスペクト比を維持してリサイズ → 中央クロップ
    target_ratio = DISPLAY_WIDTH / DISPLAY_HEIGHT  # 4:3
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # 横長 → 高さ基準でリサイズしてから横をクロップ
        new_height = DISPLAY_HEIGHT
        new_width = int(img.width * (DISPLAY_HEIGHT / img.height))
    else:
        # 縦長 → 幅基準でリサイズしてから縦をクロップ
        new_width = DISPLAY_WIDTH
        new_height = int(img.height * (DISPLAY_WIDTH / img.width))

    img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # 中央クロップ
    left = (new_width - DISPLAY_WIDTH) // 2
    top = (new_height - DISPLAY_HEIGHT) // 2
    img_cropped = img_resized.crop((left, top, left + DISPLAY_WIDTH, top + DISPLAY_HEIGHT))

    logger.info(f"リサイズ完了: {DISPLAY_WIDTH}×{DISPLAY_HEIGHT}px")
    return img_cropped


def apply_pixelate(img: Image.Image, pixel_size: int) -> Image.Image:
    """ピクセル化（モザイク処理）でドット絵風にする。

    Args:
        img: 入力画像（320×240px）
        pixel_size: 1ドットのサイズ（大きいほど粗い）

    Returns:
        ピクセル化された画像
    """
    if pixel_size <= 1:
        logger.info("pixel_size=1のためピクセル化をスキップ")
        return img

    # 縮小 → 拡大でモザイク効果を得る
    small_w = DISPLAY_WIDTH // pixel_size
    small_h = DISPLAY_HEIGHT // pixel_size

    img_small = img.resize((small_w, small_h), Image.Resampling.BILINEAR)
    img_pixelated = img_small.resize(
        (DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.NEAREST
    )

    logger.info(f"ピクセル化完了: ドットサイズ={pixel_size}px ({small_w}×{small_h}ドット)")
    return img_pixelated


def reduce_colors(img: Image.Image, num_colors: int, use_dither: bool) -> Image.Image:
    """減色処理でドット絵風の色数にする。

    Args:
        img: 入力画像（RGB）
        num_colors: 出力の色数（8/16/32/64など）
        use_dither: ディザリングを使うかどうか

    Returns:
        減色された画像（RGB）
    """
    # メディアンカット法で減色
    dither_method = Image.Dither.FLOYDSTEINBERG if use_dither else Image.Dither.NONE
    img_quantized = img.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT,
                                 dither=dither_method)

    # パレットモードからRGBに戻す
    img_rgb = img_quantized.convert('RGB')

    logger.info(f"減色完了: {num_colors}色 (ディザリング: {'あり' if use_dither else 'なし'})")
    return img_rgb


def save_bmp(img: Image.Image, output_path: str) -> None:
    """BMP形式で保存する（CoreS3表示用・24bit BMP）。

    Args:
        img: 保存する画像（RGB）
        output_path: 出力ファイルパス
    """
    try:
        img.save(output_path, format='BMP')
        file_size = Path(output_path).stat().st_size
        logger.info(f"BMP保存: {output_path} ({file_size:,} bytes)")
    except Exception as e:
        raise IOError(f"BMP保存に失敗しました: {e}")


def save_png_preview(img: Image.Image, bmp_path: str) -> None:
    """プレビュー用PNG形式で保存する。

    Args:
        img: 保存する画像（RGB）
        bmp_path: BMPファイルのパス（拡張子をpngに変えて保存）
    """
    try:
        png_path = str(Path(bmp_path).with_suffix('.png'))
        img.save(png_path, format='PNG')
        file_size = Path(png_path).stat().st_size
        logger.info(f"PNG保存: {png_path} ({file_size:,} bytes)")
    except Exception as e:
        logger.warning(f"PNGプレビュー保存に失敗しました: {e}")


def convert_to_dotart(
    input_path: str,
    output_path: str,
    num_colors: int = 16,
    pixel_size: int = 2,
    use_dither: bool = False,
) -> None:
    """画像をドット絵に変換するメイン処理。

    Args:
        input_path: 入力画像パス
        output_path: 出力BMPパス
        num_colors: 色数（デフォルト16）
        pixel_size: ドットサイズ（デフォルト2）
        use_dither: ディザリング有無
    """
    logger.info("=== ドット絵変換開始 ===")
    logger.info(f"設定: 色数={num_colors}, ドットサイズ={pixel_size}, "
                f"ディザリング={'あり' if use_dither else 'なし'}")

    # 1. 画像読み込み
    img = load_image(input_path)

    # 2. 320×240にリサイズ
    img = resize_to_display(img)

    # 3. ピクセル化（ドット感を出す）
    img = apply_pixelate(img, pixel_size)

    # 4. 減色処理
    img = reduce_colors(img, num_colors, use_dither)

    # 5. BMP保存（CoreS3用）
    save_bmp(img, output_path)

    # 6. PNGプレビュー保存
    save_png_preview(img, output_path)

    logger.info("=== 変換完了 ===")


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する。

    Returns:
        解析された引数
    """
    parser = argparse.ArgumentParser(
        description="画像をM5Stack CoreS3用ドット絵(320×240px)に変換する"
    )
    parser.add_argument("input", help="入力画像ファイルパス (jpg/png等)")
    parser.add_argument("output", help="出力BMPファイルパス")
    parser.add_argument("--colors", type=int, default=16, choices=[8, 16, 32, 64],
                        help="色数 (デフォルト: 16)")
    parser.add_argument("--pixel-size", type=int, default=2,
                        help="ドットサイズ (1=等倍, 2=粗め, 4=かなり粗い, デフォルト: 2)")
    parser.add_argument("--dither", action="store_true",
                        help="ディザリングを有効にする (グラデーション保持)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        convert_to_dotart(
            input_path=args.input,
            output_path=args.output,
            num_colors=args.colors,
            pixel_size=args.pixel_size,
            use_dither=args.dither,
        )
    except (FileNotFoundError, ValueError, IOError) as e:
        logger.error(f"エラー: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}", exc_info=True)
        sys.exit(1)
