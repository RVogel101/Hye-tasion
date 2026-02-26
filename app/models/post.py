"""
SQLAlchemy models for generated post ideas and their approval workflow.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import enum

from app.database import Base


class PostStatus(str, enum.Enum):
    pending = "pending"       # Awaiting approval
    approved = "approved"     # Approved, ready to post
    rejected = "rejected"     # Rejected by user
    posted = "posted"         # Successfully posted to Reddit
    failed = "failed"         # Failed to post


class PostIdea(Base):
    __tablename__ = "post_ideas"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=True)
    post_type = Column(String(20), default="link")  # link, self, crosspost
    target_subreddit = Column(String(100), nullable=False)
    source_url = Column(String(1000), nullable=True)
    status = Column(String(20), default=PostStatus.pending)
    generated_at = Column(DateTime, default=lambda: datetime.now(UTC))
    reviewed_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    reddit_post_id = Column(String(20), nullable=True)  # The actual Reddit post ID after posting

    # Generation metadata
    generation_method = Column(String(50), nullable=True)  # template, ai, hybrid
    predicted_engagement_score = Column(Float, nullable=True)
    source_category = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)  # User notes / rejection reason

    source_article = relationship("Article", back_populates="post_ideas")
    ab_variants = relationship("ABVariant", back_populates="post_idea")
    performance = relationship("PostPerformance", back_populates="post_idea", uselist=False)

    def __repr__(self):
        return f"<PostIdea(id={self.id}, status={self.status}, title={self.title[:40]})>"
