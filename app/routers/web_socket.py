from typing import Dict, Any, Literal, cast
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.manager.manager import GameManager
from app.config.models import FullState, AgentInfo
router = APIRouter()
_clients: list[WebSocket] = []

@router.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)

    state = GameManager.get_state()
    full_agents = []
    for ag in state.agents.values():
        role_literal = cast(Literal["Survivor", "Infected"], ag.role)
        full_agents.append(AgentInfo(
            id=ag.id,
            role=role_literal,
            is_knower=ag.is_knower,
            known_target=ag.known_target,
            alive=ag.alive,
            position=list(ag.position),
            heading=ag.heading,
            kill_cooldown=ag.kill_cooldown,
            vote_cooldown=ag.vote_cooldown,
            chat_cooldown=ag.chat_cooldown,
            trust=ag.trust
        ))

    full = FullState(
        tick=state.tick,
        map_size=list(state.map_size),
        tiles=state.tiles,
        agents=full_agents,
        chat_log=state.chat_log
    )
    await ws.send_json({"full_state": full.model_dump()})

    try:
        while True:
            msg: Dict[str, Any] = await ws.receive_json()
            if "external_actions" in msg:
                delta = GameManager.step_deterministic(msg["external_actions"])
                resp = {"tick": GameManager.get_state().tick, "delta": delta.model_dump()}
                await ws.send_json(resp)
    except WebSocketDisconnect:
        _clients.remove(ws)

async def broadcast(delta_json: Dict[str, Any]):
    dead = []
    for ws in _clients:
        try:
            await ws.send_json(delta_json)
        except Exception as e:
            print(e)
            dead.append(ws)

    for ws in dead:
        _clients.remove(ws)
