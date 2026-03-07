"""
Service layer that orchestrates scraping runs, deduplicates content,
and persists articles to the database.
"""
import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session  # type: ignore[reportMissingModuleSource, reportMissingImports]

from app.scrapers.utils import (
    run_scrape_set,
    load_articles_from_core,
    get_or_create_source,
    persist_articles,
)
from app.scrapers.armenian_news import ALL_NEWS_SCRAPERS
from app.scrapers.history_journals import ALL_HISTORY_SCRAPERS

# ``Source``/``Article``/``ScrapedArticle`` used to be referenced here; the
# helper module now imports them as needed, so we don't need them directly.
logger = logging.getLogger(__name__)
# helpers were moved to app/scrapers/utils.py; imports above replace them



def run_news_scrape(db: Session) -> dict:
    """Run all Armenian news scrapers and persist results.

    If the ``USE_CORE_NEWS`` environment variable is set truthy, we bypass the
    usual web scrapers and instead load pre‑aggregated articles from the
    ``armenian_corpus_core`` package.  That package may itself source data from
    a central database or export, giving hyebot an alternate ingestion path.
    """
    use_core = os.getenv("USE_CORE_NEWS", "").lower() in ("1", "true", "yes")
    if use_core:
        results: dict[str, dict] = {}
        articles_by_source = load_articles_from_core()  # type: ignore[name-defined]
        for src_name, articles in articles_by_source.items():
            proxy = type("CoreSource", (), {"SOURCE_NAME": src_name, "BASE_URL": ""})
            source = get_or_create_source(db, proxy)
            new = persist_articles(db, source, articles)
            results[src_name] = {"fetched": len(articles), "new": new}
            logger.info(f"Core news load [{src_name}]: fetched={len(articles)}, new={new}")
        return results
    else:
        return run_scrape_set(db, ALL_NEWS_SCRAPERS)


def run_history_scrape(db: Session) -> dict:
    """Run all history/academic scrapers and persist results."""
    return run_scrape_set(db, ALL_HISTORY_SCRAPERS)


# ``run_all_scrapes`` is no longer needed, but keep it for backwards
# compatibility with code/tests that may import it.

def run_all_scrapes(db: Session) -> dict:
    """Run both news and history scrapes in a single call.

    Just a thin wrapper around the new helpers.
    """
    return {
        "news": run_news_scrape(db),
        "history": run_history_scrape(db),
    }
