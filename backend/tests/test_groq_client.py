"""
test_groq_client.py — Checkpoint 2 verification script.

Tests:
  1. call_groq() returns a valid parsed dict
  2. JSON fence stripping works correctly
  3. The retry logic path can be triggered and tested manually

Run with: python test_groq_client.py
"""

from services.groq_client import call_groq, _strip_json_fences

# ── Test 1: Strip JSON fences ──────────────────────────────────────────────────
# We test this in isolation first — no API call needed.
print("--- Test 1: _strip_json_fences ---")

fenced = '```json\n{"ready": true, "question": null}\n```'
plain  = '{"ready": true, "question": null}'
no_lang = '```\n{"ready": true}\n```'

assert _strip_json_fences(fenced) == plain, "Failed: fenced with json tag"
assert _strip_json_fences(plain)  == plain, "Failed: already clean"
assert _strip_json_fences(no_lang) == '{"ready": true}', "Failed: fenced no lang"

print("PASS: fence stripping works for all 3 cases")

# ── Test 2: Live Groq call ────────────────────────────────────────────────────
# This hits the real Groq API. Make sure your .env has a valid GROQ_API_KEY.
print("\n--- Test 2: Live call_groq() ---")

system = (
    "You are a test assistant. Respond ONLY with valid JSON in this exact shape: "
    '{"status": "ok", "echo": <the user message repeated back as a string>}'
)

messages = [{"role": "user", "content": "hello lodestone"}]

result = call_groq(system_prompt=system, messages=messages, temperature=0.0)

print("Raw result dict:", result)
assert isinstance(result, dict), "Result should be a dict"
assert result.get("status") == "ok", f"Expected status=ok, got: {result}"
assert "echo" in result, f"Expected 'echo' key, got: {result}"

print("PASS: call_groq() returned a valid parsed dict")
print("Echoed back:", result["echo"])

print("\nCheckpoint 2 COMPLETE.")

def test_fence_strip_whitespace():
    """Test whitespace edge cases for _strip_json_fences."""

    # Leading/trailing whitespace around valid JSON
    whitespace_json = '   \n  {"ready": true}  \n '
    assert _strip_json_fences(whitespace_json) == '{"ready": true}', \
        "Failed: whitespace around JSON"

    # String containing only whitespace
    only_whitespace = "   \n\t   "
    assert _strip_json_fences(only_whitespace) == "", \
        "Failed: whitespace-only string"

    print("PASS: whitespace edge cases")
    print("PASS: fence stripping works for all 3 cases")

test_fence_strip_whitespace()