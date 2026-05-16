# SERP Tracker

Track Google search rankings, monitor AI Overviews, detect SERP volatility, and uncover keyword cannibalization — all from a web dashboard or CLI.

## Features

- **Rank tracking** — Fetch and store Google organic rankings for any keywords via SerpAPI
- **AI Overview monitoring** — Detect when Google's AI Overview appears and what it says
- **People Also Ask mining** — Collect PAA questions and answers for every keyword
- **SERP volatility alerts** — Compare consecutive snapshots to surface ranking changes (new entries, drops, movements)
- **Keyword cannibalization detection** — Find keywords where multiple pages from the same domain compete
- **Competitor analysis** — Aggregate domain presence across all tracked keywords (top-5 / top-10 counts)
- **Intent clustering** (CLI) — Group keywords by search intent using sentence embeddings
- **Scheduled tracking** — Automatic background SERP fetches at configurable intervals
- **Chart.js rank history** — Visualize position changes over time per keyword

## Quick Start

### Prerequisites

- Python 3.11+
- A [SerpAPI](https://serpapi.com/) API key

### Local development

```bash
git clone <repo-url> && cd serp-project
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export SERPAPI_KEY=your_key_here
python run.py
```

Open http://localhost:8000, go to **Settings**, add keywords, then hit **Track All Now** on the dashboard.

### Docker

```bash
docker compose up -d --build
```

Uses `SERPAPI_KEY` from your environment or a `.env` file. App available at http://localhost:8002.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (Python) |
| Templates | Jinja2 + Tailwind CSS (CDN) |
| Charts | Chart.js (CDN) |
| Database | SQLite (WAL mode) |
| Scheduler | APScheduler |
| API | SerpAPI (Google Search API) |
| ML (CLI) | sentence-transformers + scikit-learn |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERPAPI_KEY` | Yes | — | SerpAPI API key for Google search data |
| `TRACK_INTERVAL_HOURS` | No | `24` | Hours between automatic SERP fetches |

## Project Structure

```
serp-project/
├── app/
│   ├── main.py            # FastAPI app, lifespan, scheduler
│   ├── routes.py           # Web UI + API endpoints
│   ├── database.py         # SQLite queries and analytics
│   ├── serpapi.py          # SerpAPI client and response parsers
│   ├── templates/          # Jinja2 HTML templates
│   └── static/             # Static assets directory
├── serp_tracker.py         # Standalone CLI tool
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## CLI Tool

The standalone CLI (`serp_tracker.py`) shares the same database and can be used for one-off fetches:

```bash
export SERPAPI_KEY=your_key_here
python serp_tracker.py "best coffee" "espresso machine" --volatility 2 --cannibalization
```

See [docs/user-guide.md](docs/user-guide.md) for full CLI reference.

## Deployment

```bash
rsync -avz --exclude '.env' --exclude 'serp_history.db*' ./ personal_vps:~/serp-tracker/
ssh personal_vps 'cd ~/serp-tracker && docker compose up -d --build'
```

## Web Routes

| Route | Description |
|-------|-------------|
| `/` | Dashboard with stats and keyword table |
| `/keyword/{kw}` | Per-keyword detail with rank chart |
| `/competitors` | Domain-level competitor analysis |
| `/cannibalization` | Keyword cannibalization warnings |
| `/volatility` | SERP movement alerts |
| `/paa` | All mined People Also Ask questions |
| `/settings` | Add/remove keywords and view config |
| `/api/stats` | Dashboard stats as JSON |
| `/api/keyword/{kw}/history?days=30` | Rank history as JSON |

## License

MIT
