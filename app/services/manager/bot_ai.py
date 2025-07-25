import random, math
from typing import List
from .nav import random_room_center
from app.config.models import Action
from .state import GameState, AgentState
from app.config.settings import settings

def _step_towards(src: tuple[int,int], dst: List[int]) -> int:
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if abs(dx) > abs(dy):
        return 2 if dx > 0 else 4
    else:
        return 3 if dy > 0 else 1

def rule_based_action(agent: AgentState, state: GameState) -> Action:
    act = Action()
    pos = agent.position

    for corpse in state.corpses:
        dist = math.hypot(corpse[0]-pos[0], corpse[1]-pos[1])
        if dist <= settings.HEAR_RADIUS * 3:
            act.do_chat = True
            agent.rally_point = [corpse[0], corpse[1]]
            return act

    visible = [
        o for o in state.agents.values()
        if o.alive and o.id != agent.id
           and math.hypot(o.position[0]-pos[0], o.position[1]-pos[1]) <= settings.FOV_DISTANCE
    ]

    if agent.role == "Survivor":
        low = [o for o in visible if agent.trust.get(o.id,1.0) < 0.4]
        if low:
            partners = [o for o in visible if agent.trust.get(o.id,1.0) >= 0.4]
            if partners:
                avgx = sum(o.position[0] for o in partners)/len(partners)
                avgy = sum(o.position[1] for o in partners)/len(partners)
                act.move = _step_towards(pos, [int(avgx), int(avgy)])
            else:
                agent.target = random_room_center(agent, state.rooms)
                act.move = _step_towards(pos, agent.target)
        elif visible and random.random()<0.2:
            act.do_chat = True
        else:
            if not agent.target or pos == agent.target:
                agent.target = random_room_center(agent, state.rooms)
            act.move = _step_towards(pos, agent.target)

    else:
        victims = [o for o in visible if o.role == "Survivor"]
        if victims:
            vic = min(
                victims,
                key=lambda o: math.hypot(o.position[0] - pos[0],
                                         o.position[1] - pos[1])
            )
            dist = math.hypot(
                vic.position[0] - pos[0],
                vic.position[1] - pos[1]
            )
            if dist <= settings.KILL_RADIUS and agent.kill_cooldown == 0:
                act.do_kill = True
            else:
                target_pos: List[int] = list(vic.position)
                act.move = _step_towards(pos, target_pos)
        else:
            if not agent.target or pos == agent.target:
                agent.target = random_room_center(agent, state.rooms)
            target_room: List[int] = list(agent.target)
            act.move = _step_towards(pos, target_room)


    if agent.is_knower and agent.role=="Survivor" and not agent.shared:
        act.do_chat = True
        agent.shared = True

    if random.random()<0.5:
        act.do_think = True
    if state.vote_session is None and random.random()<0.05:
        act.do_vote = True
        act.suspect_idx = 0 if visible else -1

    return act
