"""Local, real sentence embeddings via FastEmbed; no API key or mock fallback."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, question: str) -> list[float]:
        ...


_SUPPORTED_MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": 384,
}


class MyEmbedder:
    """FastEmbed adapter using the same encoder for documents and queries."""

    def __init__(self, model_name: str) -> None:
        if model_name not in _SUPPORTED_MODELS:
            raise ValueError(f"Unsupported embedding model: {model_name}")
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.dimensions = _SUPPORTED_MODELS[model_name]
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = [vector.tolist() for vector in self._model.embed(texts)]
        if len(vectors) != len(texts):
            raise RuntimeError("Embedding provider returned an unexpected vector count")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise RuntimeError(
                f"Expected {self.dimensions}-dimensional vectors from {self.model_name}"
            )
        return vectors

    def embed_query(self, question: str) -> list[float]:
        vectors = self.embed_documents([question])
        if len(vectors) != 1:
            raise RuntimeError("Embedding provider did not return one query vector")
        return vectors[0]
