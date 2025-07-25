````markdown
# Last Safe Zone (LSZ) Backend

This repository implements the **deterministic** (rule-based) backend for a social-deduction LSZ game. Its responsibilities are:

1. **Serving 3D map assets** (`.glb`) and room geometry.
2. **Simulating** agent behaviour each tick according to a fixed set of mechanics.
3. **Exposing** HTTP and WebSocket endpoints for front-end integration.

---

## Table of Contents

- [Project Structure](#project-structure)  
- [Configuration](#configuration)  
- [API Endpoints](#api-endpoints)  
- [Game Loop & Modules](#game-loop--modules)  
- [Agent Roles & State](#agent-roles--state)  
- [Core Mechanics](#core-mechanics)  
  - [Movement](#movement)  
  - [Kills & Sound](#kills--sound)  
  - [Voting](#voting)  
  - [Panic](#panic)  
  - [Group Chat](#group-chat)  
  - [Gossip](#gossip)  
  - [Evacuation Zone](#evacuation-zone)  
  - [Win Conditions](#win-conditions)  
- [Deterministic Mode Workflow](#deterministic-mode-workflow)  

---

## Project Structure

```text
app/
├── main.py                   # entrypoint, FastAPI app + auto-ticker
├── config/
│   ├── settings.py           # pydantic settings (dirs, timeouts, constants)
│   └── models.py             # Pydantic schemas for request/response
├── routers/
│   ├── init.py               # POST /init
│   ├── step.py               # POST /step (manual)
│   ├── state.py              # GET /state
│   └── web_socket.py         # WS /ws streaming deltas
├── services/
│   ├── llm/
│   │   ├── llm_service.py    # batched prompt builder + Ollama client
│   │   └── roles.json          # JSON templates for roles
│   ├── manager/
│   │   ├── manager.py        # GameManager entrypoint (init, step)
│   │   ├── state.py          # GameState, AgentState, VoteSession, GroupChatSession
│   │   └── mechanics.py      # all rule-based tick functions
│   └── utils/
│       └── geometry.py       # point-in-polygon, LOS, room membership
└── data/
    ├── json/
    └── models/
````

---

## Configuration

All constants and directories live in `app/config/settings.py`. Key parameters include:

* **MAPS\_DIR**, **MODELS\_DIR**, **JSON\_DIR**
* **MODE**: `"deterministic"` or `"rl"`
* **TICK\_DURATION**: seconds between automatic ticks
* **LLM\_CACHE\_TTL**, **LLM\_MODEL**, **LLM\_MAX\_TOKENS**
* Game mechanics thresholds: `KILL_RADIUS`, `SOUND_RADIUS`, `VOTE_DURATION_SECS`, `PANIC_DURATION`, `GROUP_CHAT_*`, `GOSSIP_PROB` / `GOSSIP_TRUST_THRESHOLD`, etc.

---

## API Endpoints

### POST `/init`

**Request**: optional `map_id`
**Response**:

```json
{
  "tick": 0,
  "map_asset": "/static/maps/level1.glb",
  "rooms": [ { "id":"room_1","polygon":[…], "center":[x,y] }, … ],
  "agents": [ { "id":"agent_0","role":"Survivor",… }, … ]
}
```

### POST `/step`

Advance one tick **on demand** (deterministic or RL mode):

* **Body**: `{ external_actions: { "agent_3": { move:1, do_chat:true }, … } }`
* **Response**: `{ tick: 42, delta: { positions:{…}, infections:{…}, trust:{…}, chat:[…] } }`

### GET `/state`

Return full snapshot:

```json
{ "tick":42, "map_size":[W,H], "tiles":[…], "agents":{…}, "chat_log":[…] }
```

### WebSocket `/ws`

* On connect: sends full state.
* If `ENABLE_AUTO_TICK` is `true`, server auto-ticks every `TICK_DURATION`, broadcasts `{ tick, delta }`.
* Clients may send `{"external_actions": …}` to interleave manual steps.

---

## Game Loop & Modules

The two-stage game loop lives in `GameManager.step_deterministic`:

1. **collect\_actions**: merge external overrides with rule-based decisions.
2. **process\_movements**
3. **process\_kills**
4. **process\_votes**
5. **check\_evac\_open**
6. **process\_chat\_and\_thoughts** (batched LLM calls)
7. **process\_group\_chat**
8. **process\_gossip**
9. **apply\_cooldowns\_and\_advance\_tick**
10. **check\_win\_conditions**

Each function mutates `GameState` and records diffs in `Delta`.

---

## Agent Roles & State

* **Survivor**: goal → identify and reach evacuation.
* **Infected**: goal → eliminate survivors undetected.
* **Knower** (modifier): one random agent knows another’s true role.

AgentState fields (partial):

```python
id: str
role: "Survivor" | "Infected"
is_knower: bool
known_target: Optional[str]
position: [x,y]
heading: float
kill_cooldown, vote_cooldown, chat_cooldown: int ticks
trust: Dict[agent_id, float]  # 0.0–1.0
# rule-based extras:
target: Optional[[x,y]]
panic: bool
panic_ticks: int
```

---

## Core Mechanics

### Movement

* Agents choose `move ∈ {0: stay,1:up,2:right,3:down,4:left}`.
* New position must lie within some room polygon.

### Kills & Sound

* **Infected** with `kill_cooldown=0` can kill if target within `KILL_RADIUS` and FOV.
* Upon kill:

  * Victim marked dead, corpse added to `state.corpses`.
  * Killer’s cooldown set.
  * **Sound event**: any alive agent within `SOUND_RADIUS` who **didn’t see** the killer:

    * Loses `SOUND_TRUST_PENALTY` trust towards killer.
    * Enters `panic = True` for `PANIC_DURATION` ticks.
    * Emits system chat `{"system":"heard_gunshot"}`.

### Voting

* Any agent may `do_vote` when `vote_cooldown=0`.
* Initiates `VoteSession(suspect_id, timer=VOTE_DURATION_TICKS)`.
* Each tick: alive agents auto-vote by trust <0.5.
* LLM-driven chat discussion batched within vote ticks.
* On resolution:

  * If passed, suspect dies; panic cleared; trust resets.
  * Emits `vote_result` system chat.

### Panic

* Agents in `panic`:

  * Altered movement (random escape steps).
  * Higher chat inclination (`do_chat = True`).
  * Extended `chat_cooldown`.

### Group Chat

* When ≥`GROUP_CHAT_MIN` agents cluster within `GROUP_CHAT_RADIUS`, start `GroupChatSession(members, timer)`.
* Batched LLM chat among members each tick until timer expires.
* Emits `group_chat_started` / `group_chat_ended`.

### Gossip

* On `vote_started`, agents with `trust ≥ GOSSIP_TRUST_THRESHOLD` may, with probability `GOSSIP_PROB`, echo the suspicion in chat.
* Echoing enqueues a new `do_chat` action in `state.pending_external`.

### Evacuation Zone

* A random room chosen at init, locked until **all infected** are either dead or publicly identified.
* On unlock, emits `evac_open`. Survivors can enter.

### Win Conditions

* **Survivors win**: ≥2 alive survivors inside evacuation polygon.
* **Infected win**: only one agent remains alive (infected or mistaken survivor).

---

## Deterministic Mode Workflow

1. **Initialization** (`POST /init`): load map, rooms, place agents, assign roles.
2. **Auto-ticker** (if enabled): every `TICK_DURATION` seconds:

   * `step_deterministic()` → update state + compute `Delta` → broadcast via WS.
3. **External Actions**: front-end may override per-agent actions via WS or `POST /step`.
4. **Front-end** consumes deltas to animate movement, display chat, trust updates, corpses, voting UI.

This backend delivers a **self-contained social simulation**: even before any RL agent is attached, observers will see emergent group dynamics, panic reactions, structured discussions, and strategic bluffing powered by batched LLM calls.


To test a backend side run:

```bash
python -m hypercorn --reload app.main:app
```