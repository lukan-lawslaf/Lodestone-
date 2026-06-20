"""
test_code_run.py - Checkpoint 6 verification script.

Tests POST /session/{id}/code/run with three cases:
  1. Python success  -> exit_code 0, stdout present, ai_message null
  2. Python error    -> exit_code != 0, stderr present, ai_message (hint)
  3. JavaScript      -> exit_code 0, stdout present

Run with: uvicorn main:app in one terminal, then python test_code_run.py here.
"""

import requests
import json

BASE = "http://127.0.0.1:8000"

# ── Setup: create a session and fast-track past spec_gate ─────────────────────
print("=== Setting up session ===")
start = requests.post(f"{BASE}/session/start", json={
    "student_id": "test_cp6",
    "problem_id":  "prob_001",
    "problem_text": "Write a function that returns the sum of a list of numbers.",
}).json()
session_id = start["session_id"]
print(f"session_id: {session_id}")
print(f"phase:      {start['phase']}")
print(f"ai_message: {start['ai_message'][:60]}...")

# Fast-track spec gate - send a complete spec to unlock the editor
print("\n=== Fast-tracking spec gate ===")
for i in range(6):  # up to 6 tries to get spec_ready
    spec_resp = requests.post(f"{BASE}/session/{session_id}/spec", json={
        "student_input": (
            "I will write a function sum_list(numbers) that takes a list of "
            "integers or floats, iterates through them, and returns the total. "
            "If the list is empty it returns 0. Negative numbers are handled. "
            "No null/None inputs expected."
        )
    }).json()
    print(f"  attempt {i+1}: ready={spec_resp['ready']}")
    if spec_resp["ready"]:
        break

print(f"editor_unlocked: {spec_resp['editor_unlocked']}")

# ── Test 1: Python success ────────────────────────────────────────────────────
print("\n--- Test 1: Python success ---")
r1 = requests.post(f"{BASE}/session/{session_id}/code/run", json={
    "code": "def sum_list(nums):\n    return sum(nums)\nprint(sum_list([1,2,3]))",
    "language": "python",
}).json()
print(f"stdout:     {repr(r1['stdout'].strip())}")
print(f"stderr:     {repr(r1['stderr'][:60])}")
print(f"exit_code:  {r1['exit_code']}")
print(f"ai_message: {r1['ai_message']}")

assert r1["exit_code"] == 0, "Expected exit_code 0"
assert "6" in r1["stdout"], "Expected '6' in stdout"
assert r1["ai_message"] is None, "Expected no hint on success"
print("PASS")

# ── Test 2: Python error → hint generated ─────────────────────────────────────
print("\n--- Test 2: Python error -> hint ---")
r2 = requests.post(f"{BASE}/session/{session_id}/code/run", json={
    "code": "x = 1 / 0",
    "language": "python",
}).json()
print(f"exit_code:  {r2['exit_code']}")
print(f"stderr:     {repr(r2['stderr'][:80])}")
print(f"ai_message: {r2['ai_message']}")

assert r2["exit_code"] != 0, "Expected non-zero exit_code"
assert r2["ai_message"] is not None, "Expected a Socratic hint"
assert len(r2["ai_message"]) > 10, "Expected a non-trivial hint"
print("PASS")

# ── Test 3: JavaScript success ────────────────────────────────────────────────
print("\n--- Test 3: JavaScript success ---")
r3 = requests.post(f"{BASE}/session/{session_id}/code/run", json={
    "code": "console.log([1,2,3].reduce((a,b)=>a+b,0))",
    "language": "javascript",
}).json()
print(f"stdout:     {repr(r3['stdout'].strip())}")
print(f"exit_code:  {r3['exit_code']}")
print(f"ai_message: {r3['ai_message']}")

assert r3["exit_code"] == 0, "Expected exit_code 0 for JS"
assert "6" in r3["stdout"], "Expected '6' in stdout"
print("PASS")

print("\nCheckpoint 6 COMPLETE.")
