"""
Document ingestion pipeline for the College FAQ RAG Chatbot.

Pipeline:
  1. Load DOCX with Docx2txtLoader
  2. Split into overlapping chunks (RecursiveCharacterTextSplitter)
  3. Enrich metadata (filename, section heading, page)
  4. Generate embeddings via OpenAI text-embedding-3-small
     (NOTE: OpenRouter does NOT support /v1/embeddings — we call OpenAI directly)
  5. Persist vectors in ChromaDB

Run directly:
    python ingest.py
"""
import logging
import sys
from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_DIR,
    EMBEDDING_MODEL,
    KNOWLEDGE_BASE_PATH,
)
from utils import setup_logger, Timer

logger = setup_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Step 1 — Load document
# ─────────────────────────────────────────────────────────────────────────────

def load_document(file_path: Path) -> List[Document]:
    """Load a DOCX file and return a list of LangChain Document objects.

    Args:
        file_path: Absolute path to the .docx file.

    Returns:
        List of Document objects (usually one per file with Docx2txtLoader).

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"Knowledge base file not found: {file_path}\n"
            "Place knowledge_base.docx inside the data/ directory."
        )
    logger.info("Loading document: %s", file_path)
    loader = Docx2txtLoader(str(file_path))
    documents = loader.load()

    # Attach filename metadata for all pages
    for doc in documents:
        doc.metadata.setdefault("source", file_path.name)
        doc.metadata.setdefault("filename", file_path.name)

    logger.info("Loaded %d document section(s).", len(documents))
    return documents


# ─────────────────────────────────────────────────────────────────────────────
#  Step 2 — Split into chunks
# ─────────────────────────────────────────────────────────────────────────────

def _infer_section_heading(chunk_text: str) -> str:
    """Heuristically extract the section heading from the first line of a chunk.

    Args:
        chunk_text: Raw chunk content.

    Returns:
        Short heading string (≤120 chars) or 'General'.
    """
    lines = chunk_text.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        # Treat short, non-empty lines as headings
        if stripped and len(stripped) <= 120:
            return stripped
    return "General"


def split_documents(
    documents: List[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Document]:
    """Split documents into overlapping text chunks and enrich metadata.

    Metadata added per chunk:
        - chunk_id       : sequential integer index
        - chunk_size     : configured chunk size
        - chunk_overlap  : configured overlap
        - section_heading: first meaningful line (used for citations)
        - page           : page number (defaults to 1 if unavailable)
        - filename       : source file name

    Args:
        documents:    List of raw Document objects from the loader.
        chunk_size:   Target chunk character count.
        chunk_overlap: Character overlap between consecutive chunks.

    Returns:
        List of enriched Document chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: List[Document] = splitter.split_documents(documents)
    logger.info("Split into %d chunks (size=%d, overlap=%d).", len(chunks), chunk_size, chunk_overlap)

    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = idx
        chunk.metadata["chunk_size"] = chunk_size
        chunk.metadata["chunk_overlap"] = chunk_overlap
        chunk.metadata.setdefault("filename", "knowledge_base.docx")

        # Infer section heading for citations
        if not chunk.metadata.get("section_heading"):
            chunk.metadata["section_heading"] = _infer_section_heading(
                chunk.page_content
            )

        # Normalise page number
        raw_page = chunk.metadata.get("page")
        if raw_page is None or raw_page == "":
            chunk.metadata["page"] = "N/A"
        else:
            try:
                chunk.metadata["page"] = int(raw_page) + 1  # 0-indexed → 1-indexed
            except (ValueError, TypeError):
                chunk.metadata["page"] = str(raw_page)

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
#  Step 3 — Embeddings (local HuggingFace — no API key required)
# ─────────────────────────────────────────────────────────────────────────────

def get_embeddings() -> HuggingFaceEmbeddings:
    """Return a local HuggingFace embeddings instance.

    Uses all-MiniLM-L6-v2 — a fast, lightweight model (~90MB).
    Downloads automatically on first run, then cached locally.

    Returns:
        Configured HuggingFaceEmbeddings instance.
    """
    logger.info("Loading local embedding model: %s", EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Step 4 — ChromaDB vector store
# ─────────────────────────────────────────────────────────────────────────────

def create_or_load_vector_store(
    chunks: Optional[List[Document]] = None,
    persist_directory: Path = CHROMA_DB_DIR,
    collection_name: str = CHROMA_COLLECTION_NAME,
) -> Chroma:
    """Create a new ChromaDB vector store or load an existing one.

    If the persist directory already contains data the existing store is
    loaded and *chunks* is ignored — preventing duplicate ingestion.

    Args:
        chunks:            Document chunks to embed (only used on first run).
        persist_directory: Directory for ChromaDB persistence.
        collection_name:   ChromaDB collection identifier.

    Returns:
        Chroma vector store instance.
    """
    embeddings = get_embeddings()
    db_exists = (
        persist_directory.exists()
        and any(persist_directory.iterdir())
    )

    if db_exists:
        logger.info(
            "Existing vector store found at '%s'. Loading without re-ingesting.",
            persist_directory,
        )
        return Chroma(
            persist_directory=str(persist_directory),
            embedding_function=embeddings,
            collection_name=collection_name,
        )

    if not chunks:
        raise ValueError(
            "Vector store does not exist and no chunks were provided to create it."
        )

    persist_directory.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Creating new vector store at '%s' with %d chunks …",
        persist_directory,
        len(chunks),
    )
    return Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(persist_directory),
        collection_name=collection_name,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(
    file_path: Optional[Path] = None,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    force_recreate: bool = False,
) -> Chroma:
    """Run the full ingestion pipeline end-to-end.

    Args:
        file_path:      Path to the DOCX file (defaults to config value).
        chunk_size:     Characters per chunk.
        chunk_overlap:  Overlap between chunks.
        force_recreate: If True, delete existing ChromaDB and re-ingest.

    Returns:
        Populated Chroma vector store.
    """
    if file_path is None:
        file_path = KNOWLEDGE_BASE_PATH

    # Optionally wipe existing store
    if force_recreate and CHROMA_DB_DIR.exists():
        import shutil
        logger.warning("force_recreate=True — deleting existing vector store.")
        shutil.rmtree(CHROMA_DB_DIR)

    db_exists = CHROMA_DB_DIR.exists() and any(CHROMA_DB_DIR.iterdir())
    if db_exists:
        logger.info("Vector store already exists — skipping ingestion.")
        return create_or_load_vector_store()

    with Timer() as t:
        documents = load_document(file_path)
        chunks = split_documents(documents, chunk_size, chunk_overlap)
        vector_store = create_or_load_vector_store(chunks)

    logger.info(
        "Ingestion complete in %s. Total chunks stored: %d",
        t.get_formatted(),
        len(chunks),
    )
    return vector_store


def get_chunk_count() -> int:
    """Return the number of vectors currently stored in ChromaDB.

    Returns:
        Integer count, or 0 if the store is empty / inaccessible.
    """
    if not CHROMA_DB_DIR.exists() or not any(CHROMA_DB_DIR.iterdir()):
        return 0
    try:
        embeddings = get_embeddings()
        store = Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION_NAME,
        )
        return store._collection.count()
    except Exception as exc:
        logger.warning("Could not retrieve chunk count: %s", exc)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    try:
        store = run_ingestion()
        count = get_chunk_count()
        print(f"\n✅  Ingestion complete. {count} chunks stored in ChromaDB.\n")
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        sys.exit(1)
