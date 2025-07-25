
from fastapi import APIRouter
from app.config.models import FullState, AgentInfo
from app.services.manager.manager import GameManager
from typing import cast
from typing import Literal

router = APIRouter()

@router.get("/state", response_model=FullState)
async def get_full_state():
    state = GameManager.get_state()

    agents = []
    for ag in state.agents.values():
        role_literal = cast(Literal["Survivor", "Infected"], ag.role)
        agents.append(AgentInfo(
            id=ag.id,
            role=role_literal,
            is_knower=ag.is_knower,
            known_target=ag.known_target,
            alive=ag.alive,
            position=[ag.position[0], ag.position[1]],
            heading=ag.heading,
            kill_cooldown=ag.kill_cooldown,
            vote_cooldown=ag.vote_cooldown,
            chat_cooldown=ag.chat_cooldown,
            trust=ag.trust
        ))

    map_size = list(state.map_size)
    tiles = state.tiles

    chat_log = state.chat_log

    return FullState(
        tick=state.tick,
        map_size=map_size,
        tiles=tiles,
        agents=agents,
        chat_log=chat_log
    )
