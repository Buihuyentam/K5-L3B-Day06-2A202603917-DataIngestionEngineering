"""PostgreSQL + pgvector storage and metadata-constrained cosine search."""
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    _FILTER_FIELDS = {"section"}

    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("database_url must not be empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute(
                SQL(
                    """
                    CREATE TABLE IF NOT EXISTS retrieval_chunks (
                        strategy TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL,
                        embedding vector({}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                    """
                ).format(SQL(str(self.dimensions)))
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS retrieval_chunks_strategy_idx "
                "ON retrieval_chunks (strategy)"
            )

    def upsert(
        self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        for vector in vectors:
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"Expected {self.dimensions}-dimensional vectors, got {len(vector)}"
                )
        vector_literal = lambda vector: "[" + ",".join(
            format(value, ".9g") for value in vector
        ) + "]"
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM retrieval_chunks WHERE strategy = %s", (strategy,))
                cursor.executemany(
                    """
                    INSERT INTO retrieval_chunks
                        (strategy, chunk_id, document_id, source, page, content, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                    """,
                    [
                        (
                            strategy,
                            chunk.chunk_id,
                            chunk.document_id,
                            chunk.source,
                            chunk.page,
                            chunk.text,
                            Jsonb(chunk.metadata),
                            vector_literal(vector),
                        )
                        for chunk, vector in zip(chunks, vectors)
                    ],
                )

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions}-dimensional query vector, got {len(query_vector)}"
            )
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        vector_literal = "[" + ",".join(format(value, ".9g") for value in query_vector) + "]"
        clauses = ["strategy = %s"]
        parameters: list[Any] = [vector_literal, strategy]
        for field, value in (filters or {}).items():
            if field not in self._FILTER_FIELDS:
                raise ValueError(f"Unsupported metadata filter: {field}")
            if not isinstance(value, str) or not value:
                raise ValueError(f"Filter {field} must have a non-empty string value")
            clauses.append("metadata ->> %s = %s")
            parameters.extend((field, value))
        parameters.extend((vector_literal, top_k))
        query = f"""
            SELECT chunk_id, document_id, source, page, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM retrieval_chunks
            WHERE {" AND ".join(clauses)}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "source": row["source"],
                "page": row["page"],
                "text": row["content"],
                "metadata": row["metadata"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

    def count(self, strategy: str) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                "SELECT count(*) FROM retrieval_chunks WHERE strategy = %s", (strategy,)
            ).fetchone()
        return int(row[0])

    def server_info(self) -> dict[str, str]:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                SELECT current_setting('server_version'),
                       (SELECT extversion FROM pg_extension WHERE extname = 'vector')
                """
            ).fetchone()
        if not row or not row[1]:
            raise RuntimeError("pgvector extension is not installed")
        return {"postgresql": row[0], "pgvector": row[1]}
