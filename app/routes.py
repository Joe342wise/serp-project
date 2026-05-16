import json
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os

from . import database as db
from . import serpapi

router = APIRouter()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = db.get_dashboard_stats()
    keywords = db.get_keywords()
    alerts = db.get_all_alerts(limit=10)
    latest_rankings = {}
    for kw in keywords:
        rankings = db.get_latest_rankings(kw["keyword"], limit=5)
        if rankings:
            latest_rankings[kw["keyword"]] = rankings

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stats": stats,
            "keywords": keywords,
            "alerts": alerts,
            "latest_rankings": latest_rankings,
        },
    )


@router.get("/keyword/{keyword:path}", response_class=HTMLResponse)
async def keyword_detail(request: Request, keyword: str):
    kw = db.get_keyword(keyword)
    if not kw:
        return HTMLResponse("Keyword not found", status_code=404)

    rankings = db.get_latest_rankings(keyword, limit=20)
    history = db.get_rank_history(keyword, days=30)
    paa = db.get_paa_for_keyword(keyword)
    volatility = db.detect_volatility(keyword, lookback=2)

    return templates.TemplateResponse(
        request,
        "keyword_detail.html",
        {
            "keyword": kw,
            "rankings": rankings,
            "history": history,
            "paa": paa,
            "volatility": volatility,
        },
    )


@router.get("/competitors", response_class=HTMLResponse)
async def competitors(request: Request):
    data = db.get_competitor_summary()
    return templates.TemplateResponse(
        request,
        "competitors.html",
        {
            "competitors": data,
        },
    )


@router.get("/cannibalization", response_class=HTMLResponse)
async def cannibalization(request: Request):
    data = db.detect_cannibalization(lookback_days=14)
    return templates.TemplateResponse(
        request,
        "cannibalization.html",
        {
            "cannibals": data,
        },
    )


@router.get("/volatility", response_class=HTMLResponse)
async def volatility(request: Request):
    keywords = db.get_keywords()
    alerts = db.get_all_alerts(limit=100)
    volatilities = []
    for kw in keywords:
        v = db.detect_volatility(kw["keyword"], lookback=2)
        if v and v["changes"]:
            volatilities.append(v)
    return templates.TemplateResponse(
        request,
        "volatility.html",
        {
            "volatilities": volatilities,
            "alerts": alerts,
        },
    )


@router.get("/paa", response_class=HTMLResponse)
async def paa_page(request: Request):
    data = db.get_all_paa(limit=200)
    return templates.TemplateResponse(
        request,
        "paa.html",
        {
            "paas": data,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    keywords = db.get_keywords()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "keywords": keywords,
            "serpapi_key_set": bool(serpapi.SERPAPI_KEY),
        },
    )


@router.post("/settings/keywords/add")
async def add_keyword(
    keyword: str = Form(...),
    location: str = Form("United States"),
    device: str = Form("desktop"),
):
    db.add_keyword(keyword.strip(), location, device)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/settings/keywords/remove")
async def remove_keyword(keyword: str = Form(...)):
    db.remove_keyword(keyword.strip())
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/track/all")
async def track_all():
    keywords = db.get_keywords()
    results = []
    for kw in keywords:
        try:
            data = serpapi.fetch_serp(
                kw["keyword"],
                kw.get("location", "United States"),
                kw.get("device", "desktop"),
            )
            sid = db.store_snapshot(kw["keyword"], data)
            results.append(
                {"keyword": kw["keyword"], "snapshot_id": sid, "status": "ok"}
            )
        except Exception as e:
            results.append(
                {"keyword": kw["keyword"], "error": str(e), "status": "error"}
            )
        import time

        time.sleep(0.5)
    return JSONResponse({"results": results})


@router.post("/track/{keyword:path}")
async def track_keyword_now(keyword: str):
    kw = db.get_keyword(keyword)
    if not kw:
        return JSONResponse({"error": "Keyword not found"}, status_code=404)
    try:
        data = serpapi.fetch_serp(
            keyword, kw.get("location", "United States"), kw.get("device", "desktop")
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    sid = db.store_snapshot(keyword, data)
    return JSONResponse({"snapshot_id": sid, "status": "ok"})


@router.get("/api/keyword/{keyword:path}/history")
async def api_keyword_history(keyword: str, days: int = 30):
    history = db.get_rank_history(keyword, days=days)
    return JSONResponse(history)


@router.get("/api/stats")
async def api_stats():
    return JSONResponse(db.get_dashboard_stats())
