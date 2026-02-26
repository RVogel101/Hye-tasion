"""
Reddit data collector — fetches top/hot/new posts from analysis subreddits,
extracts engagement features, and stores them for pattern analysis.
"""
import logging
import os
import re
from datetime import datetime, UTC, timezone
from typing import Optional

import praw
from sqlalchemy.orm import Session

from app.models.reddit_data import RedditPost, EngagementPattern

logger = logging.getLogger(__name__)


def _get_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "HyeTasion/1.0"),
    )


def _extract_features(submission) -> dict:
    """Extract engagement-relevant features from a PRAW submission object."""
    title = submission.title or ""
    return {
        "title_length": len(title),
        "title_word_count": len(title.split()),
        "has_question": "?" in title,
        "has_numbers": bool(re.search(r"\d", title)),
        "post_type": (
            "self" if submission.is_self
            else "image" if hasattr(submission, "post_hint") and submission.post_hint in ("image", "rich:video")
            else "link"
        ),
    }


def _simple_sentiment(text: str) -> float:
    """
    Minimal rule-based sentiment score (-1.0 to 1.0).
    Replaced by a real model if NLTK / VADER is available.
    """
    try:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        try:
            sid = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
            sid = SentimentIntensityAnalyzer()
        return sid.polarity_scores(text)["compound"]
    except Exception:
        pos_words = {"great", "amazing", "historic", "important", "significant",
                     "victory", "peace", "freedom", "proud", "heritage"}
        neg_words = {"war", "conflict", "death", "attack", "denial", "massacre",
                     "crisis", "tragedy", "dispute", "violence"}
        lower = text.lower()
        score = sum(1 for w in pos_words if w in lower) - sum(1 for w in neg_words if w in lower)
        return max(-1.0, min(1.0, score * 0.2))


def collect_reddit_data(
    db: Session,
    subreddits: Optional[list[str]] = None,
    posts_per_sub: int = 100,
    time_filter: str = "month",
) -> dict:
    """
    Pull top posts from each analysis subreddit, compute features, persist to DB.
    """
    if subreddits is None:
        raw = os.getenv("ANALYSIS_SUBREDDITS", "armenia,hayastan,armenianhistory,history,worldnews")
        subreddits = [s.strip() for s in raw.split(",") if s.strip()]

    reddit = _get_reddit_client()
    results = {}

    for sub_name in subreddits:
        new_count = 0
        try:
            sub = reddit.subreddit(sub_name)
            for submission in sub.top(time_filter=time_filter, limit=posts_per_sub):
                existing = db.query(RedditPost).filter_by(reddit_post_id=submission.id).first()
                if existing:
                    # Refresh score / comments on already-stored posts
                    existing.score = submission.score
                    existing.num_comments = submission.num_comments
                    existing.upvote_ratio = submission.upvote_ratio
                    continue

                features = _extract_features(submission)
                sentiment = _simple_sentiment(submission.title)

                post = RedditPost(
                    reddit_post_id=submission.id,
                    subreddit=sub_name,
                    title=submission.title[:499],
                    url=submission.url[:999] if submission.url else None,
                    selftext=(submission.selftext or "")[:5000],
                    score=submission.score,
                    upvote_ratio=submission.upvote_ratio,
                    num_comments=submission.num_comments,
                    author=str(submission.author) if submission.author else None,
                    post_type=features["post_type"],
                    flair=submission.link_flair_text,
                    is_nsfw=submission.over_18,
                    created_utc=datetime.fromtimestamp(submission.created_utc, tz=UTC),
                    title_length=features["title_length"],
                    title_word_count=features["title_word_count"],
                    has_question=features["has_question"],
                    has_numbers=features["has_numbers"],
                    sentiment_score=sentiment,
                    engagement_score=float(submission.score) * submission.upvote_ratio,
                )
                db.add(post)
                new_count += 1

            db.commit()
            results[sub_name] = {"new": new_count}
            logger.info(f"[Reddit collector] r/{sub_name}: {new_count} new posts stored.")

        except Exception as exc:
            db.rollback()
            logger.error(f"[Reddit collector] r/{sub_name} failed: {exc}", exc_info=True)
            results[sub_name] = {"error": str(exc)}

    return results


def update_posted_metrics(db: Session, reddit_post_id: str) -> Optional[dict]:
    """Fetch current metrics for a previously posted Reddit submission."""
    try:
        reddit = _get_reddit_client()
        submission = reddit.submission(id=reddit_post_id)
        return {
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "num_comments": submission.num_comments,
        }
    except Exception as exc:
        logger.error(f"[Reddit metrics] Failed to fetch {reddit_post_id}: {exc}")
        return None
