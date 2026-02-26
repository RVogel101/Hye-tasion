"""
SQLAlchemy models for scraped content sources and articles.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import enum

from app.database import Base


class SourceType(str, enum.Enum):
    rss = "rss"
    html = "html"
    api = "api"


class SourceCategory(str, enum.Enum):
    news = "news"
    history = "history"
    academic = "academic"
    culture = "culture"
    investigative = "investigative"
    analysis = "analysis"


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)
    url = Column(String(500), nullable=False)
    rss_url = Column(String(500), nullable=True)
    source_type = Column(String(20), default="rss")
    category = Column(String(30), default="news")
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime, nullable=True)
    article_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    articles = relationship("Article", back_populates="source")

    def __repr__(self):
        return f"<Source(name={self.name})>"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), unique=True, nullable=False)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=lambda: datetime.now(UTC))
    category = Column(String(50), nullable=True)
    tags = Column(Text, nullable=True)  # JSON list of tags
    is_processed = Column(Boolean, default=False)  # Has been used for post generation

    source = relationship("Source", back_populates="articles")
    post_ideas = relationship("PostIdea", back_populates="source_article")

    def __repr__(self):
        return f"<Article(title={self.title[:50]})>"
