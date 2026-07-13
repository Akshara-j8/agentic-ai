from rag.retrieve import retrieve


def retrieve_policy_snippets(query: str, limit: int = 3) -> list[dict[str, str]]:
    return retrieve(query, k=limit)
