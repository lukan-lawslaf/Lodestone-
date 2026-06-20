"""
graph/state.py
--------------
Defines LodestoneState — the single shared data structure that flows
through every node in the LangGraph pipeline.

WHY A TYPEDDICT?
    LangGraph works with plain Python dicts internally. TypedDict lets us
    annotate each key with a type so our editor can autocomplete and warn
    us when we use the wrong field name. At runtime it behaves exactly like
    a regular dict — TypedDict is purely for documentation and tooling.

OWNERSHIP RULE:
    Each node owns a subset of fields — it reads only what it needs and
    writes only what it's responsible for. Never let node A overwrite a
    field that belongs to node B. This keeps the graph predictable and
    easy to debug.

SERIALIZATION:
    The entire state dict is serialized to JSON (json.dumps) and stored in
    the sessions.state_json DB column between API calls. When the next
    request arrives, json.loads() deserializes it back. All values must
    therefore be JSON-serializable (str, int, bool, list, dict, None).
"""

from typing import TypedDict, List, Dict, Optional
import json

class LodestoneState(TypedDict):
    # ── Session identity ──────────────────────────────────────────────────────
    session_id: str         # UUID string, generated once at session start

    # ── Problem context ───────────────────────────────────────────────────────
    problem: str            # The assignment text shown to the student

    # ── Spec phase fields (owned by: spec_gate, hint_generator) ──────────────
    student_spec: str       # The student's current written specification
    spec_history: List[Dict]  # Conversation: [{role, content}, ...] turns
                              # role is "user" (student) or "assistant" (AI)
    spec_ready: bool        # True once spec_gate approves the spec

    # ── Coding phase fields (owned by: code_classifier, hint_generator) ───────
    code: str               # Student's current code submission
    language: str           # "python", "java", "javascript", "cpp"
    chat_history: List[Dict]  # Code-phase chat turns [{role, content}, ...]

    # ── Compiler fields (owned by: compiler_run) ──────────────────────────────
    compiler_stdout: str    # Standard output from code execution
    compiler_stderr: str    # Standard error / exception trace
    compiler_exit_code: Optional[int]  # 0 = success, non-zero = failure, None = not run yet

    # ── Hint tracking (owned by: hint_generator) ──────────────────────────────
    hint_level: int         # 1-5, escalates when student is stuck on same issue
    attempt_num: int        # Increments each time student clicks Run

    # ── Submit phase fields (owned by: intent_diff) ───────────────────────────
    # match=True means code fulfills spec; False means mismatch was found.
    # mismatch_note is a neutral Socratic question surfacing the discrepancy.
    intent_diff_result: Optional[Dict]  # {"match": bool, "mismatch_note": str | None}

    # ── Student knowledge state (owned by: update_sks) ───────────────────────
    # Accumulated across sessions via exponential moving average.
    # Structure: {
    #     "topic_scores": {"recursion": 0.4, "arrays": 0.8},
    #     "mistake_patterns": ["forgets null checks", "off-by-one"],
    #     "avg_hint_level_needed": 2.3
    # }
    sks: Dict

    # ── Reflection (owned by: reflection node) ────────────────────────────────
    reflection_note: Optional[str]  # Closing prompt generated for the student

    # ── Telemetry (updated by every node) ─────────────────────────────────────
    phase: str  # The name of the current/last node — used by dashboard


def make_initial_state(
    session_id: str,
    problem: str,
    student_id: str = "",
) -> LodestoneState:
    """
    Create a fresh LodestoneState with safe default values.

    Called once when POST /session/start creates a new session.
    Every field must have a value — TypedDict does not support missing keys
    at runtime (even though they're Optional in the type hints).

    We use empty strings and empty lists rather than None where possible,
    because it makes downstream code simpler: no need to check
    'if state["spec_history"] is None' before appending to it.
    """
    return LodestoneState(
        session_id=session_id,
        problem=problem,
        student_spec="",
        spec_history=[],
        spec_ready=False,
        code="",
        language="python",
        chat_history=[],
        compiler_stdout="",
        compiler_stderr="",
        compiler_exit_code=None,
        hint_level=1,
        attempt_num=0,
        intent_diff_result=None,
        sks={
            "topic_scores": {},
            "mistake_patterns": [],
            "avg_hint_level_needed": 1.0,
        },
        reflection_note=None,
        phase="spec_gate",
    )

def serialize_state(state: LodestoneState) -> str:
    return json.dumps(state)


def deserialize_state(json_str: str) -> LodestoneState:
    return json.loads(json_str)