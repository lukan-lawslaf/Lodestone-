"""
config.py
---------
Central configuration module for Lodestone.

Loads environment variables from the .env file once at startup.
All other modules import constants from here instead of calling
os.getenv() directly — this keeps configuration in a single place.
"""

import os
from dotenv import load_dotenv

# load_dotenv() reads the .env file in the project root and injects
# each KEY=VALUE pair into the process environment (os.environ).
# If a variable is already set in the environment (e.g. on a CI server),
# load_dotenv() leaves it alone — it never overwrites existing env vars.
load_dotenv()

# ── Groq ────────────────────────────────────────────────────────────────────
# Your Groq API key. Required — app will fail fast if missing.
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# The LLM model to use. Locked per spec.
GROQ_MODEL: str = "llama-3.3-70b-versatile"

# ── Database ─────────────────────────────────────────────────────────────────
# SQLite connection string. The three slashes mean "relative to current dir".
# This produces a file called lodestone.db in whichever directory you run the server from.
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./lodestone.db")

# ── Sanity check ─────────────────────────────────────────────────────────────
# Fail immediately at import time if the API key is missing,
# rather than getting a cryptic error later during a real request.
if not GROQ_API_KEY:
    raise EnvironmentError(
        "GROQ_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key."
    )
