from fastapi import APIRouter, HTTPException

from app.config.settings import settings
from app.config.models import StepRequest, StepResponse, Delta
from app.services.manager.manager import GameManager

router = APIRouter()

@router.post("/step", response_model=StepResponse)
async def step_game(request: StepRequest):
    try:
        ext_actions = request.external_actions or {}

        if settings.MODE == "deterministic":
            delta: Delta = GameManager.step_deterministic(ext_actions)
        else:
            delta: Delta = GameManager.step_rl(ext_actions)

        state = GameManager.get_state()
        return StepResponse(tick=state.tick, delta=delta)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
