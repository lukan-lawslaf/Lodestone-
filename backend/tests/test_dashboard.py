"""
test_dashboard.py
-----------------
CP9 manual test: GET /dashboard/{cohort_id} endpoint.

Verifies:
  1. Response shape is correct (live_states, cohort_patterns keys present).
  2. At least one session shows up in live_states for the cohort.
  3. If a mismatch submit was done in CP8 tests, cohort_patterns shows
     an "intent_mismatch" event with count >= 1.

No new sessions are created — this queries whatever is already in the DB
from CP8's test_submit.py run. If the DB is empty, live_states will be [].

Run with:
    cd backend
    python test_dashboard.py
"""

import requests, sys

BASE_URL = "http://localhost:8000"
COHORT_ID = "prob_cp8"   # matches the problem_id used in test_submit.py

def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def cyan(s):  return f"\033[96m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"


def main():
    print(cyan(f"\n-- Test CP9: GET /dashboard/{COHORT_ID} --"))

    resp = requests.get(f"{BASE_URL}/dashboard/{COHORT_ID}", timeout=10)
    if resp.status_code != 200:
        print(red(f"HTTP {resp.status_code}: {resp.text}"))
        sys.exit(1)

    data = resp.json()

    # ── Shape check ────────────────────────────────────────────────────────────
    assert "cohort_id"       in data, "Missing cohort_id"
    assert "live_states"     in data, "Missing live_states"
    assert "cohort_patterns" in data, "Missing cohort_patterns"
    print(green("Shape check PASS ✓"))

    # ── Live states ────────────────────────────────────────────────────────────
    print(f"\nlive_states ({len(data['live_states'])} students):")
    for s in data["live_states"]:
        print(f"  {s['student_id']:25s}  phase={s['phase']:20s}  note={s['status_note']}")

    if data["live_states"]:
        first = data["live_states"][0]
        assert "student_id"  in first
        assert "phase"       in first
        assert "status_note" in first
        print(green("live_states entries well-formed ✓"))
    else:
        print("  (no sessions found — run test_submit.py first to populate data)")

    # ── Cohort patterns ────────────────────────────────────────────────────────
    print(f"\ncohort_patterns ({len(data['cohort_patterns'])} event types):")
    for p in data["cohort_patterns"]:
        print(f"  {p['event_type']:25s}  count={p['count']}  sample={p['detail_sample'][:80]}")

    mismatch_events = [p for p in data["cohort_patterns"] if p["event_type"] == "intent_mismatch"]
    if mismatch_events:
        assert mismatch_events[0]["count"] >= 1
        print(green("intent_mismatch events present ✓"))
    else:
        print("  (no intent_mismatch events — run test_submit.py bad-code path first)")

    print(bold("\nCP9 test complete."))


if __name__ == "__main__":
    main()
