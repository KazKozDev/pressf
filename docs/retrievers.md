# Retrievers and judge providers

The built-in `docs_folder` and `chunks_file` retrievers use BM25 and need no embedding model. The project also has lazy-loaded adapters for Chroma, FAISS, Qdrant, pgvector, Pinecone, Weaviate, Milvus, Elastic/OpenSearch, and LanceDB.

Install an adapter only when you use it:

```bash
uv pip install --python .venv/bin/python -e '.[qdrant]'
# or: .[chroma], .[faiss], .[pgvector], .[pinecone], .[weaviate],
#     .[milvus], .[elastic], .[lancedb]
```

Vector-backed retrievers need an `embeddings:` section configured with the model used to build the index. `init` performs a retriever health check and sample search before it saves the project.

Anthropic is the default judge provider. OpenAI and OpenAI-compatible endpoints are supported through `lazy.yaml` or setup flags; the latter requires both a model name and `base_url`. Anthropic Batch API is used for Truth Check and Agent Trajectory when the corpus meets `batch_min_examples`; other tasks run synchronously.
