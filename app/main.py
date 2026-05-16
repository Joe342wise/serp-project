import os
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

from . import database as db
from . import serpapi
from .routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def track_all_job():
    keywords = db.get_keywords()
    logger.info("Scheduled tracking %d keywords", len(keywords))
    for kw in keywords:
        try:
            data = serpapi.fetch_serp(
                kw["keyword"], kw.get("location", "United States"), kw.get("device", "desktop")
            )
            db.store_snapshot(kw["keyword"], data)
            logger.info("Tracked: %s", kw["keyword"])
        except Exception as e:
            logger.error("Failed %s: %s", kw["keyword"], e)
        time.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if serpapi.SERPAPI_KEY and db.get_keywords():
        interval = int(os.environ.get("TRACK_INTERVAL_HOURS", "24"))
        scheduler.add_job(track_all_job, "interval", hours=interval, id="track_all")
        scheduler.start()
        logger.info("Scheduler started (every %d hours)", interval)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="SERP Tracker", lifespan=lifespan)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(router)
