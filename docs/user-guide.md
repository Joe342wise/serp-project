# SERP Tracker User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Web Interface](#web-interface)
3. [CLI Tool](#cli-tool)
4. [Configuration](#configuration)
5. [Deployment](#deployment)
6. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What is SERP Tracker?

SERP Tracker monitors Google search ranking positions for keywords you care about. It periodically fetches SERP data via the SerpAPI service, stores the results in a local SQLite database, and surfaces insights through a web dashboard:

- **Rankings** — Who shows up at each position, and how that changes over time
- **AI Overviews** — When Google's AI-generated answers appear
- **People Also Ask** — Related questions Google surfaces for each keyword
- **Volatility** — Sudden ranking movements between snapshots
- **Cannibalization** — Multiple pages from the same domain competing for the same keyword
- **Competitors** — Which domains appear most often across your keyword set

### Prerequisites

- **SerpAPI key** — Sign up at [serpapi.com](https://serpapi.com) and get an API key. The free tier includes 100 searches/month.
- **Python 3.11+** or **Docker** — Either works for running the app.

### First Run

1. Set your API key and start the server:

   ```bash
   export SERPAPI_KEY=your_key_here
   python run.py
   ```

2. Open http://localhost:8000 in your browser.

3. Go to **Settings** → type a keyword (e.g. `best running shoes`) → click **Add Keyword**.

4. Go back to the **Dashboard** and click **Track All Now**. The first snapshot will appear within seconds.

5. Add more keywords and let the scheduler run automatically (every 24 hours by default) to build rank history.

---

## Web Interface

### Dashboard (`/`)

The home page shows four stat cards at the top:

| Card | What it tells you |
|------|-------------------|
| Keywords | Number of keywords being tracked |
| Snapshots | Total SERP fetches stored |
| AI Overviews | How many snapshots contained an AI Overview |
| Alerts | Number of unread volatility/cannibalization alerts |

Below the stats, the **Tracked Keywords** table lists every keyword with:
- Its current top-ranked domain and position (from the latest snapshot)
- Click the keyword to open its detail page
- A **Track All Now** button to trigger an immediate fetch for all keywords

The right sidebar shows **Recent Alerts** — the latest volatility or cannibalization events.

### Keyword Detail (`/keyword/{keyword}`)

Click any keyword from the dashboard to see:

- **Track Now** button — Fetch a fresh snapshot for just this keyword
- **Volatility banner** — Yellow warning if ranking changes were detected between the last two snapshots
- **Rank History chart** — A multi-line Chart.js chart showing each domain's position over time (y-axis is reversed: position 1 is at the top)
- **Latest Rankings table** — All organic results from the most recent snapshot (AI Overviews highlighted in purple)
- **People Also Ask sidebar** — PAA questions mined from the latest snapshot

### Competitors (`/competitors`)

Aggregates every domain that appears in your keyword snapshots. For each domain:

- **Keyword count** — How many of your tracked keywords this domain ranks for
- **Top 5 / Top 10** — How many of those rankings are in the top 5 or top 10
- **Keywords list** — Clickable pills showing each keyword and the domain's position

Use this to understand which competitors dominate your keyword space.

### Cannibalization (`/cannibalization`)

Detects keywords where multiple URLs from the same domain appear in the SERP. For each match:

- The keyword and a list of competing pages with their positions
- The best-performing page is highlighted in green
- Uses data from the last 14 days

If you see cannibalization warnings, consider consolidating those pages or adjusting your internal linking.

### Volatility (`/volatility`)

Shows ranking movement between the two most recent snapshots for each keyword:

- **New** — A domain appeared in the rankings
- **Dropped** — A domain disappeared from the rankings
- **Moved** — A domain changed position (shown as `old → new`)

The alert history table below logs every volatility event with timestamps, alert types, and messages.

### People Also Ask (`/paa`)

A searchable grid of all PAA questions ever collected. Each card shows:

- The keyword that triggered the PAA
- The question text
- A snippet preview
- A link to the answer source

### Settings (`/settings`)

**Add Keyword form:**
- **Keyword** (required) — The search query to track
- **Location** — Geographic targeting (default: United States)
- **Device** — desktop, mobile, or tablet

**Tracked Keywords list:**
- Every keyword with its location and device settings
- Remove button deletes the keyword and all associated data (snapshots, rankings, PAA, alerts)

**Configuration status:**
- Whether `SERPAPI_KEY` is set
- The tracking interval (from `TRACK_INTERVAL_HOURS`)

---

## CLI Tool

The standalone CLI (`serp_tracker.py`) is a self-contained script that does NOT require the web server to be running. It shares the same SQLite database (`serp_history.db`), so data collected via the CLI appears in the web UI and vice versa.

### Usage

```bash
python serp_tracker.py <keyword> [<keyword> ...] [options]
```

### Examples

Fetch and report on a single keyword:
```bash
export SERPAPI_KEY=your_key_here
python serp_tracker.py "best wireless headphones"
```

Fetch multiple keywords with location targeting:
```bash
python serp_tracker.py "coffee shop" "espresso machine" --location "United Kingdom" --device mobile
```

Fetch and check volatility (requires at least 3 prior snapshots):
```bash
python serp_tracker.py "best coffee" --volatility 2
```

Detect keyword cannibalization across the database:
```bash
python serp_tracker.py --cannibalization
```

Cluster keywords by search intent using ML embeddings:
```bash
python serp_tracker.py --cluster
```

### Options Reference

| Option | Description |
|--------|-------------|
| `keywords` (positional) | One or more keywords to track. Required. |
| `--location` | Geographic search location (default: `"United States"`) |
| `--device` | Device type: `desktop`, `mobile`, or `tablet` (default: `desktop`) |
| `--volatility N` | Compare the last N snapshots and report ranking changes |
| `--cannibalization` | Scan the last 7 days for cannibalized keywords |
| `--cluster` | Group keywords by search intent using KMeans on sentence embeddings |

### Reports

The CLI prints structured reports to stdout:
- **AI Overview** — If present, shows the first 120 characters
- **Top 5 Rankings** — Domain, URL, and title for each position
- **People Also Ask** — Up to 3 PAA questions
- **Knowledge Graph** — Entity name if Google returned one
- **Volatility changes** — New, dropped, or moved domains with position details
- **Cannibalization warnings** — Keywords with multiple pages from the same domain
- **Intent clusters** — Groups of semantically related keywords

---

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERPAPI_KEY` | Yes | — | Your SerpAPI API key. The app will not fetch data without this. |
| `TRACK_INTERVAL_HOURS` | No | `24` | Hours between automatic background SERP fetches (web app only). |

### Scheduler

The web app's background scheduler starts automatically when both conditions are met:
1. `SERPAPI_KEY` is set
2. At least one keyword exists in the database

The scheduler runs `track_all_job()` which loops through every active keyword, fetches SERP data, stores it, and sleeps 0.5 seconds between keywords. You can also trigger manual fetches via the **Track All Now** button or the `POST /track/all` endpoint.

### Database

The SQLite database is stored at `serp_history.db` in the project root. WAL mode is enabled for better concurrency. The database is automatically initialized with all required tables on first startup.

To reset: stop the app and delete the `.db` files (including `-shm` and `-wal` siblings). The tables will be recreated on next start.

---

## Deployment

### Docker (recommended for production)

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f app

# Stop
docker compose down
```

The database persists in `./serp_history.db` on the host (volume-mounted into the container). Set environment variables in a `.env` file:

```
SERPAPI_KEY=your_key_here
TRACK_INTERVAL_HOURS=24
```

### Remote server deployment

```bash
# Copy files
rsync -avz --exclude '.env' --exclude 'serp_history.db*' ./ user@host:~/serp-tracker/

# SSH in and start
ssh user@host
cd ~/serp-tracker
docker compose up -d --build
```

### Manual (Python)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
SERPAPI_KEY=your_key_here python run.py
```

---

## Troubleshooting

### "unable to open database file"

The SQLite database path must be writable. In Docker, ensure the volume mount point exists:

```bash
touch serp_history.db  # create empty file before first run
```

### Templates fail with "unhashable type: 'dict'"

This means `TemplateResponse` is called with the wrong argument order. The correct signature is:

```python
templates.TemplateResponse(request, "template.html", { ... })
```

`request` is the **first positional argument** in Starlette 1.0+.

### Scheduler not running

The scheduler only starts if `SERPAPI_KEY` is set AND keywords exist. Check both conditions on the **Settings** page.

### No rankings showing

- Verify your SerpAPI key is valid and has remaining quota
- Check the API response: run `curl -s "https://serpapi.com/search?q=test&api_key=$SERPAPI_KEY" | python -m json.tool`
- Ensure you've added keywords and triggered a fetch (Track All Now or wait for the scheduler)

### CLI shows "Install sentence-transformers"

The `--cluster` flag requires `sentence-transformers` and `scikit-learn`. Install them:

```bash
pip install sentence-transformers scikit-learn
```

These are included in `requirements.txt` but can be omitted if you don't need intent clustering.

### Database file grows large

Each snapshot stores the full SerpAPI JSON response. For long-running deployments, consider:
- Setting up periodic cleanup of old snapshots (e.g., keep only the last 30 days)
- Or running `VACUUM` on the SQLite database periodically
