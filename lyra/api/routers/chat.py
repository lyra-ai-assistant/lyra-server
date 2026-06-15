import asyncio
import json
from threading import Thread

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from lyra.api.dependencies import get_agent
from lyra.services.chat import handle_chat, persist_stream
from lyra.context.manager import session_manager
from lyra.memory.semantic import retrieve_relevant
from lyra.util.base_models import ChatRequest, ChatResponse, StreamRequest
from lyra.util.context_window import trim_history

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, agent=Depends(get_agent)):
    try:
        response, session_id = handle_chat(request.text, request.session_id, agent)
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: StreamRequest, agent=Depends(get_agent)):
    session_id, history = session_manager.get_or_create(request.session_id)
    trimmed = trim_history(history)
    semantic_ctx = retrieve_relevant(request.text)

    queue: asyncio.Queue = asyncio.Queue()
    collected: list[str] = []
    loop = asyncio.get_running_loop()

    def _generate():
        for token in agent.stream_request(request.text, trimmed, semantic_ctx):
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
        persist_stream(session_id, request.text, collected)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{session_id}")
async def clear_chat(session_id: str):
    session_manager.clear(session_id)
    return {"message": "Session cleared"}
