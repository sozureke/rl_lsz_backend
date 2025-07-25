from typing import Any, Dict
from .state import GameState, VoteSession
from math import hypot
from app.config.settings import (settings)
from app.config.models import Delta, Action, GroupChatSession
from ..llm.llm_service import LLMService
from ..utils.geometry import point_in_any_room, has_line_of_sight, point_in_polygon
from .bot_ai import rule_based_action
import random

def collect_actions(state: GameState, external: Dict[str, Any]) -> Dict[str, Action]:
    actions: Dict[str, Action] = {}
    for aid, ag in state.agents.items():
        if not ag.alive:
            continue
        raw = (external or {}).get(aid)
        if raw is None:
            actions[aid] = rule_based_action(ag, state)
        elif isinstance(raw, Action):
            actions[aid] = raw
        else:
            actions[aid] = Action(**raw)
    return actions

def process_movements(state: GameState, actions: Dict[str, Action], delta: Delta) -> None:
    move_map = {0:(0,0),1:(0,-1),2:(1,0),3:(0,1),4:(-1,0)}
    heading_map = {1:0.0,2:90.0,3:180.0,4:270.0}
    for aid, act in actions.items():
        if act.move == 0:
            continue
        ag = state.agents[aid]
        dx, dy = move_map[act.move]
        new_pos = (ag.position[0] + dx, ag.position[1] + dy)
        if point_in_any_room(new_pos, state.rooms):
            ag.position = new_pos
            ag.heading = heading_map[act.move]
            delta.positions[aid] = [new_pos[0], new_pos[1]]

def process_kills(state: GameState, actions: dict[str, Action], delta: Delta) -> None:
    kill_events: list[tuple[str, str]] = []
    for aid, act in actions.items():
        ag = state.agents[aid]
        if not (act.do_kill and ag.alive and ag.role == "Infected" and ag.kill_cooldown == 0):
            continue
        for bid, bg in state.agents.items():
            if bid == aid or not bg.alive:
                continue
            dist = hypot(bg.position[0] - ag.position[0], bg.position[1] - ag.position[1])
            if dist <= settings.KILL_RADIUS:
                kill_events.append((aid, bid))
                ag.kill_cooldown = settings.KILL_DELAY_TICKS
                break

    for killer, victim in kill_events:
        vk = state.agents[victim]
        vk.alive = False
        corpse_pos: tuple[int, int] = (vk.position[0], vk.position[1])
        state.corpses.append(corpse_pos)
        delta.infections[victim] = True

        sound_pos = vk.position
        for aid2, other in state.agents.items():
            if not other.alive or aid2 == killer:
                continue
            d = hypot(other.position[0] - sound_pos[0], other.position[1] - sound_pos[1])
            if d <= settings.SOUND_RADIUS:
                seen_killer = any(
                    hypot(o.position[0] - other.position[0], o.position[1] - other.position[1]) <= settings.FOV_DISTANCE
                    and o.id == killer
                    for o in state.agents.values() if o.alive
                )
                if not seen_killer:
                    new_trust = max(0.0, other.trust.get(killer, 1.0) - settings.SOUND_TRUST_PENALTY)
                    other.trust[killer] = new_trust
                    delta.trust[f"{aid2}->{killer}"] = new_trust

                    other.panic = True
                    other.panic_ticks = settings.PANIC_DURATION
                    delta.chat.append({
                        "from": aid2,
                        "system": "heard_gunshot",
                        "suspect": None,
                        "tick": state.tick
                    })

def process_votes(state: GameState, actions: dict[str, Action], delta: Delta) -> None:
    vs = state.vote_session

    if vs is None:
        for aid, act in actions.items():
            ag = state.agents[aid]
            if act.do_vote and ag.alive and ag.vote_cooldown == 0:
                visible = [vid for vid, v in state.agents.items() if v.alive and vid != aid]
                idx = act.suspect_idx
                if 0 <= idx < len(visible):
                    state.vote_session = VoteSession(
                        suspect_id=visible[idx],
                        votes={},
                        timer=settings.VOTE_DURATION_TICKS
                    )
                    ag.vote_cooldown = settings.VOTE_DURATION_TICKS
                    delta.chat.append({
                        "system": "vote_started",
                        "suspect": visible[idx],
                        "initiator": aid,
                        "tick": state.tick
                    })
                    break

    if state.vote_session:
        vs = state.vote_session
        vs.timer -= 1
        vs.votes = {
            aid: (state.agents[aid].trust.get(vs.suspect_id, 0.0) < 0.5)
            for aid, ag in state.agents.items() if ag.alive
        }

        for aid in vs.votes:
            ag = state.agents[aid]
            if ag.chat_cooldown == 0:
                msg = LLMService.generate(ag, [state.agents[vs.suspect_id]], state)
                state.chat_log.append(msg)
                delta.chat.append(msg)
                ag.chat_cooldown = settings.VOTE_DURATION_TICKS // 2

        if vs.timer <= 0:
            yes = sum(vs.votes.values())
            no = len(vs.votes) - yes
            result = "passed" if yes > no else "failed"
            delta.chat.append({
                "system": "vote_result",
                "suspect": vs.suspect_id,
                "yes": yes,
                "no": no,
                "result": result,
                "tick": state.tick
            })
            if yes > no:
                state.agents[vs.suspect_id].alive = False
                delta.infections[vs.suspect_id] = False

            for aid in vs.votes:
                other = state.agents[aid]
                other.panic = False
                other.panic_ticks = 0

                other.trust[vs.suspect_id] = 0.0
                delta.trust[f"{aid}->{vs.suspect_id}"] = 0.0

            state.vote_session = None

def process_gossip(state: GameState, delta: Delta) -> None:
    new_actions: dict[str, Action] = {}
    for entry in list(delta.chat):
        if entry.get("system") == "vote_started":
            source = entry["initiator"]
            suspect = entry["suspect"]
            for aid, ag in state.agents.items():
                if not ag.alive or aid == source:
                    continue
                trust = ag.trust.get(source, 0.0)
                if trust >= settings.GOSSIP_TRUST_THRESHOLD and random.random() < settings.GOSSIP_PROB:

                    new_actions[aid] = Action(do_chat=True)
                    delta.chat.append({
                        "from": aid,
                        "system": "gossip",
                        "heard_from": source,
                        "suspect": suspect,
                        "tick": state.tick
                    })
    if new_actions:
        state.pending_external = {**new_actions, **getattr(state, "pending_external", {})}


def check_evac_open(state: GameState, delta: Delta) -> None:
    if state.evac_open:
        return
    all_ids = [aid for aid, a in state.agents.items() if a.role == "Infected"]
    identified = []
    for aid in all_ids:
        a = state.agents[aid]
        if not a.alive or any(other.known_target == aid for other in state.agents.values()):
            identified.append(aid)
    if set(identified) == set(all_ids):
        state.evac_open = True
        delta.chat.append({"system": "evac_open"})

def process_chat(state: GameState, actions: Dict[str, Action], delta: Delta) -> None:
    for aid, act in actions.items():
        ag = state.agents[aid]
        if not (act.do_chat and ag.alive and ag.chat_cooldown == 0):
            continue
        prompt_state = state

        visible = [
            v for v in state.agents.values()
            if v.alive and v.id != aid
            and hypot(v.position[0]-ag.position[0], v.position[1]-ag.position[1]) <= settings.FOV_DISTANCE
            and has_line_of_sight(ag.position, v.position, state.rooms)
        ]

        msg = LLMService.generate(agent=ag, visible_agents=visible, state=prompt_state)
        state.chat_log.append(msg)
        delta.chat.append(msg)
        ag.chat_cooldown = max(1, int((1 - min(ag.trust.values())) * settings.VOTE_DURATION_TICKS))


def process_group_chat(state: GameState, delta: Delta) -> None:
    if state.group_chat is None:
        for aid, ag in state.agents.items():
            if not ag.alive:
                continue
            members = {
                bid for bid, bg in state.agents.items()
                if bg.alive and bid != aid
                and hypot(bg.position[0] - ag.position[0],
                          bg.position[1] - ag.position[1]) <= settings.GROUP_CHAT_RADIUS
            } | {aid}
            if len(members) >= settings.GROUP_CHAT_MIN:
                state.group_chat = GroupChatSession(
                    members=members,
                    timer=settings.GROUP_CHAT_DURATION_TICKS
                )
                delta.chat.append({
                    "system": "group_chat_started",
                    "members": list(members),
                    "tick": state.tick
                })
                break

    gc = state.group_chat
    if gc:
        gc.timer -= 1
        for aid in gc.members:
            ag = state.agents[aid]
            if not ag.alive or ag.chat_cooldown > 0:
                continue

            others = [state.agents[bid] for bid in gc.members if bid != aid]
            msg = LLMService.generate(ag, others, state)
            state.chat_log.append(msg)
            delta.chat.append(msg)
            ag.chat_cooldown = settings.GROUP_CHAT_COOLDOWN
        if gc.timer <= 0:
            delta.chat.append({
                "system": "group_chat_ended",
                "members": list(gc.members),
                "tick": state.tick
            })
            state.group_chat = None

def process_thoughts(state: GameState, actions: Dict[str, Action], delta: Delta) -> None:
    for aid, act in actions.items():
        ag = state.agents[aid]
        if act.do_think and ag.alive and ag.chat_cooldown==0:
            visible=[v for v in state.agents.values()
                     if v.alive and v.id!=aid and hypot(v.position[0]-ag.position[0],
                                                         v.position[1]-ag.position[1])<=settings.FOV_DISTANCE]
            thought=LLMService.generate_thought(ag,visible,state)
            entry={"from":aid,"thought":thought,"tick":state.tick}
            state.chat_log.append(entry); delta.chat.append(entry)
            ag.chat_cooldown = settings.VOTE_DURATION_TICKS//2


def apply_cooldowns_and_advance_tick(state: GameState) -> None:
    for ag in state.agents.values():
        ag.kill_cooldown = max(0, ag.kill_cooldown - 1)
        ag.vote_cooldown = max(0, ag.vote_cooldown - 1)
        ag.chat_cooldown = max(0, ag.chat_cooldown - 1)

        if getattr(ag, "panic", False):
            ag.panic_ticks = max(0, ag.panic_ticks - 1)
            if ag.panic_ticks == 0:
                ag.panic = False
    state.tick += 1


def check_win_conditions(state: GameState, delta: Delta) -> None:
    if state.evac_open:
        survivors_inside = sum(
            1
            for a in state.agents.values()
            if a.alive
               and a.role == "Survivor"
               and point_in_polygon(a.position, state.evac_zone.polygon)
        )
        if survivors_inside >= 2:
            delta.chat.append({"system": "survivors_win"})
            return

    alive_count = sum(1 for a in state.agents.values() if a.alive)
    if alive_count <= 1:
        delta.chat.append({"system": "infected_win"})
