"""
services/piston_client.py
--------------------------
Wraps all calls to the Piston code execution API.

Piston (https://github.com/engineer-man/piston) is an open-source, sandboxed
code execution engine. The public instance at emkc.org accepts code snippets,
runs them in isolated containers, and returns stdout/stderr/exit_code.

WHY ASYNC HERE (vs sync for Groq):
    Code execution can take 2-5 seconds. If we used synchronous requests,
    the FastAPI event loop would block for every user waiting for their code
    to run. Using httpx.AsyncClient with async/await lets other requests
    (health checks, other students' API calls) be served concurrently while
    we wait for Piston's container to spin up and run the code.

    Unlike the Groq client (where we wrapped a sync SDK), httpx natively
    supports async — so we can write a clean async function here without
    any run_in_executor() gymnastics.

TIMEOUT STRATEGY:
    We set a 15-second timeout on the Piston request. If a student submits
    an infinite loop, the container will keep running forever without a
    timeout. 15s is generous for correct code but catches most infinite loops.

ERROR HANDLING:
    resp.raise_for_status() raises httpx.HTTPStatusError if Piston returns
    4xx/5xx. We let this propagate — the route handler catches it and returns
    a 500 to the client. In production you'd add retries here.
"""

import httpx

# Self-hosted Piston instance running in Docker on localhost:2000.
# Start with: docker run --privileged -dit -p 2000:2000 -v piston_data:/piston --name piston_api ghcr.io/engineer-man/piston
# Runtimes installed via POST /api/v2/packages (see setup notes above).
# NOTE: self-hosted Piston v3 base path is /api/v2 (no trailing /piston).
PISTON_URL = "http://localhost:2000/api/v2"

# Language version lookup table.
# Piston v3 runtime names come from what /api/v2/runtimes reports AFTER install.
# The node package registers as "javascript"; gcc registers as "c++".
# Always verify with: GET http://localhost:2000/api/v2/runtimes
LANGUAGE_VERSIONS: dict[str, str] = {
    "python":     "3.10.0",
    "java":       "15.0.2",
    "javascript": "18.15.0",  # node package installs as "javascript"
    "c++":        "10.2.0",   # gcc package installs as "c++"
    "c":          "10.2.0",   # gcc also handles plain C
}

# Map from student-friendly names → registered Piston runtime language strings.
# Some aliases are already registered by Piston (js, py3, etc.) but we use
# canonical forms here so we control the mapping explicitly.
PISTON_LANG_MAP: dict[str, str] = {
    "python":     "python",
    "java":       "java",
    "javascript": "javascript",
    "js":         "javascript",
    "node":       "javascript",
    "cpp":        "c++",
    "c++":        "c++",
    "c":          "c",         # Piston gcc package registers both c and c++
}


async def run_code(code: str, language: str) -> dict:
    """
    Execute a code snippet in Piston's sandboxed environment.

    Args:
        code:     The full source code to execute.
        language: One of "python", "java", "javascript", "cpp".
                  Anything else falls back to python's version string.

    Returns:
        A dict with three keys:
          {
              "stdout":    str,   # everything printed to stdout
              "stderr":    str,   # exceptions, compile errors, runtime errors
              "exit_code": int    # 0 = success, non-zero = error
          }

    Raises:
        httpx.HTTPStatusError:  If Piston returns a non-2xx HTTP response.
        httpx.TimeoutException: If execution exceeds the 15-second timeout.

    HOW TO READ THE RESULT:
        exit_code == 0  → code ran successfully, check stdout for output
        exit_code != 0  → something went wrong, check stderr for the error
                          message (Python traceback, Java compile error, etc.)
    """
    # Translate student-facing language names to Piston package names.
    # Students say "javascript" or "cpp"; Piston wants "node" / "gcc".
    # Unknown languages fall back to "python" (safe hackathon default).
    piston_lang = PISTON_LANG_MAP.get(language.lower(), "python")
    version = LANGUAGE_VERSIONS.get(piston_lang, "3.10.0")

    # Build the Piston request payload.
    # "files" is a list — Piston supports multi-file projects, but we only
    # ever send one file for this use case.
    payload = {
        "language": piston_lang,
        "version":  version,
        "files":    [{"content": code}],
    }

    # httpx.AsyncClient is the async equivalent of requests.Session.
    # 'async with' ensures the client is properly closed after the request,
    # even if an exception occurs (same pattern as 'yield' in get_db).
    #
    # timeout=15.0 applies to the entire request lifecycle (connect + read).
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{PISTON_URL}/execute", json=payload)
        # Raise an exception for HTTP 4xx/5xx responses.
        # Without this, a 429 Rate Limited or 500 Server Error would silently
        # return an empty/malformed dict and cause confusing downstream errors.
        resp.raise_for_status()
        data = resp.json()

    # Piston wraps execution results under the "run" key.
    # We extract it with a default empty dict so .get() calls below don't crash
    # if Piston's response format ever changes.
    run = data.get("run", {})

    # exit_code ("code" in Piston's response) is null when the process was
    # killed by SIGKILL (e.g. timeout, OOM). We normalise null → -1 so that
    # callers always receive an int and can treat non-zero as an error.
    raw_code = run.get("code")
    exit_code = raw_code if raw_code is not None else -1

    # Surface timeout as a readable stderr message when Piston says so.
    stderr = run.get("stderr", "")
    if run.get("message") == "Time limit exceeded" and not stderr:
        stderr = "Time limit exceeded — your code took too long to run."

    return {
        "stdout":    run.get("stdout", ""),
        "stderr":    stderr,
        "exit_code": exit_code,
    }
