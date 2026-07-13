from rag.ingest import ingest_policies
from rag.retrieve import retrieve


def main() -> None:
    ingest_policies()
    results = retrieve("refund over $50", k=3)
    for result in results:
        print(f"{result['source']} {result['clause']}: {result['text']}")

    sources = {result["source"] for result in results}
    assert "escalation-policy.md" in sources, "Expected escalation-policy.md in retrieval results"
    print("RAG retrieval smoke test passed")


if __name__ == "__main__":
    main()
