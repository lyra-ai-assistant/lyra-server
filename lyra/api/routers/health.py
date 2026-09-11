import sys
import lyra.api.dependencies as deps

from fastapi import APIRouter
from lyra.agents.constants import MODEL_FILE
from lyra.context.manager import session_manager
from lyra.tools.linux import disk_usage, memory_info, cpu_info

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    is_linux = sys.platform == "linux"
    return {
        "status": "ok",
        "model": MODEL_FILE,
        "model_ready": deps._model_ready,
        "active_sessions": session_manager.active_count(),
        "disk": disk_usage(),
        "memory": memory_info() if is_linux else None,
        "cpu": cpu_info() if is_linux else None,
    }
