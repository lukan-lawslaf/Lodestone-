"""
test_code_chat.py
-----------------
CP7 manual test: code_classifier node + /code/chat endpoint.

Run with:
    cd backend
    python test_code_chat.py

Tests TWO paths through /code/chat:
  1. REFERENCE path — student asks a syntax question
     Expected: type="reference", ai_message contains a direct answer
  2. REASONING path — student asks about their specific bug
     Expected: type="reasoning", ai_message is a Socratic question (not an answer)

The session used here must already be in spec_ready=True state (i.e. the spec
phase must be complete). We achieve this by running /session/start then
repeatedly hitting /spec until spec_ready flips to True.

To skip the spec phase bootstrap, set EXISTING_SESSION_ID below to a session
ID that is already spec_ready. Leave as None to auto-bootstrap.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

# If you have a session ID that is already spec_ready, paste it here.
# Otherwise leave as None and the script will create one.
EXISTING_SESSION_ID = None

# ── ANSI colours ──────────────────────────────────────────────────────────────

def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"

# ── Helpers ───────────────────────────────────────────────────────────────────

def post(path, body):
    resp = requests.post(f"{BASE_URL}{path}", json=body, timeout=30)
    if resp.status_code >= 400:
        print(red(f"HTTP {resp.status_code} — {path}"))
        print(resp.text)
        sys.exit(1)
    return resp.json()


def bootstrap_ready_session():
    """
    Create a new session and iterate the spec loop until spec_ready == True.
    Returns the session_id of a fully spec-ready session.
    """
    print(cyan("\n-- Bootstrapping spec-ready session --"))

    # Use a very complete spec upfront so spec_gate approves quickly.
    COMPREHENSIVE_SPEC = (
        "Function signature: find_max(lst: list) -> float | int\n"
        "Returns: the maximum numeric value in the list.\n"
        "Empty list: raises ValueError('List is empty').\n"
        "Single element: returns that element.\n"
        "Duplicates: returns the max value (duplicates don't matter).\n"
        "Negative numbers: handled correctly by numeric comparison.\n"
        "Mixed int/float: Python comparison handles this natively.\n"
        "Non-numeric types: not in scope — caller is responsible for input validity.\n"
        "Does NOT modify the input list.\n"
        "No specific performance requirements for this exercise.\n"
    )

    data = post("/session/start", {
        "student_id": "test_cp7",
        "problem_id": "prob_cp7",
        "problem_text": (
            "Write a Python function `find_max(lst)` that returns "
            "the largest number in a list. Handle edge cases."
        ),
    })
    session_id = data["session_id"]
    print(f"Session started: {session_id}")
    print(f"AI first Q: {data['ai_message']}\n")

    # Answer each spec question.  If spec_gate is still asking, reply with the
    # comprehensive spec + a direct answer to whatever was just asked so the
    # model can see every edge case is accounted for.
    max_turns = 15
    for i in range(max_turns):
        result = post(f"/session/{session_id}/spec", {"student_input": COMPREHENSIVE_SPEC})
        ai_msg = result.get("ai_message", "(none)")
        print(f"Spec turn {i+1}: ready={result['ready']}  msg={ai_msg}")
        if result["ready"]:
            print(green("Spec approved ✓\n"))
            return session_id
        time.sleep(0.3)

    print(red("Spec was never approved after 15 turns — check spec_gate logic"))
    sys.exit(1)

# ── Main test ─────────────────────────────────────────────────────────────────

def main():
    session_id = EXISTING_SESSION_ID or bootstrap_ready_session()
    print(bold(f"Using session: {session_id}\n"))

    # ── Test 1: REFERENCE question ─────────────────────────────────────────
    print(cyan("── Test 1: Reference question (syntax lookup) ────────────"))
    ref_q = "How do I convert a string to an integer in Python?"
    print(f"Student: {ref_q}")
    result = post(f"/session/{session_id}/code/chat", {"student_message": ref_q})
    print(f"Type:       {result['type']}")
    print(f"AI message: {result['ai_message']}")

    if result["type"] == "reference":
        print(green("PASS — classified as reference ✓"))
    else:
        print(red("WARN — expected 'reference', got 'reasoning' (may be borderline)"))
    print()

    # ── Test 2: REASONING question ─────────────────────────────────────────
    print(cyan("── Test 2: Reasoning question (debugging help) ────────────"))
    reason_q = "Why does my for loop keep skipping the last element in the list?"
    print(f"Student: {reason_q}")
    result = post(f"/session/{session_id}/code/chat", {"student_message": reason_q})
    print(f"Type:       {result['type']}")
    print(f"AI message: {result['ai_message']}")

    if result["type"] == "reasoning":
        print(green("PASS — classified as reasoning ✓"))
    else:
        print(red("WARN — expected 'reasoning', got 'reference'"))
    print()

    # ── Test 3: Reasoning question WITH code in state ──────────────────────
    print(cyan("── Test 3: Reasoning with code context ───────────────────"))
    # First, put some code on the session state via /code/run
    run_result = requests.post(
        f"{BASE_URL}/session/{session_id}/code/run",
        json={
            "code": "def find_max(lst):\n    max_val = lst[0]\n    for i in range(len(lst) - 1):\n        if lst[i] > max_val:\n            max_val = lst[i]\n    return max_val",
            "language": "python",
        },
        timeout=30,
    )
    if run_result.status_code == 200:
        print(f"Code run: exit_code={run_result.json()['exit_code']}")

    reason_with_code = "My function doesn't return the last element even when it's the max — why?"
    print(f"Student: {reason_with_code}")
    result = post(f"/session/{session_id}/code/chat", {"student_message": reason_with_code})
    print(f"Type:       {result['type']}")
    print(f"AI message: {result['ai_message']}")

    if result["type"] == "reasoning":
        print(green("PASS — classified as reasoning with code context ✓"))
    else:
        print(red("WARN — expected 'reasoning'"))
    print()

    print(bold("CP7 test complete."))

if __name__ == "__main__":
    main()
