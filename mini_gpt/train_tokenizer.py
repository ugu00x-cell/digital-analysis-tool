"""
SentencePiece トークナイザーの学習スクリプト

data.txt からサブワードトークナイザーを学習し、
sp_model.model / sp_model.vocab を生成する。

使い方:
  py train_tokenizer.py
  py train_tokenizer.py --vocab_size 4000
"""

import argparse
import logging
import os

import sentencepiece as spm

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('tokenizer_log.txt', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_VOCAB_SIZE = 8000
DATA_FILE = "data.txt"
MODEL_PREFIX = "sp_model"


def train_tokenizer(data_file: str, vocab_size: int, model_prefix: str) -> None:
    """SentencePieceモデルを学習する。

    Args:
        data_file: 学習データのテキストファイルパス
        vocab_size: 語彙数
        model_prefix: 出力モデルのプレフィックス
    """
    if not os.path.exists(data_file):
        raise FileNotFoundError(f"{data_file} が見つかりません")

    # ファイルサイズをログに出力
    file_size = os.path.getsize(data_file)
    logger.info(f"学習データ: {data_file} ({file_size:,} bytes)")
    logger.info(f"語彙数: {vocab_size}")

    # SentencePiece学習
    # unigramモデル（日本語に適している）
    spm.SentencePieceTrainer.train(
        input=data_file,
        model_prefix=model_prefix,
        vocab_size=vocab_size,
        model_type='unigram',
        character_coverage=0.9995,  # 日本語向け（ほぼ全文字カバー）
        pad_id=3,  # パディングトークン
        input_sentence_size=100000,  # 学習に使う文数の上限
        shuffle_input_sentence=True,
    )

    logger.info(f"モデルを保存しました: {model_prefix}.model, {model_prefix}.vocab")

    # 動作確認
    verify_tokenizer(model_prefix, vocab_size)


def verify_tokenizer(model_prefix: str, vocab_size: int) -> None:
    """学習済みトークナイザーの動作を確認する。

    Args:
        model_prefix: モデルのプレフィックス
        vocab_size: 期待される語彙数
    """
    sp = spm.SentencePieceProcessor()
    sp.load(f"{model_prefix}.model")

    actual_vocab = sp.get_piece_size()
    logger.info(f"実際の語彙数: {actual_vocab}")

    # テストエンコード・デコード
    test_texts = [
        "吾輩は猫である。",
        "名前はまだない。",
        "主人は時々書斎の中で大きな声を出す。",
    ]

    for text in test_texts:
        # サブワード分割の様子を表示
        pieces = sp.encode_as_pieces(text)
        ids = sp.encode_as_ids(text)
        decoded = sp.decode_ids(ids)
        logger.info(f"原文: {text}")
        logger.info(f"  分割: {pieces}")
        logger.info(f"  ID数: {len(ids)}")
        logger.info(f"  復元: {decoded}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SentencePieceトークナイザー学習")
    parser.add_argument("--vocab_size", type=int, default=DEFAULT_VOCAB_SIZE,
                        help=f"語彙数（デフォルト: {DEFAULT_VOCAB_SIZE}）")
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    train_tokenizer(DATA_FILE, args.vocab_size, MODEL_PREFIX)
