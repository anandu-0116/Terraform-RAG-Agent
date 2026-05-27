import os
import psycopg2
import uuid
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

# --- NEW: OpenTelemetry Setup ---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Configure OTel to print traces to the console
provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("rag-agent-tracer")
# --------------------------------

# 1. Setup API Key and DB URL
load_dotenv()
DB_URL = os.getenv("SUPABASE_DB_URL")

# 2. Define the Tool (Now Instrumented!)
@tool
def search_enterprise_db(search_term: str) -> str:
    """Searches the enterprise database for a given keyword or topic and returns the documentation."""
    
    # We wrap the database call in a "Span" to track its latency
    with tracer.start_as_current_span("database_retrieval") as db_span:
        # We log exactly what the AI decided to search for
        db_span.set_attribute("tool.search_term", search_term)
        
        print(f"\n[Tool Execution] Agent decided to search DB for: '{search_term}'...")
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT content FROM enterprise_knowledge WHERE content ILIKE %s", (f"%{search_term}%",))
        results = cursor.fetchall()
        conn.close()
        
        # We log whether the database actually found anything
        db_span.set_attribute("tool.results_found", bool(results))
        
        if results:
            return "\n".join([row[0] for row in results])
        return "No results found in the database. Try a different search term."

# 3. Initialize the LLM Engine
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0)

# 4. Build the LangGraph Agent
tools = [search_enterprise_db]
agent_executor = create_react_agent(llm, tools=tools)

if __name__ == "__main__":
    print("Agent Initialized. Running traced query...\n")
    
    question = "According to the observability protocol, what tool is used to generate a unique conversation_id?"
    
    # Generate a unique ID for this specific user interaction
    conversation_id = str(uuid.uuid4())
    
    # We wrap the ENTIRE interaction in a parent span
    with tracer.start_as_current_span("full_agent_execution") as parent_span:
        parent_span.set_attribute("conversation_id", conversation_id)
        parent_span.set_attribute("user.question", question)
        
        # Run the agent
        response = agent_executor.invoke({"messages": [("user", question)]})
        
        print("\nFINAL ANSWER:")
        print(response["messages"][-1].content)