"""Unit coverage for optional retrieval adapters, without live services."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from pressf.config import RetrieverConfig
from pressf.embeddings import build_embedder
from pressf.retrievers.chroma import ChromaRetriever
from pressf.retrievers.elastic import ElasticRetriever
from pressf.retrievers.faiss_ import FaissRetriever
from pressf.retrievers.lancedb_ import LanceDBRetriever
from pressf.retrievers.milvus import MilvusRetriever
from pressf.retrievers.pgvector import PgvectorRetriever
from pressf.retrievers.pinecone_ import PineconeRetriever
from pressf.retrievers.qdrant import QdrantRetriever
from pressf.retrievers.weaviate_ import WeaviateRetriever


def _bare(cls, **attrs):
    instance = object.__new__(cls)
    instance.__dict__.update(attrs)
    return instance


class _Array:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values

    def __getitem__(self, index):
        return _Array(self.values[index])


def test_chroma_searches_text_and_vectors_and_reports_health():
    class Collection:
        name = "articles"

        def count(self):
            return 2

        def query(self, **kwargs):
            self.kwargs = kwargs
            return {"documents": [["answer"]], "ids": [["a"]], "metadatas": [[{"source": "doc"}]], "distances": [[0.2]]}

    collection = Collection()
    retriever = _bare(ChromaRetriever, _collection=collection, _query_mode="text", _get_embedder=None)
    assert retriever.search("question", 9)[0].score == 0.8
    assert collection.kwargs["query_texts"] == ["question"]
    assert retriever.search("   ", 1) == []
    retriever._query_mode = "vector"
    retriever._get_embedder = lambda: lambda query: [len(query)]
    retriever.search("q", 1)
    assert collection.kwargs["query_embeddings"] == [[1]]
    assert retriever.healthcheck() == "chroma: collection «articles», 2vectors"


def test_faiss_search_and_healthcheck_without_a_real_index(monkeypatch):
    class Index:
        ntotal = 2
        d = 3

        def search(self, vector, top_k):
            assert top_k == 2
            return _Array([[0.91, 0.2]]), _Array([[0, 1]])

    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(array=lambda values, dtype: values))
    retriever = _bare(
        FaissRetriever,
        _index=Index(),
        _mapping=[{"text": "first", "source": "one"}, {"text": "second"}],
        _get_embedder=lambda: lambda query: [1, 2, 3],
    )
    hits = retriever.search("query", 2)
    assert [(hit.source, hit.score) for hit in hits] == [("one", 0.91), ("row_1", 0.2)]
    assert retriever.search("", 2) == []
    assert retriever.healthcheck() == "faiss: 2vectors, dimension3"


def test_qdrant_searches_both_client_api_shapes_and_checks_health():
    points = [SimpleNamespace(id="p1", score=0.8, payload={"text": "found", "source": "kb"})]
    client = SimpleNamespace(
        query_points=lambda **kwargs: SimpleNamespace(points=points),
        get_collection=lambda collection: SimpleNamespace(points_count=3),
    )
    retriever = _bare(
        QdrantRetriever,
        _client=client,
        _collection="docs",
        _text_field="text",
        _source_field="source",
        _get_embedder=lambda: lambda query: [0.1],
    )
    assert retriever.search("where", 1)[0].source == "kb"
    assert retriever.search("", 1) == []
    assert retriever.healthcheck() == "qdrant: collection «docs», 3points"
    retriever._client = SimpleNamespace(search=lambda **kwargs: points)
    assert retriever.search("where", 1)[0].text == "found"


def test_pgvector_search_and_healthcheck_with_fake_connection(monkeypatch):
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args):
            self.statement = args

        def fetchall(self):
            return [("row", "source", 0.25)]

        def fetchone(self):
            return (1,)

    class Connection:
        def cursor(self):
            return Cursor()

    sql = SimpleNamespace(SQL=lambda value: SimpleNamespace(format=lambda **kwargs: value), Identifier=lambda value: value)
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(sql=sql))
    retriever = _bare(
        PgvectorRetriever,
        _conn=Connection(),
        _table="docs",
        _source_col="source",
        _get_embedder=lambda: lambda query: [0.1, 0.2],
    )
    retriever._sql = lambda: "SELECT"
    assert retriever.search("where", 1)[0].score == 0.75
    assert retriever.search("", 1) == []
    assert retriever.healthcheck() == "pgvector: table «docs», 1lines"


def test_pinecone_and_milvus_search_and_healthchecks():
    pinecone_index = SimpleNamespace(
        query=lambda **kwargs: {"matches": [{"id": "p", "score": 0.7, "metadata": {"text": "pine", "source": "docs"}}]},
        describe_index_stats=lambda: {"total_vector_count": 4},
    )
    pinecone = _bare(
        PineconeRetriever,
        _index=pinecone_index,
        _namespace=None,
        _text_field="text",
        _source_field="source",
        _get_embedder=lambda: lambda query: [1],
    )
    assert pinecone.search("question", 1)[0].text == "pine"
    assert pinecone.search("", 1) == []
    assert pinecone.healthcheck() == "pinecone: 4vectors"

    milvus_client = SimpleNamespace(
        search=lambda **kwargs: [[{"id": "m", "distance": 0.6, "entity": {"text": "milvus", "source": "docs"}}]],
        get_collection_stats=lambda collection: {"row_count": "2"},
    )
    milvus = _bare(
        MilvusRetriever,
        _client=milvus_client,
        _collection="docs",
        _vec_field="vector",
        _text_field="text",
        _source_field="source",
        _get_embedder=lambda: lambda query: [1],
    )
    assert milvus.search("question", 1)[0].score == 0.6
    assert milvus.search("", 1) == []
    assert milvus.healthcheck() == "milvus: collection «docs», 2lines"


def test_elastic_and_lancedb_search_and_healthchecks():
    elastic_client = SimpleNamespace(
        search=lambda **kwargs: {"hits": {"hits": [{"_id": "e", "_score": 0.9, "_source": {"text": "elastic", "source": "docs"}}]}},
        count=lambda **kwargs: {"count": 5},
    )
    elastic = _bare(
        ElasticRetriever,
        _client=elastic_client,
        _index="docs",
        _mode="bm25",
        _text_field="text",
        _vec_field="embedding",
        _source_field="source",
        _get_embedder=lambda: lambda query: [1],
    )
    assert elastic.search("question", 1)[0].text == "elastic"
    assert elastic.search("", 1) == []
    elastic._mode = "knn"
    assert elastic.search("question", 1)[0].source == "docs"
    assert elastic.healthcheck() == "elastic (knn): index «docs», 5documents"

    class Table:
        def search(self, vector):
            return self

        def limit(self, top_k):
            return self

        def to_list(self):
            return [{"text": "lance", "source": "docs", "_distance": 0.25}]

        def count_rows(self):
            return 7

    lance = _bare(
        LanceDBRetriever,
        _table=Table(),
        _text_field="text",
        _source_field="source",
        _get_embedder=lambda: lambda query: [1],
    )
    assert lance.search("question", 1)[0].score == 0.8
    assert lance.search("", 1) == []
    assert lance.healthcheck() == "lancedb: table,7lines"


def test_optional_retriever_constructors_accept_their_documented_config(monkeypatch, tmp_path):
    collection = SimpleNamespace(name="docs", count=lambda: 1)
    chroma_client = SimpleNamespace(get_collection=lambda name: collection)
    monkeypatch.setitem(sys.modules, "chromadb", SimpleNamespace(PersistentClient=lambda path: chroma_client))
    chroma = ChromaRetriever(RetrieverConfig(kind="chroma", path="db", collection="docs"))
    assert chroma._collection is collection

    mapping = tmp_path / "mapping.jsonl"
    mapping.write_text('{"text": "row"}\n', encoding="utf-8")
    faiss_index = SimpleNamespace(ntotal=1, d=2)
    monkeypatch.setitem(sys.modules, "faiss", SimpleNamespace(read_index=lambda path: faiss_index))
    faiss = FaissRetriever(
        RetrieverConfig(kind="faiss", index_path="index.bin", mapping_path=str(mapping)),
        get_embedder=lambda: lambda query: [1, 2],
    )
    assert faiss._mapping == [{"text": "row"}]

    qdrant_client = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "qdrant_client", SimpleNamespace(QdrantClient=lambda **kwargs: qdrant_client))
    qdrant = QdrantRetriever(
        RetrieverConfig(kind="qdrant", collection="docs"), get_embedder=lambda: lambda query: [1]
    )
    assert qdrant._client is qdrant_client

    pg_connection = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda dsn, autocommit: pg_connection))
    pgvector = PgvectorRetriever(
        RetrieverConfig(kind="pgvector", dsn="postgres://db", table="docs"),
        get_embedder=lambda: lambda query: [1],
    )
    assert pgvector._conn is pg_connection

    pinecone_index = SimpleNamespace()
    pinecone_api = SimpleNamespace(Index=lambda name: pinecone_index)
    monkeypatch.setitem(sys.modules, "pinecone", SimpleNamespace(Pinecone=lambda api_key: pinecone_api))
    pinecone = PineconeRetriever(
        RetrieverConfig(kind="pinecone", index="docs", api_key="test-key"),
        get_embedder=lambda: lambda query: [1],
    )
    assert pinecone._index is pinecone_index

    milvus_client = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=lambda **kwargs: milvus_client))
    milvus = MilvusRetriever(
        RetrieverConfig(kind="milvus", collection="docs"), get_embedder=lambda: lambda query: [1]
    )
    assert milvus._client is milvus_client

    elastic_client = SimpleNamespace()
    monkeypatch.setitem(sys.modules, "elasticsearch", SimpleNamespace(Elasticsearch=lambda url, **kwargs: elastic_client))
    elastic = ElasticRetriever(RetrieverConfig(kind="elastic", index="docs", api_key="key"))
    assert elastic._client is elastic_client

    lance_table = SimpleNamespace()
    monkeypatch.setitem(
        sys.modules,
        "lancedb",
        SimpleNamespace(connect=lambda uri: SimpleNamespace(open_table=lambda name: lance_table)),
    )
    lance = LanceDBRetriever(
        RetrieverConfig(kind="lancedb", uri="db", table="docs"), get_embedder=lambda: lambda query: [1]
    )
    assert lance._table is lance_table


def test_embedding_providers_build_vectors_with_fake_sdks(monkeypatch):
    class Vector:
        def tolist(self):
            return [0.1, 0.2]

    class SentenceTransformer:
        def __init__(self, model):
            self.model = model

        def encode(self, texts, show_progress_bar):
            return [Vector()]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=SentenceTransformer))
    assert build_embedder(None)("hello") == [0.1, 0.2]

    openai = SimpleNamespace(
        OpenAI=lambda: SimpleNamespace(
            embeddings=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(data=[SimpleNamespace(embedding=[0.3])]))
        )
    )
    monkeypatch.setitem(sys.modules, "openai", openai)
    assert build_embedder(SimpleNamespace(provider="openai", model="embed"))("hello") == [0.3]

    voyage = SimpleNamespace(Client=lambda: SimpleNamespace(embed=lambda texts, model: SimpleNamespace(embeddings=[[0.4]])))
    monkeypatch.setitem(sys.modules, "voyageai", voyage)
    assert build_embedder(SimpleNamespace(provider="voyage", model="voyage-test"))("hello") == [0.4]
    with pytest.raises(ValueError, match="Unknown embedding provider"):
        build_embedder(SimpleNamespace(provider="unknown", model=""))


def test_weaviate_constructor_search_and_healthcheck_without_a_service(monkeypatch):
    class ConnectionParams:
        @staticmethod
        def from_url(url, grpc_port):
            return (url, grpc_port)

    class AuthApiKey:
        def __init__(self, key):
            self.key = key

    class MetadataQuery:
        def __init__(self, distance):
            self.distance = distance

    obj = SimpleNamespace(
        uuid="id-1",
        properties={"text": "weaviate", "source": "docs"},
        metadata=SimpleNamespace(distance=0.25),
    )
    query = SimpleNamespace(
        near_text=lambda **kwargs: SimpleNamespace(objects=[obj]),
        near_vector=lambda **kwargs: SimpleNamespace(objects=[obj]),
    )
    collection = SimpleNamespace(
        query=query,
        aggregate=SimpleNamespace(over_all=lambda total_count: SimpleNamespace(total_count=2)),
    )
    client = SimpleNamespace(
        connect=lambda: None,
        collections=SimpleNamespace(get=lambda name: collection),
    )
    weaviate = SimpleNamespace(WeaviateClient=lambda **kwargs: client)
    monkeypatch.setitem(sys.modules, "weaviate", weaviate)
    monkeypatch.setitem(sys.modules, "weaviate.connect", SimpleNamespace(ConnectionParams=ConnectionParams))
    monkeypatch.setitem(sys.modules, "weaviate.auth", SimpleNamespace(AuthApiKey=AuthApiKey))
    monkeypatch.setitem(sys.modules, "weaviate.classes.query", SimpleNamespace(MetadataQuery=MetadataQuery))

    retriever = WeaviateRetriever(
        RetrieverConfig(kind="weaviate", collection="docs", api_key="key"), get_embedder=lambda: lambda query: [1]
    )
    assert retriever.search("question", 1)[0].score == 0.75
    assert retriever.search("", 1) == []
    retriever._mode = "near_vector"
    assert retriever.search("question", 1)[0].source == "docs"
    assert retriever.healthcheck() == "weaviate: collection,2objects"
