"""
rag/retrieve.py
===============
ChromaDB retrieval with a module-level singleton client.
The PersistentClient is created ONCE per process — recreating it on every
call causes 'RustBindingsAPI has no attribute bindings' under Streamlit.
"""

import sys
from pathlib import Path
from typing import Any

import chromadb
from chromadb.errors import NotFoundError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.ingest import CHROMA_DIR, COLLECTION_NAME, ingest_policies
from rag.vectorizer import embed_text

# ── Singletons — created once per process, never recreated ────────────────
_client: chromadb.PersistentClient | None = None
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection

    if _client is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        _collection = _client.get_collection(name=COLLECTION_NAME)
    except (ValueError, NotFoundError):
        ingest_policies()
        _collection = _client.get_collection(name=COLLECTION_NAME)

    return _collection


def retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    collection = _get_collection()
    result = collection.query(
        query_embeddings=[embed_text(query)],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for document, metadata, distance in zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    ):
        chunks.append(
            {
                "text": document,
                "source": metadata["source"],
                "clause": metadata["clause"],
                "title": metadata["title"],
                "distance": distance,
            }
        )
    return chunks
