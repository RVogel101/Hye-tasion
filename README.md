# Hye-tasion 🇦🇲

**Armenian Reddit Post Idea Generator & A/B Testing Platform**

Scrapes Armenian news media and history journals, analyzes Reddit engagement patterns, generates optimized post ideas, and implements A/B testing to continuously improve post effectiveness.

---

## Features

- **Multi-source scraping** — Armenian news (Armenpress, Asbarez, Armenian Weekly, Hetq, etc.) and history sources (Wikipedia, academic portals)
- **Reddit engagement analysis** — Collects top posts from target subreddits, extracts features (title structure, keywords, sentiment, posting time), and surfaces actionable patterns
- **AI-informed post generation** — Creates Reddit post ideas modelled after high-engagement patterns
- **Approval workflow** — Review, edit, approve, or reject generated ideas via a web dashboard
- **A/B testing** — Generate multiple title variants per post, post them, track metrics, and determine statistical winners
- **Performance tracking** — Monitor score, upvote ratio, and comments over time for posted content
- **Scheduled automation** — Background jobs for scraping, data collection, analysis, and metric refreshes

## Quick Start

### 1. Install dependencies
```bash
cd Hye-tasion
pip install -r requirements.txt
```

### 2. Configure
```bash
copy .env.example .env
# Edit .env with your Reddit API credentials and preferences
```

Get Reddit API credentials at https://www.reddit.com/prefs/apps (create a "script" type app).

### 3. Run
```bash
python main.py
```

> 🔁 **Alternate ingestion**
>
> Set `USE_CORE_NEWS=true` in your environment to bypass the built‑in web
> scrapers; the app will instead call
> ``armenian_corpus_core.data_sources.get_news_documents()`` and load any
> articles provided there.  This lets Hyebot consume a centralised database
> of news content maintained by the corpus‑core project.


Open **http://127.0.0.1:8000** in your browser.

## Dashboard

The web interface provides:

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Stats overview, quick actions, engagement recommendations |
| **Post Ideas** | Browse, review, approve/reject, and edit generated post ideas |
| **A/B Tests** | Manage active tests, post variants, refresh metrics, analyze results |
| **Engagement Analysis** | Visualize patterns — title structure, keywords, optimal posting times |
| **Sources** | View all scraped news and history sources |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard statistics |
| POST | `/api/scrape/all` | Trigger full scrape |
| POST | `/api/scrape/news` | Scrape news sources only (see **USE_CORE_NEWS** below) |
| POST | `/api/scrape/history` | Scrape history sources only |
| GET | `/api/articles` | List scraped articles |
| GET | `/api/post-ideas` | List generated post ideas |
| POST | `/api/generate-ideas` | Generate new post ideas |
| POST | `/api/post-ideas/{id}/approve` | Approve (optionally with A/B test) |
| POST | `/api/post-ideas/{id}/reject` | Reject an idea |
| GET | `/api/ab-tests` | List A/B tests |
| POST | `/api/ab-tests/{id}/post-variants` | Post variants to Reddit |
| POST | `/api/ab-tests/{id}/analyze` | Analyze test results |
| POST | `/api/reddit/collect` | Collect Reddit engagement data |
| POST | `/api/reddit/analyze` | Run engagement pattern analysis |
| GET | `/api/reddit/recommendations` | Get posting recommendations |

## Architecture

> **Note:** Hyebot now depends on the `armenian-corpus-core` package for
> shared normalization/contract utilities.  Install it in editable mode by
> running `pip install -e ../armenian-corpus-core` (see
> `requirements.txt`).  The scrapers import helpers such as
> `normalize_text_for_hash` and the analysis code uses common sentiment/title
> utilities from the core package.


```
Hye-tasion/
├── main.py                   # Entry point
├── config.yaml               # Scraping sources & settings
├── requirements.txt
├── app/
│   ├── __init__.py           # FastAPI app setup
│   ├── database.py           # SQLAlchemy engine & session
│   ├── scheduler.py          # APScheduler background jobs
│   ├── api/
│   │   └── routes.py         # All REST endpoints
│   ├── models/
│   │   ├── source.py         # Source, Article
│   │   ├── post.py           # PostIdea
│   │   ├── reddit_data.py    # RedditPost, EngagementPattern
│   │   └── ab_test.py        # ABTest, ABVariant, PostPerformance
│   ├── scrapers/
│   │   ├── base_scraper.py   # Abstract scraper with retry logic
│   │   ├── armenian_news.py  # RSS scrapers for 9 Armenian news outlets
│   │   ├── history_journals.py # Wikipedia, academic, on-this-day scrapers
│   │   └── scraping_service.py # Orchestrates scrape runs
│   ├── analysis/
│   │   ├── reddit_collector.py    # PRAW-based Reddit data collection
│   │   ├── engagement_analyzer.py # Feature extraction & pattern mining
│   │   └── post_generator.py      # Template-based post idea generation
│   └── ab_testing/
│       └── ab_framework.py   # Create tests, post variants, statistical analysis
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

## Configuration

Edit `config.yaml` to add/remove scraping sources, adjust Reddit analysis parameters, or tune A/B testing thresholds.

Key settings in `.env`:
- `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` — Reddit API credentials
- `TARGET_SUBREDDIT` — The subreddit to post to (default: `armenia`)
- `ANALYSIS_SUBREDDITS` — Comma-separated list of subreddits to analyze for engagement patterns
- `SCRAPE_INTERVAL_MINUTES` — How often to auto-scrape (default: 60)

## Reddit API Compliance

This project uses the Reddit API under the [Reddit Developer Terms](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) and the [Reddit Data API Terms](https://support.reddithelp.com/hc/en-us/articles/18591005200404). Below is a summary of the key terms and how Hye-tasion complies.

### Developer Terms Summary

| Area | Requirement | How We Comply |
|------|-------------|---------------|
| **Registration** | Valid Reddit account in good standing; keep API credentials secure | Credentials stored in `.env` (never committed); script-type app |
| **Allowed Use** | Non-exclusive, revocable license for API access; attribute User Content with links and usernames | Reddit posts displayed with permalink and `u/author` attribution |
| **No Commercial Use** | Don't monetize Reddit data or use it in paid services without a separate agreement | Hye-tasion is a personal/community tool with no monetization |
| **No AI/ML Training** | Don't use Reddit data to train models without permission | Only statistical pattern analysis (percentiles, keyword frequency); no model training |
| **Rate Limits** | Don't circumvent or exceed rate limits | PRAW handles `X-Ratelimit-*` headers; app adds delays between submissions |
| **Content Removal** | Delete local copies if content is removed from Reddit | Scheduled cleanup job checks for removed/deleted posts and purges stale data |
| **No Spam** | Don't spam or harass users | Posting cooldowns, sequential variant posting with delays, daily caps per subreddit |
| **User Agent** | Properly identify your bot | Format: `script:HyeTasion:1.0 (by /u/username)` |
| **Privacy** | Comply with data protection laws; don't share Reddit data with third parties | Data stays local in SQLite; no third-party sharing |
| **Termination** | Reddit can revoke access at any time; delete all data if terminated | All Reddit data stored in a single DB; can be wiped cleanly |
| **Liability** | Reddit provides everything "as-is"; max liability $100; you indemnify Reddit | Acknowledged — personal use tool |

### Data API Terms Summary

| Area | Requirement | How We Comply |
|------|-------------|---------------|
| **User Content license** | May copy and display User Content; may only modify to format for display | We display titles/scores as-is; formatting only for HTML rendering |
| **No AI/ML training** | Cannot use User Content to train ML/AI models without rightsholder permission | No model training; engagement analysis uses only statistical aggregation |
| **No commercial use** | Cannot sell, lease, sublicense, or derive revenue from Data APIs without written approval | Non-commercial personal/community project |
| **OAuth required** | Must use OAuth tokens; must not misrepresent user agent or OAuth identity | PRAW handles OAuth; user agent set per Reddit's format |
| **Attribution** | Must display "for Reddit" branding (e.g., "HyeTasion for Reddit") | Shown in frontend header and footer |
| **Rate limits** | Reddit can set and enforce limits; exceeding can result in permanent revocation | PRAW rate limiter + application-level cooldowns |
| **On termination** | Must delete all cached User Content, Materials, **and derived data/models** | Cleanup job purges raw posts + derived fields; DB can be wiped entirely |
| **Third-party libraries** | Must comply with PRAW's own terms when using it | PRAW used per its BSD license terms |
| **Confidentiality** | Protect any Reddit confidential information | No Reddit confidential info stored or shared |
| **Future fees** | Reddit reserves the right to charge for API access | Acknowledged; will comply if pricing is introduced |

### Compliance Controls

- **Rate limiting** — PRAW's built-in rate limiter + configurable delays between posts (`POSTING_COOLDOWN_SECONDS` in `.env`)
- **Attribution** — "for Reddit" branding in frontend header/footer; collected Reddit posts include author and permalink linking back to original content
- **Data retention** — Background job periodically checks stored posts against Reddit and removes deleted/suspended content; configurable retention period via `DATA_RETENTION_DAYS`
- **Spam prevention** — Minimum interval between submissions, daily posting cap per subreddit, duplicate-post detection
- **Credential security** — All secrets in `.env` (gitignored), never hardcoded
