"""Utility functions shared across hyebot's analysis modules.

Previously each file defined its own sentiment and title‑structure helpers.
Centralising them reduces duplication and makes unit testing easier.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def simple_sentiment(text: str) -> float:
    """Basic rule‑based sentiment (-1.0..1.0).

    This is a cheap fallback that lives in ``reddit_collector`` today; other
    components (or external projects) may want to re‑use it without importing
    the entire collector module.
    """
    try:
        import nltk
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
    except Exception:  # nltk not installed / resources missing
        logger.debug("NLTK unavailable, using canned sentiment vocabulary")
        pos_words = {"great", "amazing", "historic", "important", "significant",
                     "victory", "peace", "freedom", "proud", "heritage"}
        neg_words = {"war", "conflict", "death", "attack", "denial", "massacre",
                     "crisis", "tragedy", "dispute", "violence"}
        lower = text.lower()
        score = sum(1 for w in pos_words if w in lower) - sum(1 for w in neg_words if w in lower)
        return max(-1.0, min(1.0, score * 0.2))
    else:
        try:
            sid = SentimentIntensityAnalyzer()
        except LookupError:
            nltk.download("vader_lexicon", quiet=True)
            sid = SentimentIntensityAnalyzer()
        return sid.polarity_scores(text)["compound"]


def title_structure(title: str) -> str:
    """Return a categorical label describing the form of a Reddit title.

    The logic was previously embedded in ``engagement_analyzer``; it lives
    here so tests or other services (e.g. a CLI optimizer) can call it too.
    """
    t = title.strip()
    if t.endswith("?"):
        return "question"
    if re.match(r"^\d", t):
        return "starts_with_number"
    if re.search(r"\b(breaking|update|just in)\b", t, re.I):
        return "breaking_news"
    if re.search(r":\s", t):
        return "topic_colon_detail"
    if re.search(r"\b(why|how|what|who|when|where)\b", t, re.I):
        return "wh_question"
    if len(t.split()) <= 6:
        return "short_punchy"
    if len(t.split()) >= 20:
        return "long_descriptive"
    return "standard"