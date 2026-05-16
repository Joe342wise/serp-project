import os
import json
import time
import requests

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
SERPAPI_BASE = "https://serpapi.com/search"


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
            "domain": r.get("domain") or (
                r.get("link", "").split("/")[2] if r.get("link") else ""
            ),
            "snippet": r.get("snippet"),
            "is_ai_overview": 0,
        })
    return rows


def extract_ai_overview(data, keyword):
    ao = data.get("ai_overview") or {}
    if not ao:
        return None
    snippet = ao.get("snippet") or ao.get("content") or json.dumps(ao)[:500]
    link = ""
    if isinstance(ao, dict):
        link = ao.get("link") or ""
    return {
        "position": 0,
        "url": link,
        "title": "AI Overview",
        "domain": "google.ai.overview",
        "snippet": snippet[:500],
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


def extract_kg(data, keyword):
    kg = data.get("knowledge_graph") or {}
    if kg:
        return {
            "title": kg.get("title") or kg.get("name", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
        }
    return None
