import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import lyra.api.dependencies as deps
from lyra.api.routers import chat, health

model_ready_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, deps.generation_agent.warmup)
    deps._model_ready = True
    model_ready_event.set()
    print("Lyra server up", flush=True)
    yield
    model_ready_event.clear()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(health.router)

def run():
    import uvicorn
    from lyra.config.env_vars import env_vars
    uvicorn.run(app, host=env_vars.host, port=env_vars.api_port)

if __name__ == "__main__":
    run()
