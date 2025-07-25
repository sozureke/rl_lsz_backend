import json
import random
from pathlib import Path
from typing import Optional, cast, Literal

from fastapi import APIRouter, HTTPException
from app.config.settings import settings
from app.config.models import InitResponse, RawRoom, AgentInfo, Room
from app.services.manager.manager import GameManager

router = APIRouter()

@router.post("/init", response_model=InitResponse)
async def init_game(map_id: Optional[str] = None) -> InitResponse:
    models_dir = Path(settings.MODELS_DIR)
    json_dir = Path(settings.JSON_DIR)

    glb_files = list(models_dir.glob("*.glb"))
    if not glb_files:
        raise HTTPException(500, "No .glb maps found")
    glb_path = models_dir / map_id if map_id else random.choice(glb_files)
    if not glb_path.exists() or glb_path.suffix.lower() != ".glb":
        raise HTTPException(400, f"Map '{map_id}' not found")

    map_asset = f"/models/{glb_path.name}"

    rooms_json = json_dir / glb_path.with_suffix(".json").name
    if not rooms_json.exists():
        raise HTTPException(500, f"Rooms JSON not found for {glb_path.name}")
    raw = json.loads(rooms_json.read_text(encoding="utf-8"))

    raw_rooms = [RawRoom(**r) for r in raw.get("rooms", [])]
    rooms: list[Room] = [rr.to_room() for rr in raw_rooms]

    GameManager.initialize(map_asset=map_asset, rooms=rooms)

    state = GameManager.get_state()
    safe = state.evac_zone.id

    agents_info: list[AgentInfo] = []
    for ag in state.agents.values():
        role_literal = cast(Literal["Survivor", "Infected"], ag.role)
        agents_info.append(AgentInfo(
            id=ag.id,
            position=list(ag.position),
            role=role_literal,
            is_knower=ag.is_knower,
            known_target=ag.known_target,
            alive=ag.alive,
            heading=ag.heading,
            kill_cooldown=ag.kill_cooldown,
            vote_cooldown=ag.vote_cooldown,
            chat_cooldown=ag.chat_cooldown,
            trust=ag.trust
        ))

    return InitResponse(
        tick=state.tick,
        map_asset=map_asset,
        evac_zone_id=safe,
        rooms=rooms,
        agents=agents_info
    )