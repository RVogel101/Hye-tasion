"""Unit tests for the newly extracted helper modules.

These exercises ensure the refactor didn't change behaviour and provide
coverage for the shared routines moving forward.
"""
from datetime import datetime, timezone

import pytest

from app.scrapers import utils as scraper_utils
from app.analysis import utils as analysis_utils


def test_parse_rss_date_valid():
    dt = scraper_utils.parse_rss_date("Wed, 02 Oct 2002 08:00:00 GMT")
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


def test_parse_rss_date_invalid():
    assert scraper_utils.parse_rss_date("not a date") is None
    assert scraper_utils.parse_rss_date("") is None


def test_simple_sentiment_rules():
    # rule-based fallback should handle known words
    assert analysis_utils.simple_sentiment("great victory peace") > 0
    assert analysis_utils.simple_sentiment("war conflict death") < 0


def test_title_structure_various():
    assert analysis_utils.title_structure("What happened?") == "question"
    assert analysis_utils.title_structure("1 thing you must know") == "starts_with_number"
    assert analysis_utils.title_structure("Breaking: update on situation") == "breaking_news"
    assert analysis_utils.title_structure("Topic: detail here") == "topic_colon_detail"
    assert analysis_utils.title_structure("Why is this important") == "wh_question"
    assert analysis_utils.title_structure("Short") == "short_punchy"
    assert analysis_utils.title_structure("".join(["word "] * 25)) == "long_descriptive"
    assert analysis_utils.title_structure("a normal length title with words") == "standard"


def test_db_helpers(db, make_source):
    # verify get_or_create_source creates and reuses a source
    class DummyScraper:
        SOURCE_NAME = "Foo"
        BASE_URL = "https://foo.example"

    src1 = scraper_utils.get_or_create_source(db, DummyScraper)
    assert src1.name == "Foo"  # type: ignore[reportGeneralTypeIssues]
    # second call returns the same object
    src2 = scraper_utils.get_or_create_source(db, DummyScraper)
    assert src1.id == src2.id  # type: ignore[reportGeneralTypeIssues]

    # persist_articles should add new rows and skip duplicates
    from app.scrapers.base_scraper import ScrapedArticle
    dummy_article = ScrapedArticle(
        title="A", url="https://foo/a", published_at=datetime.now(timezone.utc),
        category="news", content="", summary="", tags=[]
    )
    count = scraper_utils.persist_articles(db, src1, [dummy_article, dummy_article])
    assert count == 1
    # database has exactly one Article row
    from app.models.source import Article
    articles = db.query(Article).filter_by(source_id=src1.id).all()
    assert len(articles) == 1


def test_load_from_core(monkeypatch, db):
    # create fake document records
    class FakeRec:
        def __init__(self, title, url, text, family):
            self.title = title
            self.source_url = url
            self.text = text
            self.source_family = family
    fake_docs = [
        FakeRec("A", "http://a", "text a", "Foo"),
        FakeRec("B", "http://b", "text b", "Foo"),
        FakeRec("C", "http://c", "text c", "Bar"),
    ]
    monkeypatch.setattr("app.scrapers.utils.get_news_documents", lambda: iter(fake_docs))

    # exercise helper directly
    from app.scrapers.utils import load_articles_from_core
    mapping = load_articles_from_core()
    assert set(mapping.keys()) == {"Foo", "Bar"}
    assert len(mapping["Foo"]) == 2
    assert mapping["Foo"][0].title == "A"

    # now run_news_scrape with environment var set
    import os
    os.environ["USE_CORE_NEWS"] = "true"
    from app.scrapers.scraping_service import run_news_scrape
    results = run_news_scrape(db)
    # should have two source families persisted
    assert "Foo" in results and "Bar" in results
    assert results["Foo"]["fetched"] == 2
    # cleanup env var
    del os.environ["USE_CORE_NEWS"]


def test_core_news_sources(monkeypatch):
    monkeypatch.setattr("app.scrapers.utils.get_news_sources", lambda: [{"name": "X", "url": "http://x"}])
    from app.scrapers.utils import get_core_news_sources
    assert get_core_news_sources()[0]["name"] == "X"
