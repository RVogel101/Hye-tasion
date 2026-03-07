"""
Shared test fixtures — in-memory SQLite database, FastAPI test client, and
factory helpers for common model objects.
"""
import os
import pytest

# Force test configuration BEFORE any app imports
os.environ["DATABASE_URL"] = "sqlite:///file::memory:?cache=shared"
os.environ["API_KEY"] = "test-secret-key"
os.environ["REDDIT_CLIENT_ID"] = "fake"
os.environ["REDDIT_CLIENT_SECRET"] = "fake"
os.environ["REDDIT_USERNAME"] = "fake"
os.environ["REDDIT_PASSWORD"] = "fake"

from sqlalchemy import create_engine, StaticPool  # type: ignore[reportMissingModuleSource, reportMissingImports]
from sqlalchemy.orm import sessionmaker  # type: ignore[reportMissingModuleSource, reportMissingImports]

from app.database import Base, get_db
from app import app as fastapi_app


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)  # type: ignore[reportInvalidType]
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine, db):
    """FastAPI TestClient wired to use the test database session."""
    from fastapi.testclient import TestClient  # type: ignore[reportMissingModuleSource]

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Model factory helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def make_source(db):
    from app.models.source import Source  # type: ignore[reportMissingModuleSource]

    def _make(name="Test Source", url="https://example.com", category="news", **kw):
        s = Source(name=name, url=url, category=category, **kw)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s
    return _make


@pytest.fixture()
def make_article(db, make_source):
    from app.models.source import Article  # type: ignore[reportMissingModuleSource]

    _counter = [0]

    def _make(source=None, title="Test Article", url=None, category="news", **kw):
        _counter[0] += 1
        if source is None:
            source = make_source(name=f"Source-{_counter[0]}")
        art = Article(
            source_id=source.id,
            title=title,
            url=url or f"https://example.com/article-{_counter[0]}",
            category=category,
            **kw,
        )
        db.add(art)
        db.commit()
        db.refresh(art)
        return art
    return _make


@pytest.fixture()
def make_post_idea(db, make_article):
    from app.models.post import PostIdea  # type: ignore[reportMissingModuleSource]

    _counter = [0]

    def _make(title="Test Post Idea", subreddit="armenia", article=None, **kw):
        _counter[0] += 1
        if article is None:
            article = make_article(title=f"Article-{_counter[0]}")
        idea = PostIdea(
            article_id=article.id,
            title=title,
            target_subreddit=subreddit,
            source_url=article.url,
            **kw,
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)
        return idea
    return _make


@pytest.fixture()
def make_ab_test(db, make_post_idea):
    from app.models.ab_test import ABTest, ABVariant  # type: ignore[reportMissingModuleSource] 

    def _make(subreddit="armenia", num_variants=2, variant_kw=None, **kw):
        idea = make_post_idea(subreddit=subreddit)
        test = ABTest(
            name="Test AB",
            subreddit=subreddit,
            **kw,
        )
        db.add(test)
        db.flush()
        for i in range(num_variants):
            vkw = (variant_kw or [{}] * num_variants)[i] if variant_kw else {}
            v = ABVariant(
                test_id=test.id,
                post_idea_id=idea.id,
                variant_label=chr(65 + i),
                title=f"Variant {chr(65 + i)} title",
                title_strategy="standard",
                status="live",
                **vkw,
            )
            db.add(v)
        db.commit()
        db.refresh(test)
        return test
    return _make
