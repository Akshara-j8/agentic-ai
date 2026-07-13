import re
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when run directly as a script
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import chromadb
from chromadb.errors import NotFoundError

from rag.vectorizer import embed_texts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = PROJECT_ROOT / "data" / "policies"
CHROMA_DIR = PROJECT_ROOT / "chroma"
COLLECTION_NAME = "policy_clauses"
CLAUSE_PATTERN = re.compile(
    r"\*\*(?P<clause>[A-Z]{2,}-\d+)\s+(?P<title>[^*]+?)\.\*\*\s+(?P<body>.*?)(?=\n\n\*\*[A-Z]{2,}-\d+|\Z)",
    re.DOTALL,
)


def chunk_policy_doc(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    chunks = []
    for match in CLAUSE_PATTERN.finditer(text):
        clause = match.group("clause").strip()
        title = match.group("title").strip()
        body = " ".join(match.group("body").split())
        chunks.append(
            {
                "id": f"{path.stem}:{clause}",
                "text": f"{clause} {title}. {body}",
                "metadata": {
                    "source": path.name,
                    "clause": clause,
                    "title": title,
                },
            }
        )
    return chunks


def load_policy_chunks() -> list[dict[str, Any]]:
    chunks = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        chunks.extend(chunk_policy_doc(path))
    return chunks


def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def ingest_policies(reset: bool = True) -> int:
    chunks = load_policy_chunks()
    if not chunks:
        raise RuntimeError(f"No policy clauses found in {POLICY_DIR}")

    client = get_chroma_client()
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except NotFoundError:
            pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
        embeddings=embed_texts([chunk["text"] for chunk in chunks]),
    )
    return len(chunks)


if __name__ == "__main__":
    count = ingest_policies()
    print(f"Ingested {count} policy chunks into {CHROMA_DIR}")
