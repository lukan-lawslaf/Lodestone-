"""
graph/nodes.py
--------------
All LangGraph node functions for Lodestone.

A NODE is a plain Python function with this exact signature:
    def node_name(state: LodestoneState) -> dict

It receives the current state, does its work, and returns a PARTIAL dict
containing ONLY the fields it changed. LangGraph merges this partial dict
back into the full state automatically.

IMPORTANT — Return partial dicts, not the full state:
    BAD:  return {**state, "spec_ready": True}   # returns every field
    GOOD: return {"spec_ready": True, "phase": "spec_gate"}  # only changes

Returning the full state causes subtle bugs when two nodes both update the
same field — the last one wins and silently overwrites the first.

Nodes are added to this file checkpoint by checkpoint:
    CP3: spec_gate
    CP6: compiler_run, hint_generator
    CP7: code_classifier
    CP8: intent_diff, update_sks, reflection
"""

import json
import asyncio
from graph.state import LodestoneState
from services.groq_client import call_groq
from services.piston_client import run_code
from prompts.spec_prompts import SPEC_GATE_SYSTEM_PROMPT
from prompts.hint_prompts import HINT_SYSTEM_PROMPT
from prompts.classifier_prompts import CLASSIFIER_SYSTEM_PROMPT
from prompts.diff_prompts import DIFF_SYSTEM_PROMPT
from prompts.reflection_prompts import REFLECTION_SYSTEM_PROMPT



# ── spec_gate ──────────────────────────────────────────────────────────────────

def spec_gate(state: LodestoneState) -> dict:
    """
    Evaluates the student's current specification and either asks one
    clarifying question or marks the spec as ready.

    INPUTS read from state:
        state["problem"]       — the assignment text (context for the LLM)
        state["student_spec"]  — what the student has written so far
        state["spec_history"]  — conversation turns so far (for context)

    OUTPUTS written to state (returned as partial dict):
        spec_history   — conversation list with the new AI question appended
        spec_ready     — True if the spec passed, False if more questions needed
        phase          — updated to "spec_gate" for dashboard telemetry

    HOW THE CONVERSATION IS BUILT:
        We don't just send the latest spec to Groq — we send the entire
        conversation history. This lets the model see what it already asked
        and avoid repeating questions.

        The user message we construct looks like this:
            "Problem: <problem text>

            Student's current specification:
            <student_spec>

            Ask your next question or mark ready."

        This is the *last* user turn. All previous turns are in spec_history.

    LOOP BEHAVIOR:
        This node is called repeatedly by the API route on each student reply:
          1. Student submits spec text  → spec_gate runs → returns question
          2. Student answers question   → spec_gate runs again → returns next question
          3. ...until spec_ready == True → route unlocks the code editor
    """
    problem = state["problem"]
    student_spec = state["student_spec"]
    spec_history = list(state["spec_history"])  # copy — never mutate state in place

    # Compact user message — strips the verbose trailing instruction phrase.
    # The system prompt already tells the model what to do; repeating it wastes tokens.
    current_user_message = (
        f"Problem: {problem}\n\nSpec: {student_spec}"
    )

    # Cap history at last 4 turns (2 exchanges) — older context adds noise not value.
    # The student's full spec is always in the current message so nothing is lost.
    capped_history = spec_history[-4:] if len(spec_history) > 4 else spec_history
    messages = capped_history + [{"role": "user", "content": current_user_message}]

    # Call Groq. Expected response: {"ready": bool, "question": str | null}
    response = call_groq(
        system_prompt=SPEC_GATE_SYSTEM_PROMPT,
        messages=messages,
        temperature=0.3,
    )

    # ── Validate response shape ────────────────────────────────────────────────
    # The model should always return the correct shape (we instructed it to),
    # but we defensively validate rather than assume.
    ready: bool = bool(response.get("ready", False))
    question: str | None = response.get("question", None)

    # ── Update conversation history ────────────────────────────────────────────
    # We append both sides of this turn to spec_history:
    #   1. The user message (what we sent to Groq as the last user turn)
    #   2. The assistant message (Groq's raw JSON response, stored as string)
    # This builds the full conversation that gets serialized to the DB.
    spec_history.append({"role": "user", "content": current_user_message})
    spec_history.append({
        "role": "assistant",
        "content": json.dumps(response),  # store the parsed dict re-serialized
    })

    # Return ONLY the fields this node is responsible for changing.
    # LangGraph merges this partial dict into the full state.
    return {
        "spec_history": spec_history,
        "spec_ready": ready,
        "phase": "spec_gate",
    }

# ── compiler_run ───────────────────────────────────────────────────────────────

def compiler_run(state: LodestoneState) -> dict:
    """
    Execute the student's code via the Piston sandbox and store the results.

    INPUTS read from state:
        state["code"]     - the student's current code submission
        state["language"] - e.g. "python", "javascript", "java", "cpp", "c"

    OUTPUTS written to state (returned as partial dict):
        compiler_stdout    - everything the program printed to stdout
        compiler_stderr    - error messages, tracebacks, compile errors
        compiler_exit_code - 0 = success, non-zero = error, -1 = timeout/crash
        attempt_num        - incremented by 1 each time the student hits Run
        phase              - updated to "compiler_run" for dashboard telemetry

    WHY asyncio.run() HERE:
        run_code() is async (uses httpx.AsyncClient). Node functions are
        called from synchronous route handlers. asyncio.run() creates a
        temporary event loop and bridges sync -> async correctly here.
    """
    result = asyncio.run(
        run_code(
            code=state["code"],
            language=state["language"],
        )
    )

    return {
        "compiler_stdout":    result["stdout"],
        "compiler_stderr":    result["stderr"],
        "compiler_exit_code": result["exit_code"],
        "attempt_num":        state["attempt_num"] + 1,
        "phase":              "compiler_run",
    }


# ── hint_generator ─────────────────────────────────────────────────────────────

def hint_generator(state: LodestoneState) -> dict:
    """
    Generate one Socratic guiding question to help the student move forward.

    Used in two modes:
      DEBUG MODE (compiler_stderr present): references the specific error.
      SPEC MODE:  uses spec_history as context.

    hint_level (1-5) controls specificity - see HINT_SYSTEM_PROMPT.
    hint_level is READ here but INCREMENTED by the route handler.

    OUTPUTS written to state:
        chat_history - hint appended as an assistant turn
        phase        - updated to "hint_generator"
    """
    hint_level = state.get("hint_level", 1)
    phase = state.get("phase", "compiler_run")

    # Truncation helpers — keep context focused, limit token burn.
    _STDERR_MAX = 500   # chars of stderr/stdout to include
    _CODE_MAX   = 60    # lines of code to include

    def _trunc(s: str, n: int) -> str:
        return s[:n] + "..." if len(s) > n else s

    def _trunc_lines(s: str, n: int) -> str:
        lines = s.splitlines()
        return "\n".join(lines[:n]) + ("\n..." if len(lines) > n else "")

    if phase == "compiler_run" or state.get("compiler_stderr"):
        # DEBUG MODE — compact format, truncated outputs.
        code = _trunc_lines(state.get("code", ""), _CODE_MAX)
        stderr = _trunc(state.get("compiler_stderr", ""), _STDERR_MAX)
        stdout = _trunc(state.get("compiler_stdout", ""), _STDERR_MAX)
        exit_code = state.get("compiler_exit_code", -1)
        context_msg = (
            f"Code:\n{code}\n\n"
            f"exit={exit_code} stdout={stdout!r:.200} stderr={stderr}\n"
            f"hint_level={hint_level}/5"
        )
    else:
        # SPEC/CHAT MODE — last 2 turns of relevant history only.
        history_turns = (
            state.get("chat_history", [])[-4:]
            or state.get("spec_history", [])[-4:]
        )
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in history_turns
        )
        context_msg = f"{history_text}\nhint_level={hint_level}/5"

    messages = [{"role": "user", "content": context_msg}]
    response = call_groq(
        system_prompt=HINT_SYSTEM_PROMPT,
        messages=messages,
        temperature=0.5,
    )

    hint_text: str = response.get("hint", "What have you tried so far?")

    # Append hint as an assistant turn in chat_history so the UI can show it.
    chat_history = list(state.get("chat_history", []))
    chat_history.append({"role": "assistant", "content": hint_text})

    return {
        "chat_history": chat_history,
        "phase": "hint_generator",
    }


# ── code_classifier ────────────────────────────────────────────────────────────

def code_classifier(state: LodestoneState) -> dict:
    """
    Classify the student's latest chat message during the coding phase as
    either "reference" (syntax/API lookup) or "reasoning" (debugging/logic).

    WHY THIS DISTINCTION MATTERS:
        - "reference" questions ("what's the syntax for a dict comprehension?")
          can and should be answered directly — there's no Socratic value in
          withholding a simple syntax fact.
        - "reasoning" questions ("why does my loop run one extra time?") need
          Socratic guidance, NOT a direct answer, so the route handler will
          redirect those to hint_generator.

    INPUTS read from state:
        state["chat_history"]  — the coding-phase chat history. The last
                                  "user" turn is the student's question.
        state["code"]          — provided as context so the LLM can judge
                                  whether the question is about their specific
                                  code or a general lookup.

    OUTPUTS written to state (returned as partial dict):
        chat_history  — student's message appended as a user turn
        phase         — updated to "code_classifier"

    ADDITIONALLY returns (in the partial dict):
        _classifier_type    — "reference" or "reasoning" (used by the route)
        _classifier_answer  — direct answer string if reference, else None

    NOTE: Fields prefixed with "_" are transient — they are merged into state
    temporarily for the route handler to read, but are NOT part of the
    LodestoneState schema. They are stripped before the state is persisted.
    The route handler reads them from the merged dict, then saves only the
    canonical state fields.
    """
    chat_history = list(state.get("chat_history", []))

    student_question = ""
    for turn in reversed(chat_history):
        if turn["role"] == "user":
            student_question = turn["content"]
            break

    # Include code for context, but cap at 60 lines to control token cost.
    code_lines = state.get("code", "").strip().splitlines()
    code_snippet = "\n".join(code_lines[:60])
    if len(code_lines) > 60:
        code_snippet += "\n..."

    user_message = f"Q: {student_question}"
    if code_snippet:
        user_message += f"\nCode:\n{code_snippet}"

    response = call_groq(
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        temperature=0.1,   # low temp — this is a classification task
    )

    # Validate and extract classifier output.
    # Fallback to "reasoning" if the model returns something unexpected —
    # it's always safer to be Socratic than to accidentally give away an answer.
    classification_type: str = response.get("type", "reasoning")
    if classification_type not in ("reference", "reasoning"):
        classification_type = "reasoning"

    direct_answer: str | None = response.get("answer", None)
    # Safety: if classified as reasoning, make sure answer is None regardless.
    if classification_type == "reasoning":
        direct_answer = None

    return {
        "chat_history": chat_history,
        "phase": "code_classifier",
        # Transient fields read by the route handler, not persisted to DB.
        "_classifier_type": classification_type,
        "_classifier_answer": direct_answer,
    }


# ── intent_diff ───────────────────────────────────────────────────────────

def intent_diff(state: LodestoneState) -> dict:
    """
    Compare the student's final submitted code against their written spec.

    INPUTS read from state:
        student_spec       — the approved spec text
        code               — the student's final code (set by the route handler)
        compiler_stdout    — last run's stdout (evidence of actual behavior)
        compiler_stderr    — last run's stderr (evidence of errors)
        compiler_exit_code — 0 = ran successfully, non-zero = still failing

    OUTPUTS written to state:
        intent_diff_result — {"match": bool, "mismatch_note": str | None}
        phase              — updated to "intent_diff"
    """
    spec    = state.get("student_spec", "")
    code    = state.get("code", "")
    stdout  = state.get("compiler_stdout", "")[:500]
    stderr  = state.get("compiler_stderr", "")[:500]
    exit_c  = state.get("compiler_exit_code", None)

    user_message = (
        f"Spec:\n{spec}\n\n"
        f"Final code:\n{code}\n\n"
        f"Last run: exit={exit_c} stdout={stdout!r:.300} stderr={stderr[:300]}"
    )

    response = call_groq(
        system_prompt=DIFF_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        temperature=0.2,
    )

    match: bool = bool(response.get("match", True))
    mismatch_note: str | None = response.get("mismatch_note", None)
    if match:
        mismatch_note = None  # safety: never return a note when match=True

    return {
        "intent_diff_result": {"match": match, "mismatch_note": mismatch_note},
        "phase": "intent_diff",
    }


# ── update_sks ───────────────────────────────────────────────────────────

def update_sks(state: LodestoneState) -> dict:
    """
    Update the Student Knowledge State using an exponential moving average.
    Pure Python — no LLM call.

    EMA formula: new_value = 0.7 * old_value + 0.3 * signal

    Signals derived from this session:
        avg_hint_level_needed — EMA of hint_level used
        mistake_patterns      — append mismatch_note if present (deduplicated, max 10)
        topic_scores          — unchanged (no topic tags in this build; reserved for CP9+)

    INPUTS read from state:
        sks                — current accumulated SKS dict
        hint_level         — the hint level reached this session (1-5)
        intent_diff_result — {"match": bool, "mismatch_note": str | None}

    OUTPUTS written to state:
        sks   — updated SKS dict
        phase — updated to "update_sks"
    """
    EMA_ALPHA = 0.3   # weight given to new signal (0.7 kept from old)

    sks = dict(state.get("sks", {}))
    hint_level    = state.get("hint_level", 1)
    diff_result   = state.get("intent_diff_result") or {}
    match         = diff_result.get("match", True)
    mismatch_note = diff_result.get("mismatch_note")

    # ─ Update avg_hint_level_needed ───────────────────────────────────
    old_avg = float(sks.get("avg_hint_level_needed", 1.0))
    sks["avg_hint_level_needed"] = round(
        (1 - EMA_ALPHA) * old_avg + EMA_ALPHA * hint_level, 2
    )

    # ─ Update mistake_patterns ───────────────────────────────────────
    patterns: list = list(sks.get("mistake_patterns", []))
    if mismatch_note and mismatch_note not in patterns:
        patterns.append(mismatch_note)
    sks["mistake_patterns"] = patterns[-10:]  # keep last 10

    # ─ topic_scores: unchanged (no topic tags available yet) ────────────
    if "topic_scores" not in sks:
        sks["topic_scores"] = {}

    return {
        "sks": sks,
        "phase": "update_sks",
    }


# ── reflection ───────────────────────────────────────────────────────────

def reflection(state: LodestoneState) -> dict:
    """
    Generate one closing reflection prompt for the student.

    INPUTS read from state:
        intent_diff_result — match + mismatch_note
        sks                — updated SKS (for avg_hint_level context)
        attempt_num        — how many times the student ran their code

    OUTPUTS written to state:
        reflection_note — the closing reflection string
        phase           — updated to "reflection"
    """
    diff_result   = state.get("intent_diff_result") or {}
    match         = diff_result.get("match", True)
    mismatch_note = diff_result.get("mismatch_note", "")
    sks           = state.get("sks", {})
    hint_level    = state.get("hint_level", 1)
    attempt_num   = state.get("attempt_num", 0)

    context_msg = (
        f"Session summary:\n"
        f"- Spec matched code: {match}\n"
        f"- Mismatch detail: {mismatch_note or 'none'}\n"
        f"- Hint level reached: {hint_level}/5\n"
        f"- Run attempts: {attempt_num}\n"
        f"- Avg hint level (historical): {sks.get('avg_hint_level_needed', 1.0)}"
    )

    response = call_groq(
        system_prompt=REFLECTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context_msg}],
        temperature=0.6,   # slightly higher — reflection should feel personal
    )

    reflection_text: str = response.get(
        "reflection",
        "What's one thing you would do differently next time?"
    )

    return {
        "reflection_note": reflection_text,
        "phase": "reflection",
    }
