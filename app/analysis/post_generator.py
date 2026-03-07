"""
Post idea generator — takes scraped articles and produces Reddit post ideas
modelled after high-engagement patterns discovered by the analyzer.
"""
import json
import logging
import os
import re
import random
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session  # type: ignore[reportMissingModuleSource, reportMissingImports]

from app.models.source import Article
from app.models.post import PostIdea
from app.models.reddit_data import EngagementPattern

logger = logging.getLogger(__name__)

TARGET_SUBREDDIT = os.getenv("TARGET_SUBREDDIT", "ArmeniansGlobal")

# --- Boilerplate patterns to strip ---
_BOILERPLATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\s*[–—-]\s*The post .+? appeared first on .+?\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"\s*\|\s*.+$"),  # "Title | Source Name"
    re.compile(
        r"\s*[–—-]?\s*"
        r"(Armenpress|Asbarez|Armenian Weekly|The Armenian Weekly|Hetq|Panorama|"
        r"Azatutyun|EVN Report|OC Media|Civilnet|CIVILNET|AnewZ|Eurasianet|"
        r"Council on Foreign Relations|Stratfor|EWTN News|Caspian Post|"
        r"FOX 11 Los Angeles|The National Law Review|Travel And Tour World|"
        r"The Armenian Mirror-Spectator|FRANCE 24|Latest news from Azerbaijan|"
        r"news\.google\.com)\s*\.?\s*$",
        re.IGNORECASE,
    ),
    # "By Author Name" prefix at start of summaries
    re.compile(r"^By\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\s+", re.MULTILINE),
]

# Armenian relevance filter
_ARMENIAN_RELEVANCE = re.compile(
    r"\barmenia\b|\barmenian\b|\bartsakh\b|\bart[sz]akh\b|\bkarabakh\b"
    r"|\byerevan\b|\bgyumri\b|\bpashinyan\b|\bkocharyan\b|\bsargsyan\b"
    r"|\baliyev\b.*armenia|\bazerbaijan\b.*armenia|\bgenocide\b"
    r"|\bechmiadz[iy]n\b|\bvardanyan\b|\bjavakh\b|\bhay\b|\bhye\b"
    r"|\bnagorno\b|\bstepanakert\b|\bshusha\b|\bshushi\b",
    re.IGNORECASE,
)

# ——— Title templates keyed by structure type ———
TEMPLATES: dict[str, list[str]] = {
    "question": [
        "What do you think about {topic}?",
        "Why is {topic} not getting more attention?",
        "How should the Armenian community respond to {topic}?",
    ],
    "topic_colon_detail": [
        "{topic}: {detail}",
        "{topic} — what this means for Armenia",
    ],
    "short_punchy": [
        "{topic}",
    ],
    "long_descriptive": [
        "In-depth: {topic}",
        "A comprehensive look at {topic}",
    ],
    "breaking_news": [
        "Breaking: {topic}",
        "Just in: {topic}",
    ],
    "standard": [
        "{topic}",
        "{topic} — {detail}",
    ],
}

HISTORY_TEMPLATES = [
    "On this day in Armenian history: {topic}",
    "TIL: {topic}",
    "History corner: {topic}",
    "The story of {topic}",
    "Remembering {topic}",
]

INVESTIGATION_TEMPLATES = [
    "Investigative report: {topic}",
    "{topic} — an investigative look",
    "Inside story: {topic}",
]

ANALYSIS_TEMPLATES = [
    "Analysis: {topic} — what it means for Armenia",
    "Opinion: {topic}",
    "{topic}: an analytical perspective",
]


def _clean_text(text: str) -> str:
    """Remove boilerplate suffixes, HTML entities, bylines, and truncation artifacts."""
    # Fix HTML entities
    text = text.replace("&quot;", '"').replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("\u0026quot;", '"').replace("\u0026", "&")

    # Remove boilerplate patterns
    for pat in _BOILERPLATE_PATTERNS:
        text = pat.sub("", text)

    text = text.strip()

    # If text was truncated mid-word, trim to last complete sentence or clause
    if text and text[-1] not in '.!?"\'':
        last_period = max(text.rfind(". "), text.rfind("! "), text.rfind("? "))
        if last_period > len(text) * 0.4:
            text = text[:last_period + 1]

    return text.strip()


def _is_relevant_to_armenia(article: Article) -> bool:
    """Check if an article is actually about Armenia/Armenian topics."""
    title = str(article.title or "")
    summary = str(article.summary or "")
    tags_field = str(article.tags or "")
    combined = f"{title} {summary} {tags_field}"
    return bool(_ARMENIAN_RELEVANCE.search(combined))


def _choose_template(category: str, structure: Optional[str] = None) -> str:
    """Pick an appropriate title template based on content category."""
    if category == "history":
        return random.choice(HISTORY_TEMPLATES)
    if category == "investigative":
        return random.choice(INVESTIGATION_TEMPLATES)
    if category == "analysis":
        return random.choice(ANALYSIS_TEMPLATES)
    pool = TEMPLATES.get(structure or "standard", TEMPLATES["standard"])
    return random.choice(pool)


def _extract_topic(article: Article) -> tuple[str, str]:
    """
    Extract a short topic phrase and a detail phrase from an article.
    Returns (topic, detail).
    """
    title: str = str(article.title or "")
    title = _clean_text(title)

    summary: str = str(article.summary or "")
    summary = _clean_text(summary)

    # Use cleaned summary for detail, cut at sentence boundary
    if summary and len(summary) > 120:
        # Find sentence boundary within ~120 chars
        cut = summary[:140]
        last_period = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if last_period > 40:
            detail = cut[:last_period + 1]
        else:
            last_space = cut[:120].rfind(" ")
            detail = cut[:last_space] if last_space > 60 else cut[:120]
    elif summary:
        detail = summary
    else:
        detail = ""

    topic = title[:100].strip()
    return topic, detail


def _get_best_structure(db: Session, subreddit: str) -> str:
    """Look up the best-performing title structure for this subreddit."""
    best = (
        db.query(EngagementPattern)
        .filter_by(subreddit=subreddit, pattern_type="title_structure")
        .order_by(EngagementPattern.avg_score.desc())
        .first()
    )
    if best:
        return str(best.pattern_value)
    return "standard"


def _get_top_keywords(db: Session, subreddit: str) -> list[str]:
    """Fetch the top 10 high-engagement keywords for this subreddit."""
    kws = (
        db.query(EngagementPattern)
        .filter_by(subreddit=subreddit, pattern_type="keyword")
        .order_by(EngagementPattern.avg_score.desc())
        .limit(10)
        .all()
    )
    return [str(k.pattern_value) for k in kws]


def _weave_keywords(title: str, keywords: list[str]) -> str:
    """Try to incorporate a relevant keyword into the title."""
    title_lower = title.lower()
    for kw in keywords:
        if kw.lower() in title_lower:
            return title
    if len(title) < 200 and keywords:
        kw = random.choice(keywords[:3])
        if kw.lower() not in title_lower:
            title = f"[{kw.title()}] {title}"
    return title


def _generate_body(article: Article) -> str:
    """Generate Reddit post body text."""
    parts = []
    summary = _clean_text(str(article.summary or ""))
    url = str(article.url or "")
    tags_field = str(article.tags or "")

    if summary:
        parts.append(summary)
    if url:
        parts.append(f"\n\nSource: {url}")
    tags: list[str] = []
    if tags_field:
        try:
            raw_tags = json.loads(tags_field)
            if isinstance(raw_tags, list):
                tags = [str(t) for t in raw_tags[:5]]
        except Exception:
            pass
    if tags:
        parts.append(f"\n\nRelated: {', '.join(tags)}")

    prompts = [
        "\n\n---\nWhat are your thoughts on this?",
        "\n\n---\nDoes anyone have more context on this?",
        "\n\n---\nHow do you think this will impact the Armenian community?",
        "\n\n---\nWould love to hear the community's perspective on this.",
        "\n\n---\nDiscussion welcome — what's your take?",
    ]
    parts.append(random.choice(prompts))

    return "".join(parts)[:40000]


# Structures that should ONLY apply to certain categories
_NEWS_SAFE_STRUCTURES = ["short_punchy", "standard", "breaking_news", "topic_colon_detail"]
_ALL_STRUCTURES = list(TEMPLATES.keys())


def generate_post_ideas(
    db: Session,
    subreddit: str = TARGET_SUBREDDIT,
    max_ideas: int = 20,
    categories: Optional[list[str]] = None,
) -> list[PostIdea]:
    """
    Main entry point: generate post ideas from unprocessed articles.
    """
    if categories is None:
        categories = ["news", "history", "investigative", "analysis", "culture",
                       "international", "diaspora"]

    best_structure = _get_best_structure(db, subreddit)
    top_kws = _get_top_keywords(db, subreddit)

    articles = (
        db.query(Article)
        .filter(Article.is_processed == False)  # noqa: E712
        .filter(Article.title.isnot(None))
        .filter(Article.category.in_(categories))
        .order_by(Article.scraped_at.desc())
        .limit(max_ideas * 3)
        .all()
    )

    ideas: list[PostIdea] = []
    seen_titles: set[str] = set()

    for article in articles:
        if len(ideas) >= max_ideas:
            break

        if not _is_relevant_to_armenia(article):
            article.is_processed = True  # type: ignore[assignment]
            logger.debug(f"Skipping non-Armenian article: {str(article.title)[:60]}")
            continue

        category = str(article.category or "news")
        url = str(article.url or "")

        topic, detail = _extract_topic(article)
        if not topic or len(topic) < 10:
            continue

        # Pick structure — news/international should use news-safe structures
        if category in ("news", "international", "culture", "diaspora"):
            structures_pool = _NEWS_SAFE_STRUCTURES
        else:
            structures_pool = _ALL_STRUCTURES

        structure = structures_pool[len(ideas) % len(structures_pool)]
        template = _choose_template(category, structure)

        # Fill template — only use {detail} if template asks for it AND detail is clean
        raw_title = template.format(
            topic=topic[:80],
            detail=detail[:80] if detail else "",
            number=random.choice([3, 5, 7, 10]),
            keyword=top_kws[0] if top_kws else "Armenia",
        )

        raw_title = _clean_text(raw_title)

        # If title got too long or messy, just use the clean topic
        if len(raw_title) > 250 or raw_title.count("—") > 2:
            raw_title = topic

        # Weave in keywords if available
        raw_title = _weave_keywords(raw_title, top_kws)

        # Final length cap
        if len(raw_title) > 300:
            raw_title = raw_title[:297] + "..."

        raw_title = raw_title.strip()

        # Deduplicate
        norm = raw_title.lower()
        if norm in seen_titles:
            continue
        seen_titles.add(norm)

        post_type = "link" if url else "self"
        body = _generate_body(article)

        best_pattern = (
            db.query(EngagementPattern)
            .filter_by(subreddit=subreddit, pattern_type="title_structure",
                       pattern_value=best_structure)
            .first()
        )
        predicted_score = best_pattern.avg_score if best_pattern else None

        idea = PostIdea(
            article_id=article.id,
            title=raw_title,
            body=body,
            post_type=post_type,
            target_subreddit=subreddit,
            source_url=url,
            generation_method="template",
            predicted_engagement_score=predicted_score,
            source_category=category,
        )
        db.add(idea)
        article.is_processed = True  # type: ignore[assignment]
        ideas.append(idea)

    db.commit()
    logger.info(f"[Generator] Created {len(ideas)} post ideas for r/{subreddit}.")
    return ideas


def generate_ab_variants(
    db: Session,
    post_idea: PostIdea,
    num_variants: int = 2,
) -> list[dict]:
    """
    Generate multiple title variants for A/B testing from a single PostIdea.
    """
    article = (
        db.query(Article).filter_by(id=post_idea.article_id).first()
        if post_idea.article_id is not None
        else None
    )

    topic = _clean_text(str(article.title))[:80] if article else post_idea.title[:80]
    detail = _clean_text(str(article.summary or ""))[:100] if article else ""
    category = str(article.category or "news") if article else "news"

    structures = list(TEMPLATES.keys())
    random.shuffle(structures)

    variants = []
    labels = "ABCDEFGH"
    for i in range(min(num_variants, len(structures))):
        structure = structures[i]
        template = _choose_template(category, structure)
        title = template.format(
            topic=topic,
            detail=detail or topic,
            number=random.choice([3, 5, 7, 10]),
            keyword="Armenia",
        )[:300].strip()

        variants.append({
            "label": labels[i],
            "title": title,
            "body": post_idea.body or "",
            "title_strategy": structure,
        })

    return variants
