# SERP Tracker

Track Google search rankings, monitor AI Overviews, detect SERP volatility, and uncover keyword cannibalization — all from a web dashboard or CLI.

Built for the **SerpApi PyCon US Raffle** (May 2026).

---

## Stack

| Layer | Stack |
|-------|-------|
| Backend | FastAPI (Python), APScheduler, SerpAPI SDK |
| Frontend | Jinja2 + Tailwind CSS (CDN) |
| Charts | Chart.js (CDN) |
| Database | SQLite (WAL mode) |
| ML (CLI) | sentence-transformers + scikit-learn |
| Deploy | Docker Compose |

---

## Quick Start

### Prerequisites

- [Python 3.11+](https://www.python.org/)
- A [SerpAPI API key](https://serpapi.com/manage-api-key) (free tier: 250 searches/month)

### 1. Clone and install

```bash
git clone https://github.com/Joe342wise/serp-project.git
cd serp-project
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export SERPAPI_KEY=your_key_here
```

Or create a `.env` file:

```
SERPAPI_KEY=your_key_here
```

### 3. Run

```bash
python run.py
```

Open `http://localhost:8000`, go to **Settings**, add keywords, then hit **Track All Now** on the dashboard.

### Docker

```bash
docker compose up -d --build
```

Uses `SERPAPI_KEY` from your environment or a `.env` file. App available at `http://localhost:8002`.

---

## How it works

1. You add keywords in the Settings page
2. The scheduler (APScheduler) or manual trigger sends each keyword to SerpAPI's Google search engine
3. Parsed results (rank, URL, title, snippet, AI Overview, PAA) are stored in SQLite
4. The dashboard queries the database for stats, charts, volatility alerts, and cannibalization warnings

---

## Project structure

```
app/
  main.py            — FastAPI app, lifespan, scheduler
  routes.py          — Web UI + API endpoints
  database.py        — SQLite queries and analytics
  serpapi.py         — SerpAPI client and response parsers
  templates/         — Jinja2 HTML templates
  static/            — Static assets
serp_tracker.py      — Standalone CLI tool
run.py               — Entrypoint that launches the FastAPI server
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

---

## Raffle Entry

Built by Joseph Osei Yaw Nyarko for the **SerpApi PyCon US Raffle**.

- App: [seobyserp.osei.app](https://seobyserp.osei.app)
- Repo: [serp-project](https://github.com/Joe342wise/serp-project.git)
