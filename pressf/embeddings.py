"""Embedding layer: builds a query vector for adapters, where we search ourselves.

Critical (PLAN.md §5): a person must indicate the same model that was used to build
its index - otherwise the search will return garbage. Providers - extras dependencies."""

from __future__ import annotations

from typing import Callable

from .config import EmbeddingsConfig

Embedder = Callable[[str], list[float]]

DEFAULT_MODELS = {
    "sentence_transformers": "sentence-transformers/all-MiniLM-L6-v2",
    "openai": "text-embedding-3-small",
    "voyage": "voyage-3",
}


def build_embedder(cfg: EmbeddingsConfig | None) -> Embedder:
    cfg = cfg or EmbeddingsConfig()
    provider = cfg.provider
    model = cfg.model or DEFAULT_MODELS.get(provider, "")

    if provider == "sentence_transformers":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "Need sentence-transformers: pip install 'pressf[local-embeddings]'"
            ) from e
        st = SentenceTransformer(model)

        def embed(text: str) -> list[float]:
            return st.encode([text], show_progress_bar=False)[0].tolist()

        return embed

    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError("Need openai: pip install 'pressf[openai-embeddings]'") from e
        client = OpenAI()

        def embed(text: str) -> list[float]:
            return client.embeddings.create(model=model, input=[text]).data[0].embedding

        return embed

    if provider == "voyage":
        try:
            import voyageai
        except ImportError as e:
            raise RuntimeError("Need voyageai: pip install 'pressf[voyage-embeddings]'") from e
        client = voyageai.Client()

        def embed(text: str) -> list[float]:
            return client.embed([text], model=model).embeddings[0]

        return embed

    raise ValueError(
        f"Unknown embedding provider:{provider}. "
        "Available: sentence_transformers, openai, voyage"
    )
