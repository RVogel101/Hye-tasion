"""
SQLAlchemy models for Reddit scraped data used in engagement analysis.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean  # type: ignore[reportMissingModuleSource, reportMissingImports]
from datetime import datetime, timezone

from app.database import Base


class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id = Column(Integer, primary_key=True, index=True)
    reddit_post_id = Column(String(20), unique=True, nullable=False)
    subreddit = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=True)
    selftext = Column(Text, nullable=True)
    score = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    num_comments = Column(Integer, default=0)
    author = Column(String(100), nullable=True)
    post_type = Column(String(20), nullable=True)  # link, self, image, video
    flair = Column(String(100), nullable=True)
    is_nsfw = Column(Boolean, default=False)
    created_utc = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Computed/derived engagement features
    engagement_score = Column(Float, nullable=True)   # Composite score
    title_length = Column(Integer, nullable=True)
    title_word_count = Column(Integer, nullable=True)
    has_question = Column(Boolean, default=False)
    has_numbers = Column(Boolean, default=False)
    sentiment_score = Column(Float, nullable=True)    # -1.0 to 1.0

    def __repr__(self):
        return f"<RedditPost(id={self.reddit_post_id}, score={self.score})>"


class EngagementPattern(Base):
    """Aggregated patterns derived from analysis of high-performing posts."""
    __tablename__ = "engagement_patterns"

    id = Column(Integer, primary_key=True, index=True)
    subreddit = Column(String(100), nullable=False)
    pattern_type = Column(String(50), nullable=False)  # title_structure, keyword, time_of_day, etc.
    pattern_value = Column(String(500), nullable=False)
    avg_score = Column(Float, default=0.0)
    sample_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<EngagementPattern(subreddit={self.subreddit}, type={self.pattern_type})>"
