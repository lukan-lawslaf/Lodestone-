"""
routes/session.py
-----------------
FastAPI route handlers for all session-related endpoints.

WHAT IS AN APIROUTER?
    APIRouter is FastAPI's way of grouping related routes. Think of it like
    a mini-app. We create one here and mount it in main.py with a prefix.
    This keeps main.py clean and allows routes to be organized by feature.

    In main.py:
        from routes.session import router as session_router
        app.include_router(session_router, prefix="/session", tags=["session"])

    Result: all routes defined here get the "/session" prefix automatically.
    So @router.post("/start") becomes POST /session/start.

STATE PERSISTENCE PATTERN:
    Because the LangGraph pipeline has natural pause points (waiting for the
    student to type something), we cannot keep state in memory. Each request:

      LOAD:  session_id -> DB row -> state_json -> deserialize -> LodestoneState dict
      WORK:  run the appropriate node(s)
      SAVE:  LodestoneState dict -> serialize -> state_json -> DB row update

    This is the "manual checkpointing" approach from the spec. Simple and
    reliable — the entire state survives server restarts, crashes, or scaling.

ERROR HANDLING STRATEGY:
    We raise HTTPException with appropriate status codes:
    - 404: session not found (client sent a bad/expired session_id)
    - 422: Pydantic handles malformed request bodies automatically
    - 500: unexpected server errors (let them propagate as 500 for now)
"""

import uuid
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from db import get_db
from models import Session as SessionModel
from schemas import (
    SessionStartRequest, SessionStartResponse,
    SpecStepRequest, SpecStepResponse,
    CodeRunRequest, CodeRunResponse,
)
from graph.state import make_initial_state, serialize_state, deserialize_state
from graph.nodes import spec_gate, compiler_run, hint_generator


# Create the router. All routes defined below will be mounted under /session
# by main.py.
router = APIRouter()


# ── Helper: load session from DB ───────────────────────────────────────────────

def _get_session_or_404(session_id: str, db: DBSession) -> SessionModel:
    """
    Load a Session row from the database.

    Raises HTTP 404 if no row matches the given session_id.
    We use this helper in every route that takes a {session_id} path param
    to keep error handling consistent and DRY.

    Args:
        session_id: UUID string from the URL path.
        db:         SQLAlchemy session injected by FastAPI's Depends(get_db).

    Returns:
        The SessionModel ORM row.
    """
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    return row


# ── POST /session/start ────────────────────────────────────────────────────────

@router.post("/start", response_model=SessionStartResponse)
def start_session(body: SessionStartRequest, db: DBSession = Depends(get_db)):
    """
    Create a new learning session and run the first spec_gate turn.

    FLOW:
    1. Generate a new UUID for this session.
    2. Build a fresh LodestoneState with the problem text.
    3. Run spec_gate once with an empty spec → get the AI's first question.
    4. Persist the updated state to the DB.
    5. Return session_id + the AI's first question.

    WHY run spec_gate immediately?
    The UI needs the AI's first question to display to the student before
    they type anything. We can't just create the session and wait — the
    spec_gate prompt needs a problem statement to generate a useful opening
    question (not just "what's your spec?").
    """
    # Step 1: Generate a unique session identifier.
    # uuid4() generates a random UUID. str() converts it to the standard
    # "xxxxxxxx-xxxx-4xxx-..." hyphenated string format.
    session_id = str(uuid.uuid4())

    # Step 2: Build a fresh LodestoneState with safe defaults.
    state = make_initial_state(
        session_id=session_id,
        problem=body.problem_text,
    )

    # Step 3: Run spec_gate to get the first question.
    # spec_gate reads state["problem"] and state["student_spec"] (empty at this point).
    # It returns a partial dict — we merge it into state immediately.
    update = spec_gate(state)
    state.update(update)

    # Extract the AI's first question from the conversation history.
    # spec_history[-1] is the assistant turn just added by spec_gate.
    # We parse the JSON string back to get the "question" field.
    last_assistant = json.loads(state["spec_history"][-1]["content"])
    ai_message = last_assistant.get("question") or "What is your plan for solving this problem?"

    # Step 4: Persist the session to the database.
    # We create a new SessionModel row and add it to the DB session.
    row = SessionModel(
        id=session_id,
        student_id=body.student_id,
        problem_id=body.problem_id,
        state_json=serialize_state(state),  # full LodestoneState as JSON string
        phase=state["phase"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()

    # Step 5: Return the response.
    # FastAPI validates this dict against SessionStartResponse automatically.
    return SessionStartResponse(
        session_id=session_id,
        phase=state["phase"],
        ai_message=ai_message,
    )


# ── POST /session/{session_id}/spec ───────────────────────────────────────────

@router.post("/{session_id}/spec", response_model=SpecStepResponse)
def spec_step(
    session_id: str,
    body: SpecStepRequest,
    db: DBSession = Depends(get_db),
):
    """
    Process one student reply in the spec clarification loop.

    FLOW:
    1. Load the session state from the DB.
    2. Append the student's input to spec_history as a user message.
    3. Update student_spec with the full latest text.
    4. ROUTE GUARD: if spec is already ready, return immediately.
    5. Run spec_gate again → get next question (or final approval).
    6. Persist updated state to DB.
    7. Return the AI's response + whether the editor is unlocked.

    WHY UPDATE student_spec with the full input?
    The spec_gate prompt shows student_spec as the "current specification".
    Students often rewrite their whole spec rather than just answering the
    question — that's fine and expected. We overwrite student_spec each time.
    The full conversation history is preserved separately in spec_history.
    """
    # Step 1: Load session from DB (raises 404 if not found).
    row = _get_session_or_404(session_id, db)
    state = deserialize_state(row.state_json)

    # Step 2 & 3: Update the state with the student's latest input.
    # The student's input IS their new/updated spec text.
    state["student_spec"] = body.student_input

    # Step 4: ROUTE GUARD — if already approved, don't re-run spec_gate.
    # This is the guard that prevents calling spec_gate on an already-ready spec.
    # Without this, re-submitting the same spec would be non-deterministic.
    if state["spec_ready"]:
        return SpecStepResponse(
            ready=True,
            ai_message=None,
            editor_unlocked=True,
        )

    # Step 5: Run spec_gate to evaluate the current spec.
    update = spec_gate(state)
    state.update(update)

    # Extract the AI's message (question if not ready, None if ready).
    last_assistant = json.loads(state["spec_history"][-1]["content"])
    ready: bool = last_assistant.get("ready", False)
    question: str | None = last_assistant.get("question")

    # Build the human-readable message returned to the client.
    # If ready, ai_message is None — the frontend unlocks the editor instead.
    ai_message = question if not ready else None

    # Step 6: Persist updated state.
    row.state_json = serialize_state(state)
    row.phase = state["phase"]
    row.updated_at = datetime.utcnow()
    db.commit()

    # Step 7: Return response.
    return SpecStepResponse(
        ready=ready,
        ai_message=ai_message,
        editor_unlocked=ready,
    )


# ── POST /session/{session_id}/code/run ───────────────────────────────────────

@router.post("/{session_id}/code/run", response_model=CodeRunResponse)
def code_run(
    session_id: str,
    body: CodeRunRequest,
    db: DBSession = Depends(get_db),
):
    """
    Execute the student's code and return the output. If the code fails,
    also run hint_generator to return a Socratic debug hint.

    FLOW:
    1. Load session state from DB.
    2. Write code + language onto state (student may have edited since last run).
    3. Run compiler_run node -> sets compiler_stdout/stderr/exit_code, increments attempt_num.
    4. If exit_code != 0:
         a. Escalate hint_level (cap at 5) if same-error retry, else keep at current.
            For simplicity in CP6 we always increment up to 5.
         b. Run hint_generator -> appends hint to chat_history.
         c. Include hint as ai_message in the response.
    5. Persist updated state to DB.
    6. Return stdout/stderr/exit_code + optional ai_message.

    HINT LEVEL ESCALATION:
        hint_level starts at 1. Each time the student clicks Run and the code
        still fails (any error), hint_level increments by 1 (capped at 5).
        A more sophisticated impl would reset hint_level when the ERROR TYPE
        changes - for CP6 we use simple increment-on-failure.
    """
    # Step 1: Load session.
    row = _get_session_or_404(session_id, db)
    state = deserialize_state(row.state_json)

    # Step 2: Write the submitted code + language onto state.
    # The student may have edited code since the last run - always use
    # the freshly submitted version, not whatever was stored.
    state["code"] = body.code
    state["language"] = body.language

    # Step 3: Run compiler_run.
    # This calls Piston, stores results, and increments attempt_num.
    run_update = compiler_run(state)
    state.update(run_update)

    ai_message = None

    # Step 4: If the code failed, generate a Socratic debug hint.
    if state["compiler_exit_code"] != 0:
        # Escalate hint_level (1 -> 2 -> ... -> 5) on each failed attempt.
        # We cap at 5 since level 5 is already near-explicit.
        current_hint_level = state.get("hint_level", 1)
        state["hint_level"] = min(current_hint_level + 1, 5)

        # Run hint_generator with the updated state (which now has stderr).
        hint_update = hint_generator(state)
        state.update(hint_update)

        # The hint is the last message appended to chat_history.
        if state["chat_history"]:
            ai_message = state["chat_history"][-1]["content"]

    # Step 5: Persist to DB.
    row.state_json = serialize_state(state)
    row.phase = state["phase"]
    row.updated_at = datetime.utcnow()
    db.commit()

    # Step 6: Return response.
    return CodeRunResponse(
        stdout=state["compiler_stdout"],
        stderr=state["compiler_stderr"],
        exit_code=state["compiler_exit_code"],
        ai_message=ai_message,
    )
