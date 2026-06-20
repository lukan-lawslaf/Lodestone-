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

    # Build the current user message that describes what the student wrote.
    # This is always the last "user" turn in the conversation.
    current_user_message = (
        f"Problem statement:\n{problem}\n\n"
        f"Student's current specification:\n{student_spec}\n\n"
        f"Based on the specification above and our conversation so far, "
        f"ask your next clarifying question or mark ready if the spec is complete."
    )

    # Construct the messages list: history + current user message.
    # spec_history already contains previous [user, assistant, user, assistant...]
    # turns. We append the new user message at the end.
    messages = spec_history + [{"role": "user", "content": current_user_message}]

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

    if phase == "compiler_run" or state.get("compiler_stderr"):
        # DEBUG MODE - include code + compiler output as context.
        context_msg = (
            f"The student's code:\n`\n{state.get('code', '')}\n`\n\n"
            f"Compiler/runtime output:\n"
            f"stdout: {repr(state.get('compiler_stdout', ''))}\n"
            f"stderr: {repr(state.get('compiler_stderr', ''))}\n"
            f"exit_code: {state.get('compiler_exit_code', -1)}\n\n"
            f"Hint level: {hint_level}/5. Generate a hint at this level."
        )
    else:
        # SPEC MODE - use last few spec conversation turns as context.
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in state.get("spec_history", [])[-6:]
        )
        context_msg = (
            f"Spec conversation so far:\n{history_text}\n\n"
            f"Hint level: {hint_level}/5. Help the student think about "
            f"what's missing from their spec."
        )

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
