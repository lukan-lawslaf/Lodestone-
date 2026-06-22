"""
test_submit.py
--------------
CP8 manual test: intent_diff + update_sks + reflection + /submit endpoint.

Tests TWO paths:
  1. MATCHING submit — code correctly implements the spec → match=True
  2. MISMATCHING submit — code ignores the empty-list spec → match=False, note present

Run with:
    cd backend
    python test_submit.py
"""

import requests, sys, time

BASE_URL = "http://localhost:8000"

def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"

def post(path, body):
    resp = requests.post(f"{BASE_URL}{path}", json=body, timeout=30)
    if resp.status_code >= 400:
        print(red(f"HTTP {resp.status_code} on {path}: {resp.text}"))
        sys.exit(1)
    return resp.json()


COMPREHENSIVE_SPEC = (
    "Function signature: find_max(lst: list) -> float | int\n"
    "Returns: the maximum numeric value in the list.\n"
    "Empty list: raises ValueError('List is empty').\n"
    "Single element: returns that element.\n"
    "Duplicates: returns the max value (duplicates don't matter).\n"
    "Negative numbers: handled correctly by numeric comparison.\n"
    "Mixed int/float: Python comparison handles this natively.\n"
    "Non-numeric types: not in scope -- caller is responsible for input validity.\n"
    "Does NOT modify the input list.\n"
    "No specific performance requirements for this exercise.\n"
)

GOOD_CODE = """\
def find_max(lst):
    if not lst:
        raise ValueError("List is empty")
    return max(lst)
"""

BAD_CODE = """\
def find_max(lst):
    # deliberately ignores empty-list check
    return max(lst)
"""


def bootstrap_session(label: str) -> str:
    """Create a new spec-ready session and run the code once."""
    print(cyan(f"\n-- Bootstrapping session ({label}) --"))
    data = post("/session/start", {
        "student_id": f"test_cp8_{label}",
        "problem_id": "prob_cp8",
        "problem_text": "Write a Python function find_max(lst) that returns the largest number. Handle edge cases.",
    })
    sid = data["session_id"]
    print(f"Session: {sid}")

    for i in range(10):
        r = post(f"/session/{sid}/spec", {"student_input": COMPREHENSIVE_SPEC})
        if r["ready"]:
            print(f"Spec approved (turn {i+1}) ✓")
            break
        time.sleep(0.3)
    else:
        print(red("Spec never approved")); sys.exit(1)

    return sid


def run_code_on_session(sid: str, code: str):
    """Run code and fail if Piston has issues during runtime."""
    r = requests.post(
        f"{BASE_URL}/session/{sid}/code/run",
        json={"code": code, "language": "python"},
        timeout=20,
    )
    if r.status_code != 200:
        print(red(f"ERROR: Code run failed with HTTP {r.status_code}: {r.text}"))
        sys.exit(1)
    print(f"  Code run: exit_code={r.json()['exit_code']}")


def main():
    # ── Operational check: ensure Piston is running ────────────────────────
    import socket
    try:
        s = socket.create_connection(("localhost", 2000), timeout=2.0)
        s.close()
    except Exception:
        print(red("ERROR: Local Piston Docker container is not reachable on localhost:2000."))
        print(red("Please ensure Piston is running by starting it in Docker:"))
        print("  docker run --privileged -dit -p 2000:2000 -v piston_data:/piston --name piston_api ghcr.io/engineer-man/piston")
        sys.exit(1)

    # ── Test 1: Good code — should match ──────────────────────────────────
    sid1 = bootstrap_session("good")
    run_code_on_session(sid1, GOOD_CODE)

    print(cyan("\n-- Test 1: Submit correct code (expect match=True) --"))
    r1 = post(f"/session/{sid1}/submit", {"final_code": GOOD_CODE})
    print(f"match:         {r1['match']}")
    print(f"mismatch_note: {r1['mismatch_note']}")
    print(f"reflection:    {r1['reflection']}")
    print(f"sks avg_hint:  {r1['sks_update']['avg_hint_level_needed']}")

    if r1["match"] and r1["mismatch_note"] is None:
        print(green("PASS — match=True, no mismatch note ✓"))
    else:
        print(red(f"FAIL — expected match=True, got match={r1['match']}"))

    # ── Test 2: Bad code — should mismatch ────────────────────────────────
    sid2 = bootstrap_session("bad")
    run_code_on_session(sid2, BAD_CODE)

    print(cyan("\n-- Test 2: Submit code missing empty-list check (expect match=False) --"))
    r2 = post(f"/session/{sid2}/submit", {"final_code": BAD_CODE})
    print(f"match:         {r2['match']}")
    print(f"mismatch_note: {r2['mismatch_note']}")
    print(f"reflection:    {r2['reflection']}")
    print(f"sks patterns:  {r2['sks_update']['mistake_patterns']}")

    if not r2["match"] and r2["mismatch_note"]:
        print(green("PASS — match=False, mismatch note present ✓"))
    else:
        print(red(f"WARN — expected match=False with note, got match={r2['match']}"))

    print(bold("\nCP8 test complete."))


if __name__ == "__main__":
    main()
