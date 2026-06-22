"""
schemas.py
----------
Pydantic request and response models for all Lodestone API endpoints.

WHY PYDANTIC SCHEMAS ARE SEPARATE FROM SQLALCHEMY MODELS:
    SQLAlchemy models define how data is STORED (table columns, relationships).
    Pydantic schemas define how data is TRANSFERRED (what JSON the API accepts
    and returns). They overlap in field names but serve different masters.

    Example of why they diverge:
    - The DB Session row has state_json (a big blob), created_at, updated_at.
    - The API response for /session/start has session_id and ai_message.
    - You never want to expose state_json or timestamps to the client.

HOW FASTAPI USES THESE:
    @router.post("/start", response_model=SessionStartResponse)
    def start(body: SessionStartRequest, ...):
        ...

    FastAPI automatically:
      1. Parses and validates the incoming JSON into SessionStartRequest.
         Returns HTTP 422 Unprocessable Entity if validation fails.
      2. Serializes the returned object using SessionStartResponse.
         Strips any extra fields not in the schema.

    This means your route handler never manually calls json.loads() or
    json.dumps() — FastAPI handles all that.
"""

from typing import Optional
from pydantic import BaseModel


# ── /session/start ─────────────────────────────────────────────────────────────

class SessionStartRequest(BaseModel):
    """
    Body for POST /session/start.

    student_id:   Identifies who is doing the session (e.g. "nakul_42").
                  Not authenticated in this build — just a string label.
    problem_id:   Which assignment this session is for (e.g. "prob_001").
    problem_text: The full assignment description shown to the student.
    """
    student_id: str
    problem_id: str
    problem_text: str


class SessionStartResponse(BaseModel):
    """
    Response for POST /session/start.

    session_id:  UUID string the client must include in all subsequent calls.
    phase:       Always "spec_gate" at session start.
    ai_message:  The first Socratic question from the spec_gate node (optional).
    """
    session_id: str
    phase: str
    ai_message: Optional[str] = None


# ── /session/{id}/spec ─────────────────────────────────────────────────────────

class SpecStepRequest(BaseModel):
    """
    Body for POST /session/{session_id}/spec.

    student_input: The student's latest reply in the spec conversation.
                   This becomes both the new student_spec AND the next
                   message appended to spec_history.
    """
    student_input: str


class SpecStepResponse(BaseModel):
    """
    Response for POST /session/{session_id}/spec.

    ready:           True if the spec has been approved.
    ai_message:      The AI's next question, or null if ready=True.
    editor_unlocked: True when ready — signals the frontend to show the code editor.
    """
    ready: bool
    ai_message: Optional[str]
    editor_unlocked: bool


# ── /session/{id}/code/run ─────────────────────────────────────────────────────
# (Defined now so schemas.py is complete — implemented in CP6)

class CodeRunRequest(BaseModel):
    """Body for POST /session/{session_id}/code/run."""
    code: str
    language: str


class CodeRunResponse(BaseModel):
    """Response for POST /session/{session_id}/code/run."""
    stdout: str
    stderr: str
    exit_code: int
    ai_message: Optional[str]   # Only present if exit_code != 0 (debug hint)


# ── /session/{id}/code/chat ────────────────────────────────────────────────────
# (Implemented in CP7)

class CodeChatRequest(BaseModel):
    """Body for POST /session/{session_id}/code/chat."""
    student_message: str


class CodeChatResponse(BaseModel):
    """Response for POST /session/{session_id}/code/chat."""
    type: str           # "reference" or "reasoning"
    ai_message: str


# ── /session/{id}/submit ───────────────────────────────────────────────────────
# (Implemented in CP8)

class SubmitRequest(BaseModel):
    """Body for POST /session/{session_id}/submit."""
    final_code: str


class SubmitResponse(BaseModel):
    """Response for POST /session/{session_id}/submit."""
    match: bool
    mismatch_note: Optional[str]
    reflection: str
    sks_update: dict
