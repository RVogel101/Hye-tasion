"""
SQLAlchemy models for A/B testing framework.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from app.database import Base


class ABTest(Base):
    """An A/B test comparing multiple title/body variants."""
    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    subreddit = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    concluded_at = Column(DateTime, nullable=True)
    winner_variant_id = Column(Integer, nullable=True)

    # Statistical results
    significance_achieved = Column(Boolean, default=False)
    p_value = Column(Float, nullable=True)

    variants = relationship("ABVariant", back_populates="test")

    def __repr__(self):
        return f"<ABTest(id={self.id}, name={self.name})>"


class ABVariant(Base):
    """A single variant within an A/B test."""
    __tablename__ = "ab_variants"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("ab_tests.id"), nullable=False)
    post_idea_id = Column(Integer, ForeignKey("post_ideas.id"), nullable=True)
    variant_label = Column(String(10), nullable=False)  # A, B, C...
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    title_strategy = Column(String(100), nullable=True)  # question, number, claim, etc.
    reddit_post_id = Column(String(20), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="draft")  # draft, live, concluded

    # Performance metrics (fetched from Reddit)
    score = Column(Integer, default=0)
    upvote_ratio = Column(Float, default=0.0)
    num_comments = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    last_metrics_update = Column(DateTime, nullable=True)

    test = relationship("ABTest", back_populates="variants")
    post_idea = relationship("PostIdea", back_populates="ab_variants")

    def __repr__(self):
        return f"<ABVariant(label={self.variant_label}, score={self.score})>"


class PostPerformance(Base):
    """Tracks real-world performance of posted Reddit content."""
    __tablename__ = "post_performance"

    id = Column(Integer, primary_key=True, index=True)
    post_idea_id = Column(Integer, ForeignKey("post_ideas.id"), nullable=False)
    reddit_post_id = Column(String(20), nullable=False, unique=True)
    subreddit = Column(String(100), nullable=False)

    # Snapshot history — finer-grained time buckets
    score_at_1h = Column(Integer, nullable=True)
    score_at_2h = Column(Integer, nullable=True)
    score_at_4h = Column(Integer, nullable=True)
    score_at_6h = Column(Integer, nullable=True)
    score_at_12h = Column(Integer, nullable=True)
    score_at_24h = Column(Integer, nullable=True)
    score_at_48h = Column(Integer, nullable=True)
    score_at_7d = Column(Integer, nullable=True)
    final_score = Column(Integer, nullable=True)
    final_comments = Column(Integer, nullable=True)
    final_upvote_ratio = Column(Float, nullable=True)

    first_checked_at = Column(DateTime, nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    post_idea = relationship("PostIdea", back_populates="performance")

    def __repr__(self):
        return f"<PostPerformance(reddit_id={self.reddit_post_id}, score={self.final_score})>"
