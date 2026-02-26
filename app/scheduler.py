"""
Scheduler — runs periodic scraping, Reddit collection, analysis, and
performance-metric refreshes on configurable intervals.
"""
import logging
import os

import yaml
from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.scrapers.scraping_service import run_all_scrapes
from app.analysis.reddit_collector import collect_reddit_data
from app.analysis.engagement_analyzer import analyze_engagement_patterns
from app.ab_testing.ab_framework import refresh_variant_metrics, refresh_post_performance
from app.models.ab_test import ABTest, PostPerformance

logger = logging.getLogger(__name__)

# Load interval from config
with open("config.yaml", "r", encoding="utf-8") as f:
    _cfg = yaml.safe_load(f)

SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_MINUTES", "60"))
REDDIT_COLLECT_INTERVAL = 120   # 2 hours
ANALYSIS_INTERVAL = 360         # 6 hours
METRICS_INTERVAL = 30           # 30 minutes


def _scrape_job():
    logger.info("[Scheduler] Starting scrape job…")
    db = SessionLocal()
    try:
        run_all_scrapes(db)
    except Exception as exc:
        logger.error(f"[Scheduler] Scrape job failed: {exc}", exc_info=True)
    finally:
        db.close()


def _reddit_collect_job():
    logger.info("[Scheduler] Starting Reddit collection job…")
    db = SessionLocal()
    try:
        collect_reddit_data(db)
    except Exception as exc:
        logger.error(f"[Scheduler] Reddit collect job failed: {exc}", exc_info=True)
    finally:
        db.close()


def _analysis_job():
    logger.info("[Scheduler] Starting engagement analysis job…")
    db = SessionLocal()
    try:
        analyze_engagement_patterns(db)
    except Exception as exc:
        logger.error(f"[Scheduler] Analysis job failed: {exc}", exc_info=True)
    finally:
        db.close()


def _metrics_job():
    logger.info("[Scheduler] Refreshing A/B and post metrics…")
    db = SessionLocal()
    try:
        active_tests = db.query(ABTest).filter_by(is_active=True).all()
        for test in active_tests:
            refresh_variant_metrics(db, test)
        performances = db.query(PostPerformance).filter(
            PostPerformance.final_score.is_(None)
        ).all()
        for perf in performances:
            # reddit_post_id may be a Column object; coerce to str
            refresh_post_performance(db, str(perf.reddit_post_id))
    except Exception as exc:
        logger.error(f"[Scheduler] Metrics job failed: {exc}", exc_info=True)
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(_scrape_job, "interval", minutes=SCRAPE_INTERVAL, id="scrape",
                      misfire_grace_time=60)
    scheduler.add_job(_reddit_collect_job, "interval", minutes=REDDIT_COLLECT_INTERVAL,
                      id="reddit_collect", misfire_grace_time=120)
    scheduler.add_job(_analysis_job, "interval", minutes=ANALYSIS_INTERVAL, id="analysis",
                      misfire_grace_time=300)
    scheduler.add_job(_metrics_job, "interval", minutes=METRICS_INTERVAL, id="metrics",
                      misfire_grace_time=30)
    return scheduler
