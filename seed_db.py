import os

import psycopg2
from dotenv import load_dotenv

from db import EMBEDDING_DIM, embed_documents

load_dotenv()

# 1. Connect to the database you just built
DB_URL = os.getenv("SUPABASE_DB_URL")
# print(f"TESTING URL LOAD: {DB_URL}")

# This is our new mock "Enterprise Data" focusing on our current stack
mock_pdf_text = """
INFRASTRUCTURE DEPLOYMENT GUIDE: Terraform is utilized as our primary Infrastructure-as-Code (IaC) tool.
It allows us to provision our backend database resources on Supabase declaratively, ensuring consistent cloud environments. State files must be locked and stored securely.
---
AGENT ARCHITECTURE MEMO: The new internal support bot utilizes a Retrieval-Augmented Generation (RAG) architecture.
Instead of relying on the LLM's base knowledge, the agent uses a ReAct (Reason and Act) loop to query the Supabase PostgreSQL database for the most up-to-date documentation.
---
OBSERVABILITY PROTOCOL: All AI agent tool-calls must be traced. OpenTelemetry is used to generate a unique conversation_id for each session.
This ensures we can measure the latency between the database retrieval step and the final LLM text generation step, optimizing our Eval pipelines.
"""

def seed_database():
    print("Connecting to Supabase...")
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # 2. Enable pgvector and create/upgrade the table to hold embeddings alongside content.
    # Retrieval used to be a plain ILIKE scan; ADD COLUMN IF NOT EXISTS lets this run safely
    # against a database that was already seeded before embeddings existed.
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enterprise_knowledge (
            id SERIAL PRIMARY KEY,
            content TEXT
        );
    """)
    cursor.execute(f"""
        ALTER TABLE enterprise_knowledge
        ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM});
    """)

    # 3. "Chunk" the data (split it by the '---' separators)
    chunks = [c.strip() for c in mock_pdf_text.strip().split("---")]

    # Re-seeding now costs real embedding API calls (unlike the old free-text insert),
    # so clear old rows first instead of accumulating duplicate chunks on every run.
    cursor.execute("DELETE FROM enterprise_knowledge;")

    print(f"Embedding {len(chunks)} chunks with {EMBEDDING_DIM}-dim vectors...")
    vectors = embed_documents(chunks)

    for chunk, vector in zip(chunks, vectors):
        vector_literal = "[" + ",".join(f"{v:.8f}" for v in vector) + "]"
        cursor.execute(
            "INSERT INTO enterprise_knowledge (content, embedding) VALUES (%s, %s::vector)",
            (chunk, vector_literal),
        )

    conn.commit()
    cursor.close()
    conn.close()
    print("Enterprise knowledge successfully chunked, embedded, and seeded!")

if __name__ == "__main__":
    seed_database()
