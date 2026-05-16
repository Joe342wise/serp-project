import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "serp_history.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            location TEXT DEFAULT 'United States',
            device TEXT DEFAULT 'desktop',
            active INTEGER DEFAULT 1,
            created TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            ts TEXT NOT NULL,
            raw JSON NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER,
            url TEXT,
            title TEXT,
            domain TEXT,
            snippet TEXT,
            is_ai_overview INTEGER DEFAULT 0,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
        );

        CREATE TABLE IF NOT EXISTS paa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            question TEXT,
            snippet TEXT,
            link TEXT,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
        );

        CREATE TABLE IF NOT EXISTS knowledge_graphs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            kg JSON,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            ts TEXT DEFAULT (datetime('now')),
            seen INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    return conn


def add_keyword(keyword, location="United States", device="desktop"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO keywords (keyword, location, device) VALUES (?, ?, ?)",
            (keyword, location, device),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_keyword(keyword):
    conn = get_conn()
    conn.execute("DELETE FROM keywords WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM snapshots WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM rankings WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM paa WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM knowledge_graphs WHERE keyword = ?", (keyword,))
    conn.execute("DELETE FROM alerts WHERE keyword = ?", (keyword,))
    conn.commit()
    conn.close()


def get_keywords():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM keywords WHERE active = 1 ORDER BY created DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_keyword(keyword):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM keywords WHERE keyword = ?", (keyword,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def store_snapshot(keyword, data):
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO snapshots (keyword, ts, raw) VALUES (?, ?, ?)",
        (keyword, ts, json.dumps(data)),
    )
    sid = cur.lastrowid

    from .serpapi import extract_rankings, extract_ai_overview, extract_paa, extract_kg

    ai = extract_ai_overview(data, keyword)
    rankings = extract_rankings(data, keyword)
    if ai:
        rankings.insert(0, ai)

    for r in rankings:
        conn.execute(
            "INSERT INTO rankings (snapshot_id, keyword, position, url, title, domain, snippet, is_ai_overview) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, keyword, r["position"], r["url"], r["title"], r["domain"], r["snippet"], r["is_ai_overview"]),
        )

    for q in extract_paa(data, keyword):
        conn.execute(
            "INSERT INTO paa (snapshot_id, keyword, question, snippet, link) VALUES (?, ?, ?, ?, ?)",
            (sid, keyword, q["question"], q["snippet"], q["link"]),
        )

    kg = extract_kg(data, keyword)
    if kg:
        conn.execute(
            "INSERT INTO knowledge_graphs (snapshot_id, keyword, kg) VALUES (?, ?, ?)",
            (sid, keyword, json.dumps(kg)),
        )

    conn.commit()
    conn.close()
    return sid


def get_latest_rankings(keyword, limit=20):
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.*, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE r.keyword = ?
          AND s.id = (SELECT MAX(id) FROM snapshots WHERE keyword = ?)
        ORDER BY r.position
        LIMIT ?
    """, (keyword, keyword, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rank_history(keyword, days=30):
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.domain, r.position, r.url, r.is_ai_overview, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE r.keyword = ?
        ORDER BY s.ts
    """, (keyword,)).fetchall()
    conn.close()

    history = defaultdict(list)
    for r in rows:
        d = dict(r)
        history[d["ts"]].append(d)

    sorted_ts = sorted(history.keys())[-days:]
    result = []
    for ts in sorted_ts:
        entries = history[ts]
        top10 = [e for e in entries if e["position"] is not None and 1 <= e["position"] <= 10 and not e["is_ai_overview"]]
        result.append({
            "ts": ts,
            "top10": top10,
        })
    return result


def get_paa_for_keyword(keyword):
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, s.ts
        FROM paa p
        JOIN snapshots s ON p.snapshot_id = s.id
        WHERE p.keyword = ?
        ORDER BY s.ts DESC
        LIMIT 50
    """, (keyword,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_paa(limit=100):
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, s.ts
        FROM paa p
        JOIN snapshots s ON p.snapshot_id = s.id
        ORDER BY s.ts DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def detect_volatility(keyword, lookback=2):
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.position, r.domain, r.url, r.is_ai_overview, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE r.keyword = ?
        ORDER BY s.ts DESC
    """, (keyword,)).fetchall()
    conn.close()

    snapshots = defaultdict(list)
    for r in rows:
        d = dict(r)
        if d["is_ai_overview"]:
            continue
        snapshots[d["ts"]].append((d["position"], d["domain"], d["url"]))

    sorted_ts = sorted(snapshots.keys(), reverse=True)
    if len(sorted_ts) < lookback + 1:
        return None

    latest = snapshots[sorted_ts[0]]
    prev = snapshots[sorted_ts[1]]

    latest_by_domain = {d: p for p, d, u in latest}
    prev_by_domain = {d: p for p, d, u in prev}

    changes = []
    all_domains = set(latest_by_domain) | set(prev_by_domain)
    for d in sorted(all_domains):
        lp = latest_by_domain.get(d)
        pp = prev_by_domain.get(d)
        if lp is None:
            changes.append({"domain": d, "from": pp, "to": None, "type": "dropped"})
        elif pp is None:
            changes.append({"domain": d, "from": None, "to": lp, "type": "new"})
        elif abs(lp - pp) >= 3:
            changes.append({"domain": d, "from": pp, "to": lp, "type": "moved"})
        elif lp != pp:
            changes.append({"domain": d, "from": pp, "to": lp, "type": "moved"})

    return {
        "keyword": keyword,
        "latest_ts": sorted_ts[0],
        "prev_ts": sorted_ts[1],
        "changes": changes,
    }


def get_all_alerts(limit=50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_alert(keyword, alert_type, message):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alerts (keyword, alert_type, message) VALUES (?, ?, ?)",
        (keyword, alert_type, message),
    )
    conn.commit()
    conn.close()


def detect_cannibalization(lookback_days=7):
    conn = get_conn()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    rows = conn.execute("""
        SELECT r.keyword, r.url, r.position, r.domain, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE s.ts >= ? AND r.is_ai_overview = 0
        ORDER BY r.keyword, r.url, s.ts DESC
    """, (cutoff,)).fetchall()
    conn.close()

    kw_groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        d = dict(r)
        kw_groups[d["keyword"]][d["url"]].append((d["position"], d["ts"]))

    cannibals = []
    for kw, urls in kw_groups.items():
        if len(urls) < 2:
            continue
        positions = [(url, min(vals)[0]) for url, vals in urls.items()]
        positions.sort(key=lambda x: x[1])
        best = positions[0][1]
        if best < 10:
            cannibals.append({"keyword": kw, "pages": positions})

    return cannibals


def get_competitor_summary():
    conn = get_conn()
    rows = conn.execute("""
        SELECT r.domain, r.keyword, r.position, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE s.id IN (SELECT MAX(id) FROM snapshots GROUP BY keyword)
          AND r.is_ai_overview = 0
          AND r.position IS NOT NULL
        ORDER BY r.domain, r.position
    """).fetchall()
    conn.close()

    domains = defaultdict(list)
    for r in rows:
        d = dict(r)
        if d["domain"]:
            domains[d["domain"]].append({
                "keyword": d["keyword"],
                "position": d["position"],
            })

    summary = []
    for domain, kws in sorted(domains.items(), key=lambda x: len(x[1]), reverse=True):
        top5 = sum(1 for k in kws if k["position"] <= 5)
        top10 = sum(1 for k in kws if k["position"] <= 10)
        summary.append({
            "domain": domain,
            "keyword_count": len(kws),
            "top5": top5,
            "top10": top10,
            "keywords": sorted(kws, key=lambda x: x["position"])[:20],
        })
    return summary


def get_dashboard_stats():
    conn = get_conn()
    kw_count = conn.execute("SELECT COUNT(*) FROM keywords WHERE active=1").fetchone()[0]

    latest = {}
    rows = conn.execute("""
        SELECT keyword, MAX(id) as mid FROM snapshots GROUP BY keyword
    """).fetchall()
    for r in rows:
        latest[r["keyword"]] = r["mid"]

    total_rankings = 0
    ai_count = 0
    for kid in latest.values():
        r = conn.execute(
            "SELECT COUNT(*) FROM rankings WHERE snapshot_id=? AND is_ai_overview=1",
            (kid,),
        ).fetchone()[0]
        ai_count += r
        r2 = conn.execute(
            "SELECT COUNT(*) FROM rankings WHERE snapshot_id=?",
            (kid,),
        ).fetchone()[0]
        total_rankings += r2

    alert_count = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE seen=0"
    ).fetchone()[0]

    snapshot_count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

    conn.close()

    return {
        "keyword_count": kw_count,
        "total_rankings": total_rankings,
        "ai_overview_count": ai_count,
        "alert_count": alert_count,
        "snapshot_count": snapshot_count,
    }


def get_dashboard_keywords():
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT r.keyword,
               FIRST_VALUE(r.position) OVER (PARTITION BY r.keyword ORDER BY s.ts DESC) as pos,
               FIRST_VALUE(r.domain) OVER (PARTITION BY r.keyword ORDER BY s.ts DESC) as domain
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE r.is_ai_overview = 0
          AND r.position BETWEEN 1 AND 100
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
