import uvloop, asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.routers.init import router as init_router
from app.routers.step import router as step_router
from app.routers.state import router as state_router
from app.routers.web_socket import  router as ws_router, broadcast
from app.services.manager.manager import GameManager

from app.services.llm.llm_service import LLMService
# from app.services.rl_service import RLService  # подключите, когда будете тестировать RL

uvloop.install()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    LLMService.initialize()

    if settings.ENABLE_AUTO_TICK and settings.MODE == "deterministic":
        async def ticker():
            while True:
                try:
                    await asyncio.sleep(settings.TICK_DURATION)
                    try:
                        delta = GameManager.step_deterministic({})
                    except RuntimeError:
                        continue

                    payload = {
                        "tick": GameManager.get_state().tick,
                        "delta": delta.model_dump()
                    }
                    await broadcast(payload)

                except Exception as e:
                    import traceback, sys
                    traceback.print_exception(e, file=sys.stderr)

        task = asyncio.create_task(ticker())

    yield

    if settings.ENABLE_AUTO_TICK and settings.MODE == "deterministic":
        task.cancel()
        print("🚀 Auto-ticker stopped")

app = FastAPI(
    title="Social Deduction Game API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
		lifespan=lifespan
)

app.mount("/models", StaticFiles(directory=settings.MODELS_DIR), name="models")
app.mount("/json", StaticFiles(directory=settings.JSON_DIR), name="json")

app.include_router(init_router)
app.include_router(step_router)
app.include_router(state_router)
app.include_router(ws_router)


@app.get("/ping")
async def ping():
    return {"ping": "pong"}
