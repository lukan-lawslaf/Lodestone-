"""
services/groq_client.py
-----------------------
The single place in Lodestone that knows HOW to talk to the Groq LLM API.

Every graph node that needs an LLM response calls the one public function
here: call_groq(). Nodes don't know about HTTP, JSON parsing, or retries —
they just pass a system prompt and a list of messages and get a dict back.

Architecture principle:
    Nodes decide WHAT to ask.
    This module decides HOW to ask it, parse it, and retry if needed.

Sync vs Async note:
    The Groq SDK is synchronous (it uses requests under the hood).
    FastAPI is async. Calling a blocking function inside an async endpoint
    would freeze the entire server event loop for the duration of the API call.

    Solution: asyncio.get_event_loop().run_in_executor() runs the blocking
    call in a background thread pool. The event loop stays free to handle
    other incoming requests while we wait for Groq.

    We expose:
        call_groq()       → sync, for use in test scripts and graph nodes
                            called from sync contexts (non-async node functions)
        call_groq_async() → async wrapper, for use directly in async FastAPI
                            route handlers if ever needed
"""

import json
import asyncio
from functools import partial
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL


# ── Client singleton ──────────────────────────────────────────────────────────
# We create ONE Groq client instance at module load time and reuse it.
# Creating a new client per call is wasteful — it would re-read the API key
# and set up the HTTP session from scratch on every request.
# A module-level singleton is safe here because Groq client is stateless.
_client = Groq(api_key=GROQ_API_KEY)


# ── JSON fence stripper ───────────────────────────────────────────────────────
def _strip_json_fences(text: str) -> str:
    """
    Remove markdown code fences that LLMs sometimes wrap their JSON in.

    Even when we instruct the model "respond in JSON only", it occasionally
    returns something like:
        ```json
        {"ready": true, "question": null}
        ```

    This function strips the backtick fences so json.loads() can parse it.
    We strip both ``` and ```json variants, and trim surrounding whitespace.
    """
    text = text.strip()
    # Remove opening fence (```json or just ```)
    if text.startswith("```"):
        # Find the end of the first line (the fence line) and skip it
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
    # Remove closing fence
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()


# ── Core sync function ────────────────────────────────────────────────────────
def call_groq(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.3,
) -> dict:
    """
    Send a conversation to Groq and return the model's response as a dict.

    This is the primary function every graph node calls. It handles:
      - Prepending the system prompt to the message list
      - Parsing the model's JSON response
      - Stripping any markdown fences if present
      - Retrying ONCE if JSON parsing fails, with a correction message

    Args:
        system_prompt: The system instruction for the model (from prompts/).
                       Defines the model's persona and output format.
        messages:      Conversation history as a list of dicts.
                       Each dict must have "role" and "content" keys.
                       Roles must be "user" or "assistant".
                       Example: [{"role": "user", "content": "My spec is..."}]
        temperature:   Controls randomness. 0.0 = fully deterministic.
                       0.3 = slight variation (good for structured JSON).
                       1.0 = creative/unpredictable.
                       We default to 0.3 for consistent JSON output.

    Returns:
        Parsed Python dict from the model's JSON response.

    Raises:
        json.JSONDecodeError: If both the first attempt AND the retry fail to
                              produce valid JSON. Callers should handle this.
        groq.APIError:        If the Groq API returns an HTTP error (e.g. 429
                              rate limit, 500 server error).
    """
    # The Groq API expects the system message as the first item in the list.
    # We build the full message list by prepending the system prompt.
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    def _make_request(msg_list: list[dict]) -> str:
        """
        Inner helper: makes one API call and returns the raw response string.
        Isolated so we can call it twice (initial + retry) without duplication.
        """
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=msg_list,
            temperature=temperature,
            # Note: we intentionally do NOT set response_format={"type": "json_object"}
            # here because not all Groq models support that parameter. Instead, we
            # enforce JSON via the system prompt and strip/retry manually.
        )
        # The response object follows OpenAI's format:
        # response.choices[0].message.content is the model's text reply.
        return response.choices[0].message.content

    # ── First attempt ─────────────────────────────────────────────────────────
    raw = _make_request(full_messages)

    try:
        return json.loads(_strip_json_fences(raw))

    except json.JSONDecodeError:
        # ── Retry once ────────────────────────────────────────────────────────
        # The model returned malformed JSON. We add its bad response and a
        # correction instruction to the conversation, then try once more.
        # This "self-correcting" pattern works well in practice — the model
        # sees its own mistake and produces clean JSON on the second attempt.
        print(f"[groq_client] JSON parse failed on first attempt. Retrying...")
        print(f"[groq_client] Bad response was: {raw[:200]}")  # log first 200 chars

        retry_messages = full_messages + [
            # Include the model's bad response as an "assistant" turn
            {"role": "assistant", "content": raw},
            # Then tell it to fix itself
            {
                "role": "user",
                "content": (
                    "Your previous response was not valid JSON. "
                    "Respond with a single valid JSON object only. "
                    "No markdown, no backticks, no preamble, no trailing commas."
                ),
            },
        ]

        retry_raw = _make_request(retry_messages)
        # Let this raise naturally if it still fails — callers must handle it.
        return json.loads(_strip_json_fences(retry_raw))


# ── Async wrapper ─────────────────────────────────────────────────────────────
async def call_groq_async(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.3,
) -> dict:
    """
    Async-safe wrapper around call_groq() for use in async FastAPI handlers.

    WHY THIS EXISTS:
    call_groq() is synchronous (it blocks while waiting for Groq's response).
    In an async FastAPI route, calling a blocking function directly would
    freeze the entire event loop — no other requests could be processed
    while waiting for the LLM.

    run_in_executor() solves this by running the blocking function in a
    separate thread from the thread pool. The event loop can do other work
    while that thread waits for the HTTP response. When the thread finishes,
    asyncio resumes this coroutine with the result.

    functools.partial() is used to bind arguments to call_groq so we can
    pass it to run_in_executor() which only accepts zero-argument callables.

    Usage:
        result = await call_groq_async(system_prompt, messages)
    """
    loop = asyncio.get_event_loop()
    # partial() creates a new callable: call_groq with arguments pre-filled.
    # This is equivalent to: lambda: call_groq(system_prompt, messages, temperature)
    bound_call = partial(call_groq, system_prompt, messages, temperature)
    # Run the blocking call in the default thread pool executor.
    # None = use the default ThreadPoolExecutor managed by asyncio.
    return await loop.run_in_executor(None, bound_call)
