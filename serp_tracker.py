#!/usr/bin/env python3
"""SERP Rank Tracker + Movement Analyzer (SerpAPI PoC)"""

import json
import sqlite3
import os
import time
import argparse
from datetime import datetime, timezone
from collections import defaultdict

import requests

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_BASE = "https://serpapi.com/search"

DB_PATH = "serp_history.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            ts TEXT NOT NULL,
            raw JSON NOT NULL
        )
    """)
    conn.execute("""
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
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS paa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            keyword TEXT NOT NULL,
            question TEXT,
            snippet TEXT,
            link TEXT,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
        )
    """)
    conn.commit()
    return conn

def fetch_serp(keyword, location="United States", device="desktop"):
    params = {
        "q": keyword,
        "location": location,
        "device": device,
        "api_key": SERPAPI_KEY,
        "engine": "google",
        "num": 20,
    }
    resp = requests.get(SERPAPI_BASE, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def extract_rankings(data, keyword):
    rows = []
    for r in data.get("organic_results", []):
        rows.append({
            "position": r.get("position"),
            "url": r.get("link"),
            "title": r.get("title"),
            "domain": r.get("domain") or (r.get("link", "").split("/")[2] if r.get("link") else ""),
            "snippet": r.get("snippet"),
            "is_ai_overview": 0,
        })
    return rows

def extract_ai_overview(data, keyword):
    ao = data.get("ai_overview") or {}
    if not ao:
        return None
    return {
        "position": 0,
        "url": ao.get("link") or "",
        "title": "AI Overview",
        "domain": "google.ai.overview",
        "snippet": ao.get("snippet") or ao.get("content") or json.dumps(ao)[:500],
        "is_ai_overview": 1,
    }

def extract_paa(data, keyword):
    items = []
    for r in data.get("related_questions", []):
        items.append({
            "question": r.get("question"),
            "snippet": r.get("snippet"),
            "link": r.get("link"),
        })
    return items

def store_snapshot(conn, keyword, data):
    ts = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO snapshots (keyword, ts, raw) VALUES (?, ?, ?)",
        (keyword, ts, json.dumps(data)),
    )
    sid = cur.lastrowid

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

    conn.commit()
    return sid

def detect_volatility(conn, keyword, lookback=2):
    cur = conn.execute("""
        SELECT r.position, r.domain, r.url, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE r.keyword = ? AND r.is_ai_overview = 0
        ORDER BY s.ts DESC
    """, (keyword,))
    rows = cur.fetchall()

    snapshots = defaultdict(list)
    for pos, domain, url, ts in rows:
        snapshots[ts].append((pos, domain, url))

    sorted_ts = sorted(snapshots.keys(), reverse=True)
    if len(sorted_ts) < lookback + 1:
        return None

    latest = snapshots[sorted_ts[0]]
    prev = snapshots[sorted_ts[1]]

    latest_by_domain = {d: p for p, d, u in latest}
    prev_by_domain = {d: p for p, d, u in prev}

    changes = []
    all_domains = set(latest_by_domain) | set(prev_by_domain)
    for d in all_domains:
        lp = latest_by_domain.get(d)
        pp = prev_by_domain.get(d)
        if lp is None:
            changes.append((d, pp, "dropped"))
        elif pp is None:
            changes.append((d, lp, "new"))
        elif abs(lp - pp) >= 3:
            changes.append((d, f"{pp}->{lp}", "moved"))

    return {
        "keyword": keyword,
        "latest_ts": sorted_ts[0],
        "prev_ts": sorted_ts[1],
        "changes": changes,
    }

def detect_cannibalization(conn, lookback_days=7):
    cutoff = datetime.now(timezone.utc).isoformat()
    cur = conn.execute("""
        SELECT r.keyword, r.url, r.position, r.domain, s.ts
        FROM rankings r
        JOIN snapshots s ON r.snapshot_id = s.id
        WHERE s.ts >= date('now', '-? days')
          AND r.is_ai_overview = 0
        ORDER BY r.keyword, r.url, s.ts DESC
    """, (lookback_days,))
    rows = cur.fetchall()

    cannibals = []
    kw_groups = defaultdict(lambda: defaultdict(list))
    for kw, url, pos, domain, ts in rows:
        kw_groups[kw][url].append((pos, ts))

    for kw, urls in kw_groups.items():
        if len(urls) < 2:
            continue
        positions = [(url, min(vals)[0]) for url, vals in urls.items()]
        positions.sort(key=lambda x: x[1])
        if positions[0][1] < 10 and len(positions) > 1:
            cannibals.append({"keyword": kw, "pages": positions})

    return cannibals

def print_report(keyword, data):
    ai = extract_ai_overview(data, keyword)
    rankings = extract_rankings(data, keyword)

    print(f"\n{'='*60}")
    print(f"KEYWORD: {keyword}")
    print(f"{'='*60}")

    if ai:
        print(f"\n  [AI OVERVIEW] {ai['snippet'][:120]}...")

    print(f"\n  Top 5 Rankings:")
    for r in rankings[:5]:
        marker = " [AI]" if r["is_ai_overview"] else ""
        print(f"    {r['position']:>2}. {r['domain']:<30} {r['title'][:50]}{marker}")

    paas = extract_paa(data, keyword)
    if paas:
        print(f"\n  People Also Ask ({len(paas)}):")
        for q in paas[:3]:
            print(f"    \u2022 {q['question'][:70]}")

    kg = data.get("knowledge_graph", {})
    if kg:
        name = kg.get("title") or kg.get("name", "")
        print(f"\n  Knowledge Graph: {name}")

def intent_cluster(conn, model_name="all-MiniLM-L6-v2"):
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
    except ImportError:
        print("Install sentence-transformers for intent clustering: pip install sentence-transformers")
        return

    cur = conn.execute("""
        SELECT DISTINCT r.keyword,
                        GROUP_CONCAT(r.snippet, ' ') as snippets
        FROM rankings r
        WHERE r.snippet IS NOT NULL
        GROUP BY r.keyword
    """)
    rows = cur.fetchall()
    if not rows:
        return

    kw_list = [r[0] for r in rows]
    texts = [r[1][:512] for r in rows]
    emb = model.encode(texts)
    from sklearn.cluster import KMeans
    n = min(5, len(kw_list))
    clusters = KMeans(n_clusters=n, random_state=0).fit_predict(emb)
    groups = defaultdict(list)
    for kw, c in zip(kw_list, clusters):
        groups[int(c)].append(kw)
    print(f"\n{'='*60}")
    print("INTENT CLUSTERS (via embeddings)")
    print(f"{'='*60}")
    for cid in sorted(groups):
        print(f"\n  Cluster {cid}:")
        for kw in groups[cid]:
            print(f"    \u2022 {kw}")


def main():
    parser = argparse.ArgumentParser(description="SERP Rank Tracker")
    parser.add_argument("keywords", nargs="+", help="Keywords to track")
    parser.add_argument("--location", default="United States")
    parser.add_argument("--device", default="desktop")
    parser.add_argument("--volatility", type=int, default=0, help="Check volatility (lookback snapshots)")
    parser.add_argument("--cannibalization", action="store_true", help="Detect keyword cannibalization")
    parser.add_argument("--cluster", action="store_true", help="Cluster keywords by intent (requires sentence-transformers)")
    args = parser.parse_args()

    conn = init_db()

    for kw in args.keywords:
        print(f"\nFetching SERP for: {kw}")
        try:
            data = fetch_serp(kw, args.location, args.device)
        except requests.RequestException as e:
            print(f"  ERROR: {e}")
            continue

        sid = store_snapshot(conn, kw, data)
        print(f"  Stored snapshot #{sid}")
        print_report(kw, data)
        time.sleep(0.5)

    if args.volatility:
        print(f"\n{'='*60}")
        print("SERP VOLATILITY ALERTS")
        print(f"{'='*60}")
        for kw in args.keywords:
            v = detect_volatility(conn, kw, lookback=args.volatility)
            if v and v["changes"]:
                print(f"\n  {kw}:")
                for domain, detail, kind in v["changes"][:5]:
                    print(f"    {domain:<30} {kind} ({detail})")

    if args.cannibalization:
        cannibals = detect_cannibalization(conn)
        if cannibals:
            print(f"\n{'='*60}")
            print("KEYWORD CANNIBALIZATION WARNINGS")
            print(f"{'='*60}")
            for c in cannibals:
                print(f"\n  {c['keyword']}:")
                for url, pos in c["pages"]:
                    print(f"    pos {pos:<3} {url}")

    if args.cluster:
        intent_cluster(conn)

    conn.close()


if __name__ == "__main__":
    main()
