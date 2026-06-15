import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.GenerationAgent import GenerationAgent
from context.manager import session_manager
from memory.semantic import store_exchange, retrieve_relevant
from util.base_models import ChatRequest, ChatResponse, StreamRequest
from util.context_window import trim_history
from util.formatting import to_html
from tools.linux import disk_usage, memory_info, cpu_info

generation_agent = GenerationAgent()
_model_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model_ready
    generation_agent.warmup()
    _model_ready = True
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        session_id, history = session_manager.get_or_create(request.session_id)
        trimmed = trim_history(history)
        semantic_ctx = retrieve_relevant(request.text)
        response_text = generation_agent.handle_request(request.text, trimmed, semantic_ctx)
        session_manager.add_messages(session_id, request.text, response_text)
        store_exchange(session_id, request.text, response_text, time.time())
        return ChatResponse(response=to_html(response_text), session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: StreamRequest):
    session_id, history = session_manager.get_or_create(request.session_id)
    trimmed = trim_history(history)
    semantic_ctx = retrieve_relevant(request.text)

    queue: asyncio.Queue = asyncio.Queue()
    collected: list[str] = []
    loop = asyncio.get_running_loop()

    def _generate():
        for token in generation_agent.stream_request(request.text, trimmed, semantic_ctx):
            asyncio.run_coroutine_threadsafe(queue.put(token), loop)
            collected.append(token)
        asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    Thread(target=_generate, daemon=True).start()

    async def event_stream():
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"
        while True:
            token = await queue.get()
            if token is None:
                break
            yield f"data: {json.dumps({'token': token})}\n\n"
        full_response = "".join(collected)
        session_manager.add_messages(session_id, request.text, full_response)
        store_exchange(session_id, request.text, full_response, time.time())
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.delete("/chat/{session_id}")
async def clear_chat(session_id: str):
    session_manager.clear(session_id)
    return {"message": "Session cleared"}


@app.get("/health")
async def health():
    is_linux = sys.platform == "linux"
    return {
        "status": "ok",
        "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "model_ready": _model_ready,
        "active_sessions": session_manager.active_count(),
        "disk": disk_usage(),
        "memory": memory_info() if is_linux else None,
        "cpu": cpu_info() if is_linux else None,
    }
