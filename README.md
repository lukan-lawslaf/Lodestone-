# 🪨 Lodestone

> **The AI tutor that never gives you the answer — and that's the point.**

Lodestone is a Socratic coding education platform. Instead of handing students solutions, it asks the right questions at the right time — guiding them to write better code by *thinking*, not copying.

Built for **Bharat Academix CodeQuest** hackathon by **WildestIdeas** (Garv · Rohin · Nakul).

---

## 🧠 What Makes It Different

Most AI tools for coding either write the code *for* you or explain it *to* you. Lodestone does neither.

It runs a **Socratic loop**:

```
Student writes spec  →  AI asks "wait, what happens when X is empty?"
Student answers      →  AI asks "and what about negative numbers?"
Student answers      →  AI says "great, now write it"
Student writes code  →  Code fails
                     →  AI asks "what does your loop variable equal on the last iteration?"
Student thinks       →  Student fixes it themselves
                     →  🎉
```

The student builds understanding. Not just a working program.

---

## ⚙️ How It Works (Architecture)

```
Frontend (coming soon)
        │
        ▼
   FastAPI Backend  ◄──── SQLite (session state)
        │
        ├── LangGraph Nodes
        │     ├── spec_gate       → Socratic spec review (Groq LLM)
        │     ├── compiler_run    → Sandboxed code execution (Piston)
        │     ├── hint_generator  → Debug hints scaled 1–5 (Groq LLM)
        │     ├── code_classifier → Is this a syntax Q or a reasoning Q?
        │     ├── intent_diff     → Does code match the spec?
        │     ├── update_sks      → Track what the student struggles with
        │     └── reflection      → One closing takeaway per session
        │
        ├── Groq API  (llama-3.3-70b-versatile)
        └── Piston    (self-hosted Docker, sandboxed code runner)
```

State is serialized to SQLite between every API call — no WebSockets, no in-memory state, just clean HTTP + persistence.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop (for Piston sandbox)
- A free [Groq API key](https://console.groq.com)

### 1. Clone & Install

```bash
git clone https://github.com/lukan-lawslaf/Lodestone-.git
cd Lodestone-/backend
pip install -r requirements.txt
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env and paste your GROQ_API_KEY
```

### 3. Start the Code Execution Sandbox

```bash
# Pull and run Piston (one-time setup)
docker run --privileged -dit \
  -p 2000:2000 \
  -v piston_data:/piston \
  -e PISTON_RUN_TIMEOUT=10000 \
  -e PISTON_COMPILE_TIMEOUT=15000 \
  --name piston_api \
  ghcr.io/engineer-man/piston

# Install language runtimes (run once after the container starts)
# Wait ~10 seconds for the server to be ready, then:
curl -s http://localhost:2000/api/v2/runtimes   # should return []

# Install Python
curl -X POST http://localhost:2000/api/v2/packages \
  -H "Content-Type: application/json" \
  -d '{"language":"python","version":"3.10.0"}'

# Install JavaScript (Node)
curl -X POST http://localhost:2000/api/v2/packages \
  -H "Content-Type: application/json" \
  -d '{"language":"node","version":"18.15.0"}'

# Install Java
curl -X POST http://localhost:2000/api/v2/packages \
  -H "Content-Type: application/json" \
  -d '{"language":"java","version":"15.0.2"}'

# Install C and C++ (same gcc package)
curl -X POST http://localhost:2000/api/v2/packages \
  -H "Content-Type: application/json" \
  -d '{"language":"gcc","version":"10.2.0"}'
```

> **Windows users:** Use PowerShell's `Invoke-WebRequest` instead of `curl`:
> ```powershell
> Invoke-WebRequest -Uri "http://localhost:2000/api/v2/packages" `
>   -Method POST -ContentType "application/json" `
>   -Body '{"language":"python","version":"3.10.0"}' -UseBasicParsing
> ```

### 4. Start the API Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) — you'll see the full interactive API explorer.

---

## 📡 API Overview

| Method | Endpoint | What it does |
|--------|----------|-------------|
| `GET`  | `/` | Health check |
| `POST` | `/session/start` | Start a new session, get first Socratic question |
| `POST` | `/session/{id}/spec` | Submit spec answer, get next question or editor unlock |
| `POST` | `/session/{id}/code/run` | Run code in sandbox, get output + debug hint if it fails |
| `POST` | `/session/{id}/code/chat` | Ask a coding question — gets direct answer or Socratic hint |
| `POST` | `/session/{id}/submit` | Submit final code — get spec-match check + reflection |
| `GET`  | `/dashboard/{cohort_id}` | Teacher view: live student states + class-wide patterns |

### Example: Start a Session

```bash
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "nakul_42",
    "problem_id": "prob_001",
    "problem_text": "Write a function that returns the sum of a list of numbers."
  }'
```

```json
{
  "session_id": "cfba98f7-...",
  "phase": "spec_gate",
  "ai_message": "What should your function return if the input list is empty?"
}
```

---

## 🗂️ Project Structure

```
Lodestone-/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Environment variables
│   ├── db.py                # SQLAlchemy setup
│   ├── models.py            # DB tables (Session, StudentSKS, CohortEvent)
│   ├── schemas.py           # Pydantic request/response shapes
│   │
│   ├── graph/
│   │   ├── state.py         # LodestoneState TypedDict + helpers
│   │   └── nodes.py         # All LangGraph node functions
│   │
│   ├── services/
│   │   ├── groq_client.py   # Groq API wrapper (sync, JSON retry)
│   │   └── piston_client.py # Piston sandbox wrapper (async, 5 languages)
│   │
│   ├── prompts/
│   │   ├── spec_prompts.py      # Spec review system prompt
│   │   └── hint_prompts.py      # Hint generator system prompt (levels 1-5)
│   │
│   └── routes/
│       └── session.py       # All /session/* endpoints
│
├── .env.example
├── .gitignore
└── README.md
```

---

## 🌍 Supported Languages

| Student sends | Runtime | Version |
|---|---|---|
| `python` | Python | 3.10.0 |
| `javascript` / `js` | Node.js | 18.15.0 |
| `java` | Java | 15.0.2 |
| `cpp` / `c++` | GCC | 10.2.0 |
| `c` | GCC | 10.2.0 |

All code runs inside isolated Piston containers — no network access, no filesystem access, 10-second timeout.

---

## 🏗️ Build Checkpoints

The backend is being built checkpoint by checkpoint, each testable independently:

- [x] **CP1** — DB boots, tables created cleanly
- [x] **CP2** — Groq client works, JSON parsing with retry
- [x] **CP3** — `spec_gate` node, Socratic spec review
- [x] **CP4** — `/session/start` + `/session/{id}/spec` — full spec loop via HTTP
- [x] **CP5** — Piston client, 5 languages, sandboxed execution
- [x] **CP6** — `compiler_run` + `hint_generator` + `/code/run` endpoint
- [ ] **CP7** — `code_classifier` + `/code/chat` endpoint
- [ ] **CP8** — `intent_diff` + `update_sks` + `reflection` + `/submit`
- [ ] **CP9** — `dashboard.py` — cohort analytics endpoint

---

## 🔐 Environment Variables

```env
GROQ_API_KEY=your_groq_key_here
DATABASE_URL=sqlite:///./lodestone.db
```

Get your free Groq key at [console.groq.com](https://console.groq.com). The free tier is generous enough for hackathon use.

---

## 🛠️ Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI | Fast, async, automatic docs |
| LLM | Groq `llama-3.3-70b` | Fast inference, free tier |
| Workflow | LangGraph | Clean node-based state machine |
| Code sandbox | Piston (self-hosted) | Isolated containers, 5 languages |
| Database | SQLite + SQLAlchemy | Zero-config persistence |

---

## 🤝 Team

**WildestIdeas** — *Bharat Academix CodeQuest*

| Name | Role |
|------|------|
| Garv | Lead |
| Rohin | Backend |
| Nakul | Backend |

---

<div align="center">

*Built with caffeine, curiosity, and a deep distrust of "just Google it"*

</div>
