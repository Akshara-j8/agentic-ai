import hashlib
import math
import re


VECTOR_DIMENSIONS = 384
TOKEN_PATTERN = re.compile(r"[a-z0-9$]+")


def tokenize(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(text.lower())
    normalized = []
    for token in tokens:
        normalized.append(token)
        if token.endswith("s") and len(token) > 3:
            normalized.append(token[:-1])
    return normalized


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(text) for text in texts]

