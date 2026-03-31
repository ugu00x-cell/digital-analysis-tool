"""
青空文庫 複数作品ダウンロード＆data.txt生成スクリプト
ZIPをDLして Shift-JIS→UTF-8変換、ルビ・注記を除去し結合する
"""

import io
import logging
import re
import urllib.request
import zipfile
from pathlib import Path

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('prepare_data.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── 対象作品リスト（青空文庫 ZIPのURL） ──────────────────
BOOKS: list[dict] = [
    # 夏目漱石
    {
        "title": "吾輩は猫である",
        "url": "https://www.aozora.gr.jp/cards/000148/files/789_ruby_5639.zip",
    },
    {
        "title": "坊っちゃん",
        "url": "https://www.aozora.gr.jp/cards/000148/files/752_ruby_2438.zip",
    },
    {
        "title": "三四郎",
        "url": "https://www.aozora.gr.jp/cards/000148/files/794_ruby_4237.zip",
    },
    {
        "title": "こころ",
        "url": "https://www.aozora.gr.jp/cards/000148/files/773_ruby_5968.zip",
    },
    {
        "title": "それから",
        "url": "https://www.aozora.gr.jp/cards/000148/files/56143_ruby_50824.zip",
    },
    # 芥川龍之介
    {
        "title": "羅生門",
        "url": "https://www.aozora.gr.jp/cards/000879/files/127_ruby_150.zip",
    },
    {
        "title": "藪の中",
        "url": "https://www.aozora.gr.jp/cards/000879/files/179_ruby_168.zip",
    },
    {
        "title": "鼻",
        "url": "https://www.aozora.gr.jp/cards/000879/files/42_ruby_154.zip",
    },
    # 太宰治
    {
        "title": "人間失格",
        "url": "https://www.aozora.gr.jp/cards/000035/files/301_ruby_5915.zip",
    },
    {
        "title": "走れメロス",
        "url": "https://www.aozora.gr.jp/cards/000035/files/1567_ruby_4948.zip",
    },
    # 森鴎外
    {
        "title": "舞姫",
        "url": "https://www.aozora.gr.jp/cards/000129/files/58126_ruby_73643.zip",
    },
]

# ZIPに含まれるtxtファイルのパターン（ルビ付きを優先）
TXT_PATTERN = re.compile(r'.*\.txt$', re.IGNORECASE)


def clean_text(raw: str) -> str:
    """青空文庫テキストからルビ・注記・ヘッダ・フッタを除去する。

    青空文庫の構造:
      タイトル/著者
      ---（区切り）---
      【テキスト中に現れる記号について】
      ---（区切り）---
      本文
      （---区切り--- 底本情報 ※ない場合もある）

    Args:
        raw: Shift-JIS→UTF-8変換済みの生テキスト

    Returns:
        クリーニング済みテキスト
    """
    # ルビ記号《》を除去（読み仮名のみ削除）
    text = re.sub(r'《[^》]*》', '', raw)
    # ルビの親文字マーク｜を除去
    text = re.sub(r'｜', '', text)
    # 注記 ［＃ ... ］ を除去
    text = re.sub(r'［＃[^］]*］', '', text)
    # 傍点記号を除去（例: ［＃「〇」に傍点］）
    text = re.sub(r'〔[^〕]*〕', '', text)

    # ヘッダ除去：「10個以上の-だけで構成された行」を区切りとして分割
    # part[0]=タイトル, part[1]=記号説明, part[2]=本文(, part[3]=底本情報)
    parts = re.split(r'\r?\n-{10,}\r?\n', text)
    if len(parts) >= 3:
        # 本文は3番目のパーツ（末尾に底本情報がある場合は除外）
        text = '\n'.join(parts[2:-1]) if len(parts) >= 4 else parts[2]
    elif len(parts) == 2:
        text = parts[1]
    # \r\n → \n に統一
    text = text.replace('\r\n', '\n')
    # 空行の連続を1行に圧縮
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def download_and_extract(book: dict, cache_dir: Path) -> str | None:
    """ZIPをダウンロードして txt を抽出・クリーニングして返す。

    Args:
        book: タイトルとURLを含む辞書
        cache_dir: ZIPキャッシュ保存先

    Returns:
        クリーニング済みテキスト、失敗時はNone
    """
    title = book["title"]
    url = book["url"]
    zip_path = cache_dir / f"{title}.zip"

    # キャッシュがなければダウンロード
    if not zip_path.exists():
        logger.info(f"ダウンロード中: {title}")
        try:
            urllib.request.urlretrieve(url, zip_path)
        except Exception as e:
            logger.error(f"DL失敗 [{title}]: {e}")
            return None
    else:
        logger.info(f"キャッシュ使用: {title}")

    # ZIPから最初のtxtを取り出す
    try:
        with zipfile.ZipFile(zip_path) as zf:
            txt_names = [n for n in zf.namelist() if TXT_PATTERN.match(n)]
            if not txt_names:
                logger.warning(f"txtファイルが見つかりません: {title}")
                return None
            # ファイル名が最も長いもの（ルビ付き）を選ぶ
            txt_name = max(txt_names, key=len)
            raw_bytes = zf.read(txt_name)
    except Exception as e:
        logger.error(f"ZIP展開失敗 [{title}]: {e}")
        return None

    # Shift-JIS でデコード
    try:
        raw_text = raw_bytes.decode('shift_jis')
    except UnicodeDecodeError:
        try:
            raw_text = raw_bytes.decode('cp932')
        except Exception as e:
            logger.error(f"デコード失敗 [{title}]: {e}")
            return None

    cleaned = clean_text(raw_text)
    logger.info(f"  → {len(cleaned):,} 文字 ({title})")
    return cleaned


def build_data_txt(output_path: Path, cache_dir: Path) -> None:
    """全作品をダウンロード＆結合して data.txt を生成する。

    Args:
        output_path: 出力先 data.txt のパス
        cache_dir: ZIPキャッシュ保存ディレクトリ
    """
    cache_dir.mkdir(exist_ok=True)
    all_texts: list[str] = []
    total_chars = 0

    for book in BOOKS:
        text = download_and_extract(book, cache_dir)
        if text:
            all_texts.append(text)
            total_chars += len(text)

    if not all_texts:
        logger.error("テキストを1つも取得できませんでした")
        return

    combined = "\n\n".join(all_texts)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(combined)

    logger.info(f"\n{'='*50}")
    logger.info(f"data.txt 生成完了: {len(all_texts)} 作品")
    logger.info(f"総文字数: {total_chars:,} 文字")
    logger.info(f"保存先: {output_path}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    script_dir = Path(__file__).parent
    build_data_txt(
        output_path=script_dir / "data.txt",
        cache_dir=script_dir / "zip_cache",
    )
