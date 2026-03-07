"""Shared helper utilities for the hyebot scraping subsystem.

The old ``scraping_service`` module contained two almost identical loops for
news/history scrapers, as well as helper functions for database persistence
and RSS date parsing.  Those helpers are now centralized here so that other
modules can depend on them without duplication.

This module also contains a thin wrapper around text normalization from the
*armenian-corpus-core* package; by depending on that repository we can
reuse canonical cleaning routines and eventually share vocabulary/lexicon
contracts between multiple projects.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.source import Source, Article
from app.scrapers.base_scraper import ScrapedArticle

# import normalization helpers from the core package; the dependency is added
to requirements.txt so pip installs a local editable copy
try:
    from armenian_corpus_core.core_contracts import normalize_text_for_hash
except ImportError:  # pragma: no cover - optional during early development
    def normalize_text_for_hash(text: str) -> str:  # type: ignore
        # fall back to a noop if core isn't available
        return text.strip()

# ---------------------------------------------------------------------------
# optional corpus-core integration (centralized news database)
# ---------------------------------------------------------------------------
try:
    from armenian_corpus_core.data_sources import get_news_documents, get_news_sources
except Exception:  # import error or NotImplementedError
    def get_news_documents():  # type: ignore
        raise NotImplementedError("No core news document source configured")
    def get_news_sources():  # type: ignore
        return []


def load_articles_from_core() -> dict[str, list[ScrapedArticle]]:
    """Load any pre‑aggregated news articles provided by the core package.

    Returns a mapping from ``source_family`` (often the original news source
    name) to a list of :class:`ScrapedArticle` objects constructed from the
    underlying ``DocumentRecord`` instances.  The caller (usually
    :func:`run_news_scrape`) can then persist them just as if they were fetched
    by a real scraper.

    When the core package does not provide any documents the result will be
    an empty dict.
    """
    mapping: dict[str, list[ScrapedArticle]] = {}
    try:
        docs = get_news_documents()
    except NotImplementedError:
        return mapping

    for rec in docs:
        sf = getattr(rec, "source_family", "core") or "core"
        art = ScrapedArticle(
            title=rec.title or "",
            url=rec.source_url or "",
            content=rec.text or "",
            summary="",
            published_at=None,
            category="news",
            tags=[],
        )
        mapping.setdefault(sf, []).append(art)
    return mapping


def get_core_news_sources() -> list[dict]:
    """Return metadata about news sources stored in the core package.

    Each item is a dict with at least ``name`` and ``url`` fields.  This
    mirrors :func:`get_news_sources` from the core package but normalises the
    result to a plain list so callers don't have to handle import failures.
    """
    try:
        return list(get_news_sources())
    except Exception:
        return []

logger = logging.getLogger(__name__)


def parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse an RFC-2822 / RSS date string into a timezone-aware datetime.

    Historically identical copies of this function lived in
    ``armenian_news`` and ``scraping_service``; consolidate it here so that
    new scrapers can easily import it.
    """
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime

        return parsedate_to_datetime(date_str)
    except Exception:  # broad because feed dates vary wildly
        return None


# ---------------------------------------------------------------------------
# database helpers
# ---------------------------------------------------------------------------


def get_or_create_source(db: Session, scraper) -> Source:
    """Return the ``Source`` row for a scraper, creating it if missing.

    The hyebot service layer called this repeatedly so we made it public for
    reuse by other modules (e.g. tests).
    """
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


def persist_articles(db: Session, source: Source, articles: Iterable[ScrapedArticle]) -> int:
    """Insert *new* articles into the database, skipping duplicates.

    The original implementation lived in ``scraping_service`` and was
    duplicated in a unit test; tests now import this helper as well.
    """
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

    source.last_scraped_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    source.article_count = (source.article_count or 0) + new_count  # type: ignore[assignment]
    db.commit()
    return new_count


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def run_scrape_set(db: Session, scraper_classes: Iterable[type]) -> dict[str, dict]:
    """Generic loop that runs a batch of scraper classes and persists results.

    ``scraping_service`` previously had two almost-identical methods for news
    and history; we now call this helper from there.  The return value mirrors
    the old behaviour (source name \u2192 fetched/new counts or error).
    """
    results: dict[str, dict] = {}
    for ScraperClass in scraper_classes:
        scraper = ScraperClass()
        try:
            source = get_or_create_source(db, scraper)
            articles = scraper.scrape()
            new = persist_articles(db, source, articles)
            results[scraper.SOURCE_NAME] = {"fetched": len(articles), "new": new}
            logger.info(
                f"Scrape [{scraper.SOURCE_NAME}]: fetched={len(articles)}, new={new}"
            )
        except Exception as exc:  # keep old behaviour of catching everything
            logger.error(f"Scrape [{scraper.SOURCE_NAME}] failed: {exc}", exc_info=True)
            results[scraper.SOURCE_NAME] = {"error": str(exc)}
    return results
