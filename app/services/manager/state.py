from pydantic import BaseModel
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from app.config.models import Room, GroupChatSession, Action


class AgentState(BaseModel):
    id: str
    role: str
    is_knower: bool
    known_target: Optional[str]
    alive: bool
    position: Tuple[int, int]
    heading: float
    kill_cooldown: int
    vote_cooldown: int
    chat_cooldown: int
    trust: Dict[str, float]

    panic: bool = False
    panic_ticks: int = 0

    target: Optional[List[int]] = None
    shared: bool = False
    rally_point: Optional[List[int]] = None


@dataclass
class VoteSession:
    suspect_id: str
    votes: Dict[str, bool]
    timer: int

@dataclass
class GameState:
    tick: int = 0
    map_asset: str = ""
    rooms: List[Room] = field(default_factory=list)
    evac_zone: Optional[Room] = None
    evac_open: bool = False

    agents: Dict[str, AgentState] = field(default_factory=dict)
    map_size: Tuple[int, int] = (0, 0)
    tiles: List[List[int]] = field(default_factory=list)
    corpses: List[Tuple[int, int]] = field(default_factory=list)
    group_chat: Optional[GroupChatSession] = None
    pending_external: Dict[str, Action] = field(default_factory=dict)

    vote_session: Optional[VoteSession] = None
    chat_log: List[Dict] = field(default_factory=list)
