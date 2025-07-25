from __future__ import annotations
from pydantic import BaseModel, Field, conint
from typing import List, Dict, Optional, Literal

Point = List[int]
Polygon = List[Point]

class RawRoom(BaseModel):
  name: str= Field(alias="name")
  poly: Polygon = Field(alias="poly")

  def to_room(self) -> Room:
    xs = [p[0] for p in self.poly]
    ys = [p[1] for p in self.poly]

    center_x: int = int(sum(xs) / len(xs))
    center_y: int = int(sum(ys) / len(ys))

    return Room(
      id=self.name,
      polygon=self.poly,
      center=[center_x, center_y]
    )

class Room(BaseModel):
  id: str
  polygon: Polygon
  center: Point


class AgentInfo(BaseModel):
  id: str
  role: Literal["Survivor", "Infected"]
  is_knower: bool
  known_target: Optional[str] = None
  alive: bool = True

  position: Point
  heading: float

  kill_cooldown: int
  vote_cooldown: int
  chat_cooldown: int

  trust: Dict[str, float]


class InitResponse(BaseModel):
  tick: int = 0
  map_asset: str
  rooms: List[Room]
  agents: List[AgentInfo] = []
  evac_zone_id: str


class Delta(BaseModel):
  positions: Dict[str, Point] = Field(default_factory=dict)
  infections: Dict[str, bool] = Field(default_factory=dict)
  trust: Dict[str, float] = Field(default_factory=dict)
  chat: List[Dict] = Field(default_factory=list)


class Action(BaseModel):
    move: conint(ge=0, le=4) = 0           # Idle=0, N, E, S, W
    do_kill: bool = False
    do_vote: bool = False
    do_chat: bool = False
    do_think: bool = False
    suspect_idx: int = -1


class GroupChatSession(BaseModel):
  members: set[str]
  timer: int

class StepRequest(BaseModel):
  external_actions: Optional[Dict[str, Action]]


class StepResponse(BaseModel):
  tick: int
  delta: Delta


class FullState(BaseModel):
  tick: int
  map_size: Point
  tiles: List[List[int]]
  agents: List[AgentInfo]
  chat_log: List[Dict]