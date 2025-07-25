import random
from .state import AgentState

def random_room_center(agent: AgentState, rooms: list) -> list[int]:
    current = agent.position
    centers = [r.center for r in rooms if tuple(r.center) != current]
    return random.choice(centers) if centers else list(current)
