from rag.ingest import chunk_policy_doc, ingest_policies, load_policy_chunks


def load_policy_documents() -> list[dict[str, str]]:
    documents: list[dict[str, str]] = []
    for chunk in load_policy_chunks():
        documents.append(
            {
                "source": chunk["metadata"]["source"],
                "clause": chunk["metadata"]["clause"],
                "text": chunk["text"],
            }
        )
    return documents
