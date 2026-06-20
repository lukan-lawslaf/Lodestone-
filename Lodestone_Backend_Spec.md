# Lodestone Backend — Build Specification

**Purpose of this document:** This is a complete implementation brief for the Lodestone backend. Build exactly what is specified below — file structure, state schema, node logic, API contracts, and prompts are all final decisions, not suggestions to redesign.

**Project:** Lodestone — AI-Powered Socratic Coding Education Platform
**Team:** WildestIdeas (Garv — lead, Rohin, Nakul)
**Hackathon:** Bharat Academix CodeQuest

---

## 1. Tech Stack (locked)

| Layer | Choice |
|---|---|
| Backend framework | FastAPI |
| Workflow orchestration | LangGraph (`StateGraph` only — no agents, no tool-calling, no ReAct) |
| LLM | Groq API, model `llama-3.3-70b-versatile` |
| Code execution | Piston API (public instance: `https://emkc.org/api/v2/piston`) |
| Database | SQLite (via SQLAlchemy ORM) |
| Env management | `python-dotenv` |

Python version: 3.11+. Use `pip install fastapi uvicorn langgraph langchain-groq groq sqlalchemy python-dotenv httpx pydantic`.

---

## 2. Folder Structure

```
backend/
  main.py                  # FastAPI app, mounts routes
  config.py                 # loads .env (GROQ_API_KEY), constants
  db.py                      # SQLAlchemy engine, session, table creation
  models.py                   # SQLAlchemy ORM models
  schemas.py                   # Pydantic request/response schemas

  graph/
    state.py                  # LodestoneState TypedDict
    nodes.py                    # all node functions
    edges.py                     # conditional routing functions
    graph.py                      # StateGraph wiring, compiled graph export

  services/
    groq_client.py             # wraps Groq chat completion calls
    piston_client.py             # wraps Piston code execution calls

  prompts/
    spec_prompts.py             # Spec Gate system prompts
    classifier_prompts.py        # reference vs reasoning classifier prompt
    hint_prompts.py               # Socratic hint generation prompts
    diff_prompts.py                 # Intent-Diff comparison prompt
    reflection_prompts.py            # reflection phase prompt

  routes/
    session.py                  # POST /session/start, /session/{id}/step
    dashboard.py                  # GET /dashboard/{cohort_id}

  requirements.txt
  .env.example
```

---

## 3. Shared State Schema

File: `graph/state.py`

```python
from typing import TypedDict, List, Dict, Optional

class LodestoneState(TypedDict):
    session_id: str
    problem: str                      # the assignment/problem statement
    student_spec: str                 # student's current spec text
    spec_history: List[Dict]          # list of {role, content} spec-phase chat turns
    spec_ready: bool                  # True once spec passes the gate

    code: str                         # student's current code
    language: str                     # e.g. "python", "java", "cpp"
    chat_history: List[Dict]          # Phase 2 coding chat turns

    compiler_stdout: str
    compiler_stderr: str
    compiler_exit_code: Optional[int]

    hint_level: int                   # 1-5, escalates per retry on same issue
    attempt_num: int                  # increments each Run click

    intent_diff_result: Optional[Dict]  # {"match": bool, "mismatch_note": str}

    sks: Dict                         # Student Knowledge State, see section 7

    reflection_note: Optional[str]
    phase: str                        # current node name, for dashboard telemetry
```

This dict is the single object passed through every LangGraph node. Each node reads only the fields it needs and writes only the fields it owns. Never mutate fields outside a node's responsibility.

---

## 4. Graph Nodes

File: `graph/nodes.py`. Each node is a plain function `def node_name(state: LodestoneState) -> LodestoneState`.

### 4.1 `spec_gate`
- Input: `state.student_spec`, `state.spec_history`, `state.problem`
- Calls `services/groq_client.py` with system prompt from `prompts/spec_prompts.py`
- The prompt instructs the model to: read the spec, identify ONE most important missing detail (edge case, constraint, ambiguity), and either (a) ask a single targeted clarifying question, or (b) if the spec is unambiguous and implementable, return a structured signal `{"ready": true}`.
- Model must respond in strict JSON: `{"ready": bool, "question": str | null}`
- Updates `state.spec_history` (append both user input and AI question), sets `state.spec_ready`
- This node is called in a loop — after each student reply, it re-invokes the same node until `spec_ready == True`.

### 4.2 `hint_generator` (used in both spec clarification loop and code debug loop)
- Input: current phase context (`spec_history` or `chat_history`), `state.hint_level`
- Generates a Socratic question, never a direct answer.
- `hint_level` escalates the specificity of the hint if the student is stuck across multiple attempts on the same issue (1 = abstract nudge, 5 = near-explicit pseudocode-level hint — but even level 5 never writes runnable code).
- Output: appends a hint message to the relevant history list.

### 4.3 `code_classifier`
- Input: latest student question in `state.chat_history` during the coding phase
- Calls Groq with prompt from `prompts/classifier_prompts.py`
- Classifies the question as `"reference"` (syntax/API lookup — answer directly) or `"reasoning"` (debugging/logic help — route to `hint_generator` instead)
- Output: `{"type": "reference" | "reasoning", "answer": str | null}` — `answer` populated only if type is `"reference"`.

### 4.4 `compiler_run`
- Input: `state.code`, `state.language`
- Calls `services/piston_client.py`
- Sets `state.compiler_stdout`, `state.compiler_stderr`, `state.compiler_exit_code`
- Increments `state.attempt_num`

### 4.5 `intent_diff`
- Input: `state.student_spec`, `state.code`, `state.compiler_stdout`, `state.compiler_stderr`
- Calls Groq with prompt from `prompts/diff_prompts.py`
- The model is given the full spec and the full final code plus compiler output, and asked to identify if the implementation fulfills every commitment made in the spec.
- Output strict JSON: `{"match": bool, "mismatch_note": str | null}` — if `match` is false, `mismatch_note` is a single neutral question in the style: "In your spec, you committed to X, but your code does Y. What happened?"
- Sets `state.intent_diff_result`

### 4.6 `update_sks`
- Input: `state.intent_diff_result`, `state.hint_level`, `state.attempt_num`, problem topic tags (if available)
- Updates `state.sks`, a dict structured as:
```python
{
  "topic_scores": {"recursion": 0.4, "arrays": 0.8, ...},  # 0-1 confidence
  "mistake_patterns": ["forgets null checks", "off-by-one in loops"],
  "avg_hint_level_needed": 2.3
}
```
- This is an additive update — merge new signal into existing scores using simple exponential moving average (`new = 0.7*old + 0.3*signal`), not overwrite.
- Persist to DB (see section 6) at the end of this node.

### 4.7 `reflection`
- Input: `state.intent_diff_result`, `state.sks`
- Calls Groq with prompt from `prompts/reflection_prompts.py` — generates one short closing reflection prompt for the student based on what they struggled with this session.
- Sets `state.reflection_note`

---

## 5. Graph Wiring (Edges)

File: `graph/edges.py` and `graph/graph.py`.

```text
START
  → spec_gate
      ├─ spec_ready == False → hint_generator → (wait for student reply, re-enter spec_gate)
      └─ spec_ready == True → [unlock code editor, exit graph here, wait for student code submission]

[on Run button] → compiler_run
  ├─ compiler_exit_code != 0 → hint_generator (debug mode) → (wait for student edit, re-enter compiler_run)
  └─ compiler_exit_code == 0 → [allow Submit]

[on Submit button] → intent_diff → update_sks → reflection → END
```

Note: this graph has natural pause points (waiting for student input). Each pause point is a separate API call from the frontend — the graph is NOT run start-to-end in one call. Each FastAPI endpoint invokes the graph for exactly one node-cycle, persists `LodestoneState` to DB between calls (serialize as JSON in the `sessions` table), and reloads it on the next call. Use LangGraph's checkpointing if straightforward, otherwise manually serialize/deserialize the state dict to/from the DB — manual approach is acceptable and simpler for hackathon scope.

`code_classifier` is invoked directly from the coding-phase chat endpoint, not as a graph node in the main pipeline — it's a simple routing function called per chat message during Phase 2, separate from the spec/compile/diff flow.

---

## 6. Database Schema

File: `models.py`, using SQLAlchemy.

```python
class Session(Base):
    id = Column(String, primary_key=True)         # uuid
    student_id = Column(String)
    problem_id = Column(String)
    state_json = Column(Text)                       # full LodestoneState serialized
    phase = Column(String)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class StudentSKS(Base):
    student_id = Column(String, primary_key=True)
    sks_json = Column(Text)                          # persisted SKS dict
    updated_at = Column(DateTime)

class CohortEvent(Base):
    id = Column(Integer, primary_key=True, autoincrement=True)
    cohort_id = Column(String)
    student_id = Column(String)
    session_id = Column(String)
    event_type = Column(String)        # "spec_miss", "compiler_error", "intent_mismatch"
    detail = Column(Text)
    created_at = Column(DateTime)
```

`CohortEvent` rows are written by `update_sks` and `intent_diff` nodes whenever something notable happens (a spec gap, a recurring compiler error type, a mismatch) — this feeds the dashboard's cohort analytics directly via simple `GROUP BY event_type` queries, no separate analytics pipeline needed.

---

## 7. API Contracts

File: `routes/session.py`. All request/response bodies defined in `schemas.py` using Pydantic.

### `POST /session/start`
Request: `{ "student_id": str, "problem_id": str, "problem_text": str }`
Response: `{ "session_id": str, "phase": "spec_gate", "ai_message": str }`
Creates a new `LodestoneState`, runs `spec_gate` once with empty spec, returns the AI's first question.

### `POST /session/{session_id}/spec`
Request: `{ "student_input": str }`
Response: `{ "ready": bool, "ai_message": str | null, "editor_unlocked": bool }`
Loads state, appends student input to `spec_history`, re-runs `spec_gate`. If `ready`, unlocks editor.

### `POST /session/{session_id}/code/chat`
Request: `{ "student_message": str }`
Response: `{ "type": "reference" | "reasoning", "ai_message": str }`
Runs `code_classifier`, routes to direct answer or `hint_generator`.

### `POST /session/{session_id}/code/run`
Request: `{ "code": str, "language": str }`
Response: `{ "stdout": str, "stderr": str, "exit_code": int, "ai_message": str | null }`
Runs `compiler_run`. If non-zero exit, also runs `hint_generator` in debug mode and includes `ai_message`.

### `POST /session/{session_id}/submit`
Request: `{ "final_code": str }`
Response: `{ "match": bool, "mismatch_note": str | null, "reflection": str, "sks_update": dict }`
Runs `intent_diff` → `update_sks` → `reflection` in sequence, returns combined result.

### `GET /dashboard/{cohort_id}`
Response:
```json
{
  "live_states": [{"student_id": str, "phase": str, "status_note": str}],
  "cohort_patterns": [{"event_type": str, "count": int, "detail_sample": str}]
}
```
`status_note` is a short human-readable string derived from the student's current phase and last hint topic (e.g. "Confused about case-sensitivity at spec stage") — generate this with a cheap Groq call or simple template, not a full reasoning chain.

---

## 8. Prompt Templates

All prompts must instruct the model to respond in **strict JSON only, no markdown fences, no preamble**. Wrap every Groq call in a JSON parse with a fallback retry (one re-ask with "respond in valid JSON only" if parsing fails).

### `prompts/spec_prompts.py`
```
System: You are a Socratic programming instructor running a specification review.
You will be given a problem statement and a student's specification of their intended solution.
Your job: find the single most important gap, ambiguity, or unhandled edge case in the spec.
If the spec is genuinely unambiguous and implementable as-is, mark ready=true.
Never write or suggest code. Never give the answer directly. Ask one question at a time.
Respond ONLY with JSON: {"ready": boolean, "question": string or null}
```

### `prompts/classifier_prompts.py`
```
System: Classify the following student question as either "reference" or "reasoning".
"reference" = asking for syntax, API names, language features, factual lookups.
"reasoning" = asking why their code is wrong, debugging help, logic explanation.
If "reference", also provide a direct, concise answer.
Respond ONLY with JSON: {"type": "reference" or "reasoning", "answer": string or null}
```

### `prompts/hint_prompts.py`
```
System: You are a Socratic tutor. The student is stuck. Never give the direct answer or write code.
Generate ONE guiding question appropriate to hint_level (1=abstract conceptual nudge, 5=near-explicit
but still requires the student to write the final logic themselves).
If compiler error context is provided, use the specific error and code location to make the question
concrete (e.g. reference the exact line or exception type) without stating the fix outright.
Respond ONLY with JSON: {"hint": string}
```

### `prompts/diff_prompts.py`
```
System: Compare the student's final code against their original specification and compiler output.
Determine if the implementation fulfills every commitment made in the spec.
If there is a mismatch, phrase it as a neutral question in this exact style:
"In your spec, you committed to X, but your code does Y. What happened?"
Do not editorialize. Do not say whether this is "wrong" — just surface the discrepancy.
Respond ONLY with JSON: {"match": boolean, "mismatch_note": string or null}
```

### `prompts/reflection_prompts.py`
```
System: Generate one short (1-2 sentence) reflective prompt for the student based on what they
struggled with this session (drawn from hint usage and any intent-diff mismatch). The goal is
to make them articulate a takeaway, not to summarize for them.
Respond ONLY with JSON: {"reflection": string}
```

---

## 9. External Service Wrappers

### `services/groq_client.py`
```python
from groq import Groq
import os, json

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def call_groq(system_prompt: str, messages: list[dict], temperature: float = 0.3) -> dict:
    """
    messages: list of {"role": "user"|"assistant", "content": str}
    Returns parsed JSON dict from model response. Retries once on parse failure.
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=full_messages,
        temperature=temperature,
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        retry_messages = full_messages + [{"role": "user", "content": "Respond in valid JSON only."}]
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=retry_messages,
            temperature=temperature,
        )
        return json.loads(response.choices[0].message.content)
```

### `services/piston_client.py`
```python
import httpx

PISTON_URL = "https://emkc.org/api/v2/piston"

LANGUAGE_VERSIONS = {
    "python": "3.10.0",
    "java": "15.0.2",
    "javascript": "18.15.0",
    "cpp": "10.2.0",
}

async def run_code(code: str, language: str) -> dict:
    payload = {
        "language": language,
        "version": LANGUAGE_VERSIONS.get(language, "3.10.0"),
        "files": [{"content": code}],
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{PISTON_URL}/execute", json=payload, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    run = data.get("run", {})
    return {
        "stdout": run.get("stdout", ""),
        "stderr": run.get("stderr", ""),
        "exit_code": run.get("code", -1),
    }
```

---

## 10. Build Order (checkpoints)

Build and manually test in this order — each checkpoint should be runnable and demoable before moving to the next.

1. `config.py`, `db.py`, `models.py` — DB boots, tables create cleanly.
2. `services/groq_client.py` — test standalone with a hardcoded prompt, confirm JSON parsing works.
3. `graph/state.py`, `prompts/spec_prompts.py`, `graph/nodes.py` (`spec_gate` only) — test in a script, no API yet.
4. `routes/session.py` — `/session/start` and `/session/{id}/spec` only. Demo-able: full spec-gate conversation loop via curl/Postman.
5. `services/piston_client.py` — test standalone with a hardcoded "hello world" snippet per language.
6. Add `compiler_run` node + `/session/{id}/code/run` endpoint. Demo-able: write code, run it, see output.
7. Add `code_classifier` node + `/session/{id}/code/chat` endpoint.
8. Add `intent_diff`, `update_sks`, `reflection` nodes + `/session/{id}/submit` endpoint. Demo-able: full pipeline start to finish.
9. `routes/dashboard.py` — cohort query endpoint last, lowest priority for live demo but easy once `CohortEvent` rows exist.

---

## 11. Environment Variables

`.env.example`:
```
GROQ_API_KEY=your_key_here
DATABASE_URL=sqlite:///./lodestone.db
```

---

## 12. Non-Goals (explicitly out of scope for this build)

Do not implement: user authentication, multi-language frontend localization, RAG/vector search, Docker-based code sandboxing, WebSocket live updates (poll-based dashboard refresh is sufficient), Whisper/voice input, any payment or production deployment configuration. These are post-hackathon roadmap items only.
