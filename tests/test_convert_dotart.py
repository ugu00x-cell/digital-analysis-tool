"""convert_dotart.py のテスト"""

import os
import sys
import tempfile

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'm5stack_cores3'))
from convert_dotart import (
    apply_pixelate,
    convert_to_dotart,
    load_image,
    reduce_colors,
    resize_to_display,
)


def _make_test_image(width: int, height: int, color: tuple = (255, 0, 0)) -> str:
    """テスト用画像を一時ファイルとして作成する"""
    img = Image.new('RGB', (width, height), color)
    path = tempfile.mktemp(suffix='.png')
    img.save(path)
    return path


# ==========================================
# load_image: 正常系
# ==========================================
class TestLoadImage:
    def test_load_valid_image(self):
        """正常な画像ファイルを読み込める"""
        path = _make_test_image(100, 100)
        img = load_image(path)
        assert img.size == (100, 100)
        os.unlink(path)

    def test_load_rgba_image(self):
        """RGBA画像も読み込める"""
        img = Image.new('RGBA', (50, 50), (255, 0, 0, 128))
        path = tempfile.mktemp(suffix='.png')
        img.save(path)
        loaded = load_image(path)
        assert loaded is not None
        os.unlink(path)

    # 異常系
    def test_load_nonexistent_file(self):
        """存在しないファイルはFileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_image("nonexistent_file.jpg")

    def test_load_invalid_file(self):
        """画像でないファイルはValueError"""
        path = tempfile.mktemp(suffix='.txt')
        with open(path, 'w') as f:
            f.write("not an image")
        with pytest.raises(ValueError):
            load_image(path)
        os.unlink(path)


# ==========================================
# resize_to_display: 正常系・境界値
# ==========================================
class TestResizeToDisplay:
    def test_landscape_image(self):
        """横長画像が320×240にリサイズされる"""
        img = Image.new('RGB', (1920, 1080))
        result = resize_to_display(img)
        assert result.size == (320, 240)

    def test_portrait_image(self):
        """縦長画像が320×240にリサイズされる"""
        img = Image.new('RGB', (1080, 1920))
        result = resize_to_display(img)
        assert result.size == (320, 240)

    def test_exact_size_image(self):
        """320×240の画像はそのままのサイズ"""
        img = Image.new('RGB', (320, 240))
        result = resize_to_display(img)
        assert result.size == (320, 240)

    def test_rgba_converted_to_rgb(self):
        """RGBA画像がRGBに変換される"""
        img = Image.new('RGBA', (640, 480))
        result = resize_to_display(img)
        assert result.mode == 'RGB'

    # 境界値
    def test_tiny_image(self):
        """1×1の極小画像でも320×240にリサイズできる"""
        img = Image.new('RGB', (1, 1), (128, 128, 128))
        result = resize_to_display(img)
        assert result.size == (320, 240)


# ==========================================
# apply_pixelate: 正常系
# ==========================================
class TestApplyPixelate:
    def test_pixel_size_2(self):
        """pixel_size=2でピクセル化され、サイズは320×240を維持"""
        img = Image.new('RGB', (320, 240))
        result = apply_pixelate(img, pixel_size=2)
        assert result.size == (320, 240)

    def test_pixel_size_1_skips(self):
        """pixel_size=1ではピクセル化しない"""
        img = Image.new('RGB', (320, 240), (100, 200, 50))
        result = apply_pixelate(img, pixel_size=1)
        assert result.size == (320, 240)

    # 異常系（大きすぎるpixel_size）
    def test_pixel_size_4(self):
        """pixel_size=4でも正常動作"""
        img = Image.new('RGB', (320, 240))
        result = apply_pixelate(img, pixel_size=4)
        assert result.size == (320, 240)

    def test_pixel_size_8(self):
        """pixel_size=8でもクラッシュしない"""
        img = Image.new('RGB', (320, 240))
        result = apply_pixelate(img, pixel_size=8)
        assert result.size == (320, 240)


# ==========================================
# reduce_colors: 正常系
# ==========================================
class TestReduceColors:
    def test_reduce_to_16_colors(self):
        """16色に減色できる"""
        img = Image.new('RGB', (320, 240))
        result = reduce_colors(img, num_colors=16, use_dither=False)
        assert result.mode == 'RGB'
        assert result.size == (320, 240)

    def test_reduce_to_32_colors(self):
        """32色に減色できる"""
        img = Image.new('RGB', (320, 240))
        result = reduce_colors(img, num_colors=32, use_dither=False)
        assert result.size == (320, 240)

    # ディザリングあり
    def test_reduce_with_dither(self):
        """ディザリング有効で減色できる"""
        img = Image.new('RGB', (320, 240))
        result = reduce_colors(img, num_colors=16, use_dither=True)
        assert result.size == (320, 240)

    # 境界値
    def test_reduce_to_8_colors(self):
        """8色の最小色数でも動作する"""
        img = Image.new('RGB', (320, 240))
        result = reduce_colors(img, num_colors=8, use_dither=False)
        assert result.size == (320, 240)


# ==========================================
# convert_to_dotart: 結合テスト
# ==========================================
class TestConvertToDotart:
    def test_full_pipeline_bmp(self):
        """全パイプラインでBMP出力される"""
        input_path = _make_test_image(800, 600, (0, 128, 255))
        output_path = tempfile.mktemp(suffix='.bmp')

        convert_to_dotart(input_path, output_path, num_colors=16, pixel_size=2)

        assert os.path.exists(output_path)
        result = Image.open(output_path)
        assert result.size == (320, 240)
        assert result.format == 'BMP'
        result.close()

        # PNGプレビューも生成される
        png_path = output_path.replace('.bmp', '.png')
        assert os.path.exists(png_path)

        os.unlink(input_path)
        os.unlink(output_path)
        os.unlink(png_path)

    def test_full_pipeline_with_dither(self):
        """ディザリング有効で全パイプライン動作"""
        input_path = _make_test_image(640, 480)
        output_path = tempfile.mktemp(suffix='.bmp')

        convert_to_dotart(input_path, output_path, num_colors=32,
                          pixel_size=4, use_dither=True)

        assert os.path.exists(output_path)
        result = Image.open(output_path)
        assert result.size == (320, 240)
        result.close()

        os.unlink(input_path)
        os.unlink(output_path)
        png_path = output_path.replace('.bmp', '.png')
        if os.path.exists(png_path):
            os.unlink(png_path)
