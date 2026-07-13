// Which knowledge-base connection fields each retriever adapter needs. Mirrors the
// params the Python adapters in pressf/retrievers/ actually read. Pure data — this
// module is imported by both the Electron main process and the renderer form.

export type RetrieverFieldKey =
  | "path"
  | "url"
  | "uri"
  | "dsn"
  | "collection"
  | "index"
  | "table"
  | "index_path"
  | "mapping_path";

export type RetrieverField = {
  key: RetrieverFieldKey;
  label: string;
  placeholder: string;
  /** The first required field identifies where the knowledge base lives. */
  required?: boolean;
  kind?: "folder" | "file";
};

export type RetrieverKindSpec = {
  kind: string;
  label: string;
  fields: RetrieverField[];
};

export const RETRIEVER_PARAM_KEYS: RetrieverFieldKey[] = [
  "path",
  "url",
  "uri",
  "dsn",
  "collection",
  "index",
  "table",
  "index_path",
  "mapping_path"
];

export const RETRIEVER_KINDS: RetrieverKindSpec[] = [
  {
    kind: "docs_folder",
    label: "Folder with documents",
    fields: [{ key: "path", label: "Documents folder", placeholder: "/path/to/docs", required: true, kind: "folder" }]
  },
  {
    kind: "chunks_file",
    label: "Exported chunks (JSONL)",
    fields: [{ key: "path", label: "Chunks file", placeholder: "/path/to/chunks.jsonl", required: true, kind: "file" }]
  },
  {
    kind: "chroma",
    label: "Chroma",
    fields: [
      { key: "path", label: "Persist directory", placeholder: "/path/to/chroma", required: true, kind: "folder" },
      { key: "collection", label: "Collection", placeholder: "my-collection" }
    ]
  },
  {
    kind: "qdrant",
    label: "Qdrant",
    fields: [
      { key: "url", label: "URL", placeholder: "http://localhost:6333", required: true },
      { key: "collection", label: "Collection", placeholder: "my-collection" }
    ]
  },
  {
    kind: "weaviate",
    label: "Weaviate",
    fields: [
      { key: "url", label: "URL", placeholder: "http://localhost:8080", required: true },
      { key: "collection", label: "Collection", placeholder: "MyCollection" }
    ]
  },
  {
    kind: "milvus",
    label: "Milvus",
    fields: [
      { key: "uri", label: "URI", placeholder: "http://localhost:19530", required: true },
      { key: "collection", label: "Collection", placeholder: "my_collection" }
    ]
  },
  {
    kind: "pgvector",
    label: "pgvector (Postgres)",
    fields: [
      { key: "dsn", label: "DSN", placeholder: "postgresql://user:pass@localhost/db", required: true },
      { key: "table", label: "Table", placeholder: "chunks" }
    ]
  },
  {
    kind: "pinecone",
    label: "Pinecone",
    fields: [{ key: "index", label: "Index", placeholder: "my-index", required: true }]
  },
  {
    kind: "elastic",
    label: "Elasticsearch / OpenSearch",
    fields: [
      { key: "url", label: "URL", placeholder: "http://localhost:9200", required: true },
      { key: "index", label: "Index", placeholder: "chunks" }
    ]
  },
  {
    kind: "faiss",
    label: "FAISS",
    fields: [
      { key: "index_path", label: "Index file", placeholder: "/path/to/index.faiss", required: true, kind: "file" },
      { key: "mapping_path", label: "Mapping file", placeholder: "/path/to/mapping.jsonl", kind: "file" }
    ]
  },
  {
    kind: "lancedb",
    label: "LanceDB",
    fields: [
      { key: "uri", label: "URI / path", placeholder: "/path/to/lancedb", required: true },
      { key: "table", label: "Table", placeholder: "chunks" }
    ]
  }
];

export function retrieverSpecFor(kind: string): RetrieverKindSpec {
  return RETRIEVER_KINDS.find((spec) => spec.kind === kind) ?? RETRIEVER_KINDS[0];
}
