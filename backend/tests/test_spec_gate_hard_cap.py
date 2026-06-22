"""
test_spec_gate_hard_cap.py
--------------------------
Verifies the spec_gate 3-turn hard cap logic.
Sends 3 vague student replies in a row and confirms that spec_ready becomes True on the 3rd turn.
"""

import requests
import sys

BASE_URL = "http://localhost:8000"

def post(path, body):
    resp = requests.post(f"{BASE_URL}{path}", json=body, timeout=15)
    if resp.status_code >= 400:
        print(f"HTTP {resp.status_code} — {path}")
        print(resp.text)
        sys.exit(1)
    return resp.json()

def main():
    print("--- Test: spec_gate 3-turn hard cap ---")
    
    # 1. Start session
    data = post("/session/start", {
        "student_id": "test_hard_cap",
        "problem_id": "prob_hard_cap",
        "problem_text": "Write a Python function that returns the sum of a list of numbers.",
    })
    session_id = data["session_id"]
    print(f"Session started: {session_id}")
    print(f"AI opening Q: {data.get('ai_message')}\n")

    # 2. Reply 1: "idk"
    print("Sending Reply 1: 'idk'")
    res1 = post(f"/session/{session_id}/spec", {"student_input": "idk"})
    print(f"Reply 1 result: ready={res1['ready']}, ai_message={res1['ai_message']}")
    assert not res1['ready'], "Should not be ready on Turn 1"

    # 3. Reply 2: "sure"
    print("Sending Reply 2: 'sure'")
    res2 = post(f"/session/{session_id}/spec", {"student_input": "sure"})
    print(f"Reply 2 result: ready={res2['ready']}, ai_message={res2['ai_message']}")
    assert not res2['ready'], "Should not be ready on Turn 2"

    # 4. Reply 3: "ok"
    print("Sending Reply 3: 'ok'")
    res3 = post(f"/session/{session_id}/spec", {"student_input": "ok"})
    print(f"Reply 3 result: ready={res3['ready']}, ai_message={res3['ai_message']}")
    assert res3['ready'], "Should force ready=True exactly on Turn 3"
    assert res3['ai_message'] is None, "AI message should be None when ready"
    
    print("\nPASS: Spec gate 3-turn hard cap forced ready=True on Turn 3 successfully!")

if __name__ == "__main__":
    main()
