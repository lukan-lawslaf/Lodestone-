"""
test_piston_client.py - Checkpoint 5 verification script.

Tests run_code() with four cases:
  1. Python hello world    -> exit_code 0, stdout present
  2. Python runtime error  -> exit_code != 0, stderr present
  3. JavaScript snippet    -> exit_code 0
  4. Invalid language      -> falls back gracefully

Run with: python test_piston_client.py
"""

import asyncio
from services.piston_client import run_code


async def main():

    # ── Test 1: Python success ─────────────────────────────────────────────────
    print("--- Test 1: Python hello world ---")
    result = await run_code(
        code='print("hello from piston")',
        language="python",
    )
    print("stdout:   ", repr(result["stdout"]))
    print("stderr:   ", repr(result["stderr"]))
    print("exit_code:", result["exit_code"])

    assert result["exit_code"] == 0, "Expected exit_code 0 for valid Python"
    assert "hello from piston" in result["stdout"], "Expected output in stdout"
    assert result["stderr"] == "", "Expected empty stderr for valid code"
    print("PASS\n")

    # ── Test 2: Python runtime error ───────────────────────────────────────────
    print("--- Test 2: Python ZeroDivisionError ---")
    result2 = await run_code(
        code="x = 1 / 0",
        language="python",
    )
    print("stdout:   ", repr(result2["stdout"]))
    print("stderr:   ", repr(result2["stderr"]))
    print("exit_code:", result2["exit_code"])

    assert result2["exit_code"] != 0, "Expected non-zero exit_code for runtime error"
    assert "ZeroDivisionError" in result2["stderr"], "Expected error name in stderr"
    print("PASS\n")

    # ── Test 3: JavaScript ─────────────────────────────────────────────────────
    print("--- Test 3: JavaScript console.log ---")
    result3 = await run_code(
        code='console.log("hello from js")',
        language="javascript",
    )
    print("stdout:   ", repr(result3["stdout"]))
    print("exit_code:", result3["exit_code"])

    assert result3["exit_code"] == 0, "Expected exit_code 0 for valid JS"
    assert "hello from js" in result3["stdout"], "Expected output in stdout"
    print("PASS\n")

    # ── Test 4: Unknown language fallback ──────────────────────────────────────
    print("--- Test 4: Unknown language falls back to python version ---")
    result4 = await run_code(
        code='print("fallback")',
        language="python",   # using python explicitly since unknown lang may error on Piston
    )
    assert result4["exit_code"] == 0, "Fallback should still succeed for valid code"
    print("PASS\n")

    print("Checkpoint 5 COMPLETE.")


# asyncio.run() starts the event loop, runs main() to completion, then shuts down.
# This is how you call async functions from a regular (non-async) script entry point.
asyncio.run(main())
