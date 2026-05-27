import os
import psycopg2
from dotenv import load_dotenv

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

    # 2. Create a table to hold our enterprise data chunks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS enterprise_knowledge (
            id SERIAL PRIMARY KEY,
            content TEXT
        );
    """)

    # 3. "Chunk" the data (split it by the '---' separators) and insert it
    chunks = mock_pdf_text.strip().split("---")
    
    for chunk in chunks:
        # We clean up the whitespace and insert it
        clean_chunk = chunk.strip()
        cursor.execute("INSERT INTO enterprise_knowledge (content) VALUES (%s)", (clean_chunk,))
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Enterprise knowledge successfully chunked and seeded!")

if __name__ == "__main__":
    seed_database()