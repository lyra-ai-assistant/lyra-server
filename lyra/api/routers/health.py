import sys
from fastapi import APIRouter
from lyra.api.dependencies import _model_ready
from lyra.context.manager import session_manager
from lyra.tools.linux import disk_usage, memory_info, cpu_info

router = APIRouter(tags=["health"])


@router.get("/health")
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
