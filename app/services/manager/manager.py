from typing import Any, Dict, List
from app.config.models import Delta, Room
from .state import GameState
from .mechanics import (
    collect_actions, process_movements, process_kills,
    process_votes, check_evac_open, process_chat,
    apply_cooldowns_and_advance_tick, check_win_conditions, process_thoughts, process_group_chat, process_gossip
)
from .state import AgentState
import random

class GameManager:
    _state: GameState = None

    @classmethod
    def initialize(cls, map_asset: str, rooms: List[Room]) -> None:


        state = GameState()
        state.map_asset = map_asset
        state.rooms = rooms

        state.evac_zone = random.choice(rooms)
        state.evac_open = False

        ids = [f"agent_{i}" for i in range(8)]
        roles = ["Infected"]*2 + ["Survivor"]*6
        random.shuffle(roles)
        knower = random.choice(ids)
        for aid, role in zip(ids, roles):
            is_knower = (aid == knower)
            known = None
            if is_knower:
                known = random.choice([i for i in ids if i != aid])
            room = random.choice(rooms)
            pos = (room.center[0], room.center[1])
            trust = {o: 0.5 for o in ids if o != aid}
            state.agents[aid] = AgentState(
                id=aid,
                role=role,
                is_knower=is_knower,
                known_target=known,
                alive=True,
                position=pos,
                heading=0.0,
                kill_cooldown=0,
                vote_cooldown=0,
                chat_cooldown=0,
                target=None,
                shared=False,
                rally_point=None,
                trust=trust
            )

        cls._state = state

    @classmethod
    def get_state(cls) -> GameState:
        if cls._state is None:
            raise RuntimeError("Not initialized")
        return cls._state

    @classmethod
    def step_deterministic(cls, external_actions: Dict[str, Any]) -> Delta:
        state = cls.get_state()
        delta = Delta()

        actions = collect_actions(state, external_actions)
        process_movements(state, actions, delta)
        process_kills(state, actions, delta)
        process_votes(state, actions, delta)
        check_evac_open(state, delta)
        process_chat(state, actions, delta)
        process_group_chat(state, delta)
        process_gossip(state, delta)
        process_thoughts(state, actions, delta)
        apply_cooldowns_and_advance_tick(state)
        check_win_conditions(state, delta)

        return delta

    @classmethod
    def step_rl(cls, external_actions: Dict[str, Any]) -> Delta:
        # RLService.compute_actions
        return cls.step_deterministic(external_actions)
