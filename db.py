"""
Shared retrieval layer for the enterprise knowledge base.

Used by both seed_db.py (to embed and store documents) and agent.py / server.py
(to embed a query and pull back the nearest chunks by cosine distance).

Retrieval used to be a plain `ILIKE '%term%'` scan, which only works when the
user's wording happens to appear verbatim in a document. This module replaces
that with real semantic search: embed the query with the same model used to
embed the documents, then rank by vector distance in Postgres via pgvector.

Embedding and DB calls are wrapped with retries, since both are network calls
to third-party services that can throttle or hiccup transiently. Callers get
a single `RetrievalError` on exhausted retries instead of a raw traceback.
"""
import os

import psycopg2
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL")

# Keep the model + dimensionality in one place: seed_db.py and db.py must
# agree, since the table's `embedding` column is created with a fixed width.
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768

_embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL,
    output_dimensionality=EMBEDDING_DIM,
)

_RETRY = dict(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
)


class RetrievalError(RuntimeError):
    """Raised when the embedding call or the database can't be reached after retries."""


def _to_pgvector_literal(vector: list[float]) -> str:
    """Format a Python vector as a pgvector input literal, e.g. '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{v:.8f}" for v in vector) + "]"


@retry(**_RETRY)
def embed_text(text: str) -> list[float]:
    """Embed a single string. Retries transient failures before giving up."""
    return _embeddings.embed_query(text)


@retry(**_RETRY)
def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings (used at seed time)."""
    return _embeddings.embed_documents(texts)


@retry(**_RETRY)
def _connect():
    return psycopg2.connect(DB_URL, connect_timeout=5)


def retrieve_similar_chunks(query: str, k: int = 3) -> list[str]:
    """
    Embed `query` and return the k nearest knowledge chunks by cosine distance.

    Raises RetrievalError (never the underlying psycopg2/embedding exception)
    if either the embedding call or the database is unreachable after retries,
    so callers can decide how to degrade gracefully.
    """
    try:
        query_vector = embed_text(query)
    except Exception as exc:
        raise RetrievalError(f"embedding call failed after retries: {exc}") from exc

    try:
        conn = _connect()
    except Exception as exc:
        raise RetrievalError(f"database connection failed after retries: {exc}") from exc

    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT content
                FROM enterprise_knowledge
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (_to_pgvector_literal(query_vector), k),
            )
            rows = cur.fetchall()
    except Exception as exc:
        raise RetrievalError(f"similarity search query failed: {exc}") from exc
    finally:
        conn.close()

    return [row[0] for row in rows]
