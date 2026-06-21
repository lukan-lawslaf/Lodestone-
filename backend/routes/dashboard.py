"""
routes/dashboard.py
--------------------
GET /dashboard/{cohort_id} — teacher-facing cohort analytics endpoint.

Returns two things:
  1. live_states   — one entry per student currently in the cohort, showing
                     their current phase and a short human-readable status note.
  2. cohort_patterns — aggregated CohortEvent counts grouped by event_type,
                       with a sample detail string for the most recent event.

NO LLM CALLS in this route — status_note is generated from a simple template.
The spec allows a cheap Groq call for status_note but a template is faster,
cheaper, and more reliable for a dashboard that may be polled frequently.

HOW COHORT MEMBERSHIP WORKS:
    We use problem_id as the cohort_id proxy. All sessions for the same
    problem_id are considered part of the same cohort. This is the simplest
    approach for the hackathon — no explicit cohort table needed.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func

from db import get_db
from models import Session as SessionModel, CohortEvent
from graph.state import deserialize_state

router = APIRouter()


# ── Status note template ──────────────────────────────────────────────────────

_PHASE_NOTES = {
    "spec_gate":       "Refining their specification",
    "hint_generator":  "Stuck — receiving a Socratic hint",
    "compiler_run":    "Running their code",
    "code_classifier": "Asking a question",
    "code_chat":       "In a coding chat",
    "intent_diff":     "Submitting final code for review",
    "update_sks":      "Session being evaluated",
    "reflection":      "Session complete — reading reflection",
}

def _status_note(phase: str, state: dict) -> str:
    """
    Build a short human-readable status string from the current phase + state.
    Adds attempt count and hint level where relevant.
    """
    base = _PHASE_NOTES.get(phase, f"In phase: {phase}")

    if phase == "compiler_run":
        attempt = state.get("attempt_num", 0)
        return f"{base} (attempt {attempt})"

    if phase == "hint_generator":
        hint_level = state.get("hint_level", 1)
        return f"{base} (hint level {hint_level}/5)"

    return base


# ── GET /dashboard/{cohort_id} ────────────────────────────────────────────────

@router.get("/{cohort_id}")
def get_dashboard(cohort_id: str, db: DBSession = Depends(get_db)):
    """
    Return live student states and cohort-wide event patterns.

    LIVE STATES:
        Query all Session rows where problem_id == cohort_id.
        For each, deserialize state_json to extract hint_level and attempt_num
        for the status note. We only deserialize what we need — we don't pass
        the full state to the client.

    COHORT PATTERNS:
        Query CohortEvent rows where cohort_id == cohort_id.
        GROUP BY event_type to get counts.
        Include the most recent detail string as a sample.

    PERFORMANCE NOTE:
        For a hackathon, deserializing every session's state_json is fine.
        In production you'd add indexed columns for hint_level and attempt_num
        on the Session table to avoid deserializing blobs.
    """

    # ── Live states ────────────────────────────────────────────────────────────
    session_rows = (
        db.query(SessionModel)
        .filter(SessionModel.problem_id == cohort_id)
        .order_by(SessionModel.updated_at.desc())
        .all()
    )

    live_states = []
    for row in session_rows:
        try:
            state = deserialize_state(row.state_json)
        except Exception:
            state = {}

        live_states.append({
            "student_id":  row.student_id,
            "phase":       row.phase,
            "status_note": _status_note(row.phase, state),
        })

    # ── Cohort patterns ────────────────────────────────────────────────────────
    # Subquery: latest detail per event_type for this cohort.
    # SQLite doesn't support DISTINCT ON, so we do a correlated subquery approach
    # using a Python grouping after fetching all events.
    event_rows = (
        db.query(CohortEvent)
        .filter(CohortEvent.cohort_id == cohort_id)
        .order_by(CohortEvent.created_at.desc())
        .all()
    )

    # Group by event_type: count occurrences, capture most-recent detail sample.
    pattern_map: dict[str, dict] = {}
    for ev in event_rows:
        if ev.event_type not in pattern_map:
            pattern_map[ev.event_type] = {
                "event_type":    ev.event_type,
                "count":         0,
                "detail_sample": ev.detail or "",
            }
        pattern_map[ev.event_type]["count"] += 1

    cohort_patterns = sorted(
        pattern_map.values(),
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "cohort_id":       cohort_id,
        "live_states":     live_states,
        "cohort_patterns": cohort_patterns,
    }
