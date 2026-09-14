import uuid
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

# --- NEW: OpenTelemetry Setup ---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from db import RetrievalError, retrieve_similar_chunks

# Configure OTel to print traces to the console
provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("rag-agent-tracer")
# --------------------------------

# 1. Setup API Key and DB URL
load_dotenv()

# 2. Define the Tool (Now Instrumented!)
@tool
def search_enterprise_db(search_term: str) -> str:
    """Searches the enterprise database for a given keyword or topic and returns the documentation."""

    # We wrap the database call in a "Span" to track its latency
    with tracer.start_as_current_span("database_retrieval") as db_span:
        # We log exactly what the AI decided to search for
        db_span.set_attribute("tool.search_term", search_term)

        print(f"\n[Tool Execution] Agent decided to search DB for: '{search_term}'...")

        # retrieve_similar_chunks embeds the search term and ranks chunks by
        # cosine distance (real semantic search, not string matching), and
        # retries transient embedding/DB failures before giving up.
        try:
            results = retrieve_similar_chunks(search_term, k=3)
        except RetrievalError as exc:
            # A tool that's supposed to be "instrumented" but swallows its own
            # failures silently isn't observable at all — record it on the span
            # and hand the agent a usable fallback instead of a raw traceback.
            db_span.record_exception(exc)
            db_span.set_status(Status(StatusCode.ERROR, str(exc)))
            db_span.set_attribute("tool.results_found", False)
            print(f"[Tool Execution] Retrieval failed after retries: {exc}")
            # Worded deliberately to stop the ReAct loop from treating this like
            # a bad search term and burning further tool calls (and further
            # internal retries) on rephrased queries — a real outage doesn't
            # get fixed by asking again with different words, so tell the
            # agent that explicitly instead of letting it infer it.
            return (
                "TOOL UNAVAILABLE: the knowledge base infrastructure is down "
                "(connection failed after multiple retries) — this is an outage, "
                "not a missing document. Do not retry this tool with a different "
                "search term; instead, tell the user the knowledge base is "
                "temporarily unreachable and to try again later."
            )

        # We log whether the database actually found anything
        db_span.set_attribute("tool.results_found", bool(results))

        if results:
            return "\n".join(results)
        return "No results found in the database. Try a different search term."

# 3. Initialize the LLM Engine
# thinking_level="minimal": our own OTel traces showed the ReAct loop spending
# 16-32s per run almost entirely in the LLM (DB retrieval is a stable ~0.4-0.6s),
# which is Gemini's extended-thinking budget, not actual work — this is a small
# query answered from 3 short chunks, not a problem that needs multi-second
# reasoning. Dialing it down is a direct, measured response to that finding.
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash", temperature=0, thinking_level="minimal")

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