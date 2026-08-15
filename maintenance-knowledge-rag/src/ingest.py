"""ChromaDB 取り込みモジュール

excel_parser / ocr_mock の出力（List[Document]）をチャンク分割し、
多言語対応の埋め込みモデルでベクトル化して ChromaDB に永続化する。

仕様:
    - 埋め込みモデル: paraphrase-multilingual-mpnet-base-v2
    - チャンクサイズ: 300文字 / オーバーラップ: 50文字
    - メタデータ: machine_id / date / source

実行例:
    python src/ingest.py
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.excel_parser import parse_all
from src.ocr_mock import generate_paper_documents

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

load_dotenv()

DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"
DEFAULT_CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_db"
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
COLLECTION_NAME = "maintenance_knowledge"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50


def split_documents(docs: list[Document]) -> list[Document]:
    """Document をチャンクに分割する。

    Args:
        docs: 入力 Document リスト

    Returns:
        チャンク分割後の Document リスト（メタデータは継承）
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "、", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info("チャンク分割: %d → %d", len(docs), len(chunks))
    return chunks


def build_embeddings(model_name: str | None = None) -> HuggingFaceEmbeddings:
    """埋め込みモデルを初期化する。

    Args:
        model_name: モデル名。None なら .env または既定値を使用。

    Returns:
        HuggingFaceEmbeddings インスタンス
    """
    name = model_name or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    logger.info("埋め込みモデル読み込み: %s", name)
    return HuggingFaceEmbeddings(model_name=name)


def build_vectorstore(
    docs: list[Document],
    persist_dir: Path,
    embeddings: HuggingFaceEmbeddings,
    reset: bool = False,
) -> Chroma:
    """Document リストから ChromaDB を構築する。

    Args:
        docs: 取り込み対象の Document（チャンク分割済み想定）
        persist_dir: ChromaDB の永続化先ディレクトリ
        embeddings: 埋め込みモデル
        reset: True の場合は既存DBを削除して作り直す

    Returns:
        構築済み Chroma インスタンス

    Raises:
        ValueError: docs が空の場合
    """
    if not docs:
        raise ValueError("取り込み対象の Document が空です")
    if reset and persist_dir.exists():
        logger.warning("既存DBを削除: %s", persist_dir)
        shutil.rmtree(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    vs = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(persist_dir),
        collection_name=COLLECTION_NAME,
    )
    logger.info("取り込み完了：%d 件", len(docs))
    return vs


def collect_documents(raw_dir: Path = DEFAULT_RAW_DIR,
                       include_ocr: bool = True) -> list[Document]:
    """Excel + OCRモックから全 Document を集約する。

    Args:
        raw_dir: Excel 配置ディレクトリ
        include_ocr: True なら紙点検票OCRモックも含める

    Returns:
        Document のリスト
    """
    docs = parse_all(raw_dir)
    if include_ocr:
        docs.extend(generate_paper_documents())
    logger.info("収集ドキュメント総数: %d", len(docs))
    return docs


def main(reset: bool = True) -> None:
    """データ収集 → チャンク分割 → ChromaDB 取り込みの一気通貫処理。

    Args:
        reset: True なら既存DBを削除して作り直す
    """
    persist_dir = Path(os.getenv("CHROMA_DB_DIR", str(DEFAULT_CHROMA_DIR)))
    docs = collect_documents()
    chunks = split_documents(docs)
    embeddings = build_embeddings()
    build_vectorstore(chunks, persist_dir, embeddings, reset=reset)
    logger.info("ChromaDB 永続化先: %s", persist_dir)


if __name__ == "__main__":
    main()
