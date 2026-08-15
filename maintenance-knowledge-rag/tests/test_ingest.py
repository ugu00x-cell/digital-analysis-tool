"""ingest.py のテスト。

埋め込みモデルのダウンロードを避けるため、HuggingFaceEmbeddings は
FakeEmbeddings に差し替えて軽量に検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from src.ingest import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    build_vectorstore,
    split_documents,
)


# ---- split_documents 正常系 ----

def test_split_documents_short_input_unchanged() -> None:
    """チャンクサイズ未満の Document はそのまま1件として残ること。"""
    docs = [Document(page_content="短いテキスト", metadata={"source": "保全記録"})]
    chunks = split_documents(docs)
    assert len(chunks) == 1
    assert chunks[0].metadata["source"] == "保全記録"


def test_split_documents_preserves_metadata() -> None:
    """分割後もメタデータが継承されること。"""
    long_text = "あ" * (CHUNK_SIZE * 3)
    docs = [Document(page_content=long_text,
                     metadata={"machine_id": "MC003", "source": "トラブル履歴"})]
    chunks = split_documents(docs)
    assert len(chunks) >= 2  # 分割される
    for c in chunks:
        assert c.metadata["machine_id"] == "MC003"
        assert c.metadata["source"] == "トラブル履歴"


# ---- 境界値: ちょうどチャンクサイズ ----

def test_split_documents_at_chunk_size_boundary() -> None:
    """ちょうど CHUNK_SIZE 文字なら1チャンクに収まること。"""
    docs = [Document(page_content="あ" * CHUNK_SIZE, metadata={})]
    chunks = split_documents(docs)
    assert len(chunks) == 1


# ---- build_vectorstore 異常系 ----

def test_build_vectorstore_empty_docs_raises(tmp_path: Path) -> None:
    """空のリストは ValueError。"""
    with pytest.raises(ValueError):
        build_vectorstore([], tmp_path / "db", FakeEmbeddings(size=8))


# ---- build_vectorstore 正常系（Fake埋め込み） ----

def test_build_vectorstore_persists_and_retrieves(tmp_path: Path) -> None:
    """FakeEmbeddings でDB構築 → 類似検索が動くこと。"""
    docs = [
        Document(page_content="ベアリング異音発生",
                 metadata={"source": "保全記録", "machine_id": "MC003", "date": "2024-01-01"}),
        Document(page_content="クーラント交換実施",
                 metadata={"source": "保全記録", "machine_id": "MC005", "date": "2024-01-02"}),
    ]
    vs = build_vectorstore(docs, tmp_path / "db", FakeEmbeddings(size=8), reset=True)
    results = vs.similarity_search("ベアリング", k=1)
    assert len(results) == 1
    assert results[0].metadata["machine_id"] in {"MC003", "MC005"}


# ---- 設定値の固定確認 ----

def test_chunk_constants_match_spec() -> None:
    """チャンクサイズ・オーバーラップが仕様書通りであること。"""
    assert CHUNK_SIZE == 300
    assert CHUNK_OVERLAP == 50
