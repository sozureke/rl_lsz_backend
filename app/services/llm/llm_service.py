import json
import threading
from typing import List
from cachetools import TTLCache, cached
import ollama
from pathlib import Path
from app.config.settings import settings
from app.services.manager.state import AgentState, GameState


class LLMService:
    _lock = threading.Lock()
    _cache: TTLCache
    _prompts: dict

    @classmethod
    def initialize(cls):
        cls._cache = TTLCache(maxsize=1000, ttl=settings.LLM_CACHE_TTL)

        path = Path(__file__).parent / "roles.json"
        with path.open(encoding="utf-8") as f:
            cls._prompts = json.load(f)

    @classmethod
    def _build_prompt(cls, agent: AgentState, visible: List[AgentState], state: GameState) -> str:
        role_data = cls._prompts["roles"].get(agent.role, {})
        system_parts = [role_data.get("system", "")]

        if agent.is_knower:
            mod = cls._prompts["modifiers"].get("Knower", {})
            system_parts.append(mod.get("system", ""))

        system = " ".join(p for p in system_parts if p)

        vis_ids = [v.id for v in visible]
        recent = state.chat_log[-5:]
        vs = state.vote_session
        vote_part = ""
        if vs and agent.alive and agent.id in vs.votes:
            vote_part = (
                f"A vote is in progress for suspect {vs.suspect_id}. "
                f"Time left: {vs.timer * settings.TICK_DURATION:.1f}s. "
                "Discuss your view."
            )

        return (
            f"SYSTEM: {system}\n"
            f"{vote_part}\n"
            f"You are agent {agent.id} ({agent.role}{', knower' if agent.is_knower else ''}).\n"
            f"Visible agents: {', '.join(vis_ids)}.\n"
            f"Known target: {agent.known_target}.\n"
            f"Trust levels: {agent.trust}.\n"
            f"Recent chat: {recent}.\n"
            "USER: Generate a brief in-character message."
        )


    @classmethod
    def generate_thought(cls, agent: AgentState, visible_agents: List[AgentState], state: GameState) -> str:
        prompt = (
            "SYSTEM: Think step-by-step, do not reveal hidden roles.\n"
            f"You are {agent.role} {agent.id}.\n"
            f"Visible: {', '.join(v.id for v in visible_agents)}\n"
            f"Known target: {agent.known_target}\n"
            f"Trust: {agent.trust}\n"
            f"Last 3 chat: {state.chat_log[-3:]}\n"
            "Thought:"
        )

    @classmethod
    def generate(cls, agent: AgentState, visible_agents: List[AgentState], state: GameState) -> dict:
        prompt = cls._build_prompt(agent, visible_agents, state)

        @cached(cls._cache)
        def _call_ollama(p: str) -> str:
            with cls._lock:
                resp = ollama.chat(
                    model=settings.LLM_MODEL,
                    messages=[{"role": "user", "content": p}],
                    options={"max_tokens": settings.LLM_MAX_TOKENS}
                )
                if "message" in resp:
                    return resp["message"]["content"]
                return resp["choices"][0]["message"]["content"]

        text = _call_ollama(prompt).strip()
        return {
            "from": agent.id,
            "text": text,
            "to": [v.id for v in visible_agents],
            "tick": state.tick
        }