from app.scrapers.base_scraper import BaseScraper, ScrapedArticle
from app.scrapers.armenian_news import ALL_NEWS_SCRAPERS
from app.scrapers.history_journals import ALL_HISTORY_SCRAPERS
from app.scrapers.scraping_service import run_all_scrapes, run_news_scrape, run_history_scrape

__all__ = [
    "BaseScraper", "ScrapedArticle",
    "ALL_NEWS_SCRAPERS", "ALL_HISTORY_SCRAPERS",
    "run_all_scrapes", "run_news_scrape", "run_history_scrape",
]
