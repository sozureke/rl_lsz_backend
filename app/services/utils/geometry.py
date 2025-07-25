from typing import Tuple, List
from app.config.models import Room
from app.services.manager.state import AgentState, GameState
from math import hypot
from app.config.settings import settings


def point_in_polygon(point: Tuple[int,int], polygon: List[List[int]]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[(i+1) % n]
        intersect = ((yi > y) != (yj > y)) and \
                    (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi)
        if intersect:
            inside = not inside
    return inside

def point_in_any_room(point: Tuple[int,int], rooms: List["Room"]) -> bool:
    for room in rooms:
        if point_in_polygon(point, room.polygon):
            return True
    return False


def has_line_of_sight(a_pos: Tuple[int,int], b_pos: Tuple[int,int],
                      rooms: List["Room"]) -> bool:
    mid = ((a_pos[0] + b_pos[0]) // 2, (a_pos[1] + b_pos[1]) // 2)
    return point_in_any_room(mid, rooms)


def get_visible(agent: AgentState, state: GameState) -> list[AgentState]:
    visible: list[AgentState] = []
    for other in state.agents.values():
        if not other.alive or other.id == agent.id:
            continue
        dx = other.position[0] - agent.position[0]
        dy = other.position[1] - agent.position[1]
        dist = hypot(dx, dy)
        if dist <= settings.FOV_DISTANCE and has_line_of_sight(agent.position, other.position, state.rooms):
            visible.append(other)
    return visible