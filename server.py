"""
Streams the RAG agent's ReAct steps to a WebSocket client as they happen.

agent.py's __main__ block calls `agent_executor.invoke(...)`, which blocks for
the entire multi-step loop (tool call -> DB round-trip -> LLM generation)
before returning anything. That's fine for a one-shot script, but no real
chat/agent interface works that way: users watch a live sequence of "thinking
-> searching -> answering" instead of a blank screen. This module exposes the
same agent over a WebSocket and streams each step as it completes.

Run:      python server.py
Connect:  send {"question": "..."} as JSON text; you'll receive a stream of
          JSON events ({"type": "human"|"ai"|"tool"|"error"|"done", ...})
          as the agent works through the question, ending in "done".
"""
import asyncio
import json
import uuid

import websockets
from opentelemetry.trace import Status, StatusCode

from agent import agent_executor, tracer

HOST = "localhost"
PORT = 8765


def _message_to_event(message) -> dict:
    """Turn a LangChain message into a small JSON-serializable event."""
    event = {
        "type": getattr(message, "type", message.__class__.__name__),
        "content": getattr(message, "content", ""),
    }
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        event["tool_calls"] = [
            {"name": call.get("name"), "args": call.get("args")} for call in tool_calls
        ]
    return event


async def stream_answer(websocket, question: str) -> None:
    conversation_id = str(uuid.uuid4())

    with tracer.start_as_current_span("full_agent_execution") as parent_span:
        parent_span.set_attribute("conversation_id", conversation_id)
        parent_span.set_attribute("user.question", question)
        await websocket.send(json.dumps({"type": "start", "conversation_id": conversation_id}))

        seen = 0
        try:
            # stream_mode="values" yields the full running message list after
            # each graph step; we forward only the messages appended since the
            # last step so the client sees each tool call/result/answer live.
            async for state in agent_executor.astream(
                {"messages": [("user", question)]}, stream_mode="values"
            ):
                messages = state["messages"]
                for message in messages[seen:]:
                    await websocket.send(json.dumps(_message_to_event(message)))
                seen = len(messages)
        except Exception as exc:
            parent_span.record_exception(exc)
            parent_span.set_status(Status(StatusCode.ERROR, str(exc)))
            await websocket.send(json.dumps({"type": "error", "detail": str(exc)}))
            return

        await websocket.send(json.dumps({"type": "done", "conversation_id": conversation_id}))


async def handler(websocket) -> None:
    async for raw in websocket:
        try:
            payload = json.loads(raw)
            question = payload["question"]
        except (json.JSONDecodeError, KeyError, TypeError):
            await websocket.send(
                json.dumps({"type": "error", "detail": 'expected {"question": "..."}'})
            )
            continue
        await stream_answer(websocket, question)


async def main() -> None:
    print(f"WebSocket RAG server listening on ws://{HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run until interrupted


if __name__ == "__main__":
    asyncio.run(main())
