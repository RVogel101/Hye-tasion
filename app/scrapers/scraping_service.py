"""
Service layer that orchestrates scraping runs, deduplicates content,
and persists articles to the database.
"""
import json
import logging
from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.models.source import Source, Article
from app.scrapers.armenian_news import ALL_NEWS_SCRAPERS
from app.scrapers.history_journals import ALL_HISTORY_SCRAPERS
from app.scrapers.base_scraper import ScrapedArticle

logger = logging.getLogger(__name__)


def _get_or_create_source(db: Session, scraper) -> Source:
    """Fetch the DB Source row for a scraper, creating it if absent."""
    source = db.query(Source).filter_by(name=scraper.SOURCE_NAME).first()
    if not source:
        source = Source(
            name=scraper.SOURCE_NAME,
            url=scraper.BASE_URL,
            rss_url=getattr(scraper, "RSS_URL", None) or getattr(scraper, "rss_url", None),
            source_type=getattr(scraper, "source_type", "rss"),
            category=getattr(scraper, "category", "news"),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source


def _persist_articles(db: Session, source: Source, articles: list[ScrapedArticle]) -> int:
    """Insert new articles (skip already-known URLs). Returns count of new inserts."""
    new_count = 0
    for art in articles:
        if not art.url or not art.title:
            continue
        exists = db.query(Article).filter_by(url=art.url).first()
        if exists:
            continue
        db_article = Article(
            source_id=source.id,
            title=art.title[:499],
            url=art.url[:999],
            content=art.content[:50000] if art.content else None,
            summary=art.summary[:2000] if art.summary else None,
            published_at=art.published_at,
            category=art.category,
            tags=json.dumps(art.tags),
        )
        db.add(db_article)
        new_count += 1

    source.last_scraped_at = datetime.now(UTC)
    source.article_count = (source.article_count or 0) + new_count
    db.commit()
    return new_count


def run_news_scrape(db: Session) -> dict:
    """Run all Armenian news scrapers and persist results."""
    results = {}
    for ScraperClass in ALL_NEWS_SCRAPERS:
        scraper = ScraperClass()
        try:
            source = _get_or_create_source(db, scraper)
            articles = scraper.scrape()
            new = _persist_articles(db, source, articles)
            results[scraper.SOURCE_NAME] = {"fetched": len(articles), "new": new}
            logger.info(f"News scrape [{scraper.SOURCE_NAME}]: fetched={len(articles)}, new={new}")
        except Exception as exc:
            logger.error(f"News scrape [{scraper.SOURCE_NAME}] failed: {exc}", exc_info=True)
            results[scraper.SOURCE_NAME] = {"error": str(exc)}
    return results


def run_history_scrape(db: Session) -> dict:
    """Run all history/academic scrapers and persist results."""
    results = {}
    for ScraperClass in ALL_HISTORY_SCRAPERS:
        scraper = ScraperClass()
        try:
            source = _get_or_create_source(db, scraper)
            articles = scraper.scrape()
            new = _persist_articles(db, source, articles)
            results[scraper.SOURCE_NAME] = {"fetched": len(articles), "new": new}
            logger.info(f"History scrape [{scraper.SOURCE_NAME}]: fetched={len(articles)}, new={new}")
        except Exception as exc:
            logger.error(f"History scrape [{scraper.SOURCE_NAME}] failed: {exc}", exc_info=True)
            results[scraper.SOURCE_NAME] = {"error": str(exc)}
    return results


def run_all_scrapes(db: Session) -> dict:
    """Run both news and history scrapes in a single call."""
    return {
        "news": run_news_scrape(db),
        "history": run_history_scrape(db),
    }
