# Healthy5.AI

An AI-powered personal health companion that integrates with Telegram to provide conversational health support through specialized agents.

## What It Does

- **Weight Tracking** — Log, update, and review body weight over time
- **Mind Buddy** — A gentle mental health companion with journaling and mood support
- **Reminders** — Create recurring self-care reminders (daily or interval-based)
- **Profile Management** — Stores personal context for personalized interactions
- **Multi-Bot Support** — Run multiple Telegram bots from a single backend

## Architecture

Event-driven backend built with **FastAPI**, **Redis/RQ**, and **LangGraph**:

```
Telegram → FastAPI Gateway → Redis Queue → Agent Worker (LangGraph) → Egress Worker → Telegram
```

- **LLM**: Groq (cloud) or Ollama (local) — configurable via Admin UI
- **Database**: MongoDB
- **Frontend**: Next.js admin dashboard for managing users, settings, and integrations

## Quick Start

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/create_admin.py <username> <password>
./scripts/start_dev.sh

# Frontend
cd frontend
npm install && npm run dev
```

**Requires:** Python 3.12+, Node.js 18+, Redis, MongoDB

## Docs

- [Architecture](docs/architecture.md) — System design and event flow
- [Running Locally](docs/RUN_LOCALLY.md) — Detailed setup instructions
