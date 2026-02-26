"""
Base scraper class with shared HTTP, retry, and parsing utilities.
"""
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ScrapedArticle:
    """Lightweight data container for a scraped article."""

    def __init__(
        self,
        title: str,
        url: str,
        content: str = "",
        summary: str = "",
        published_at: Optional[datetime] = None,
        category: str = "news",
        tags: Optional[list] = None,
    ):
        self.title = title.strip()
        self.url = url.strip()
        self.content = content.strip()
        self.summary = summary.strip()
        self.published_at = published_at
        self.category = category
        self.tags = tags or []

    def __repr__(self):
        return f"<ScrapedArticle title={self.title[:50]!r}>"


class BaseScraper(ABC):
    """Abstract base for all scrapers — handles HTTP and retry logic."""

    def __init__(self, name: str, base_url: str, request_delay: float = 1.5):
        self.name = name
        self.base_url = base_url
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    )
    def fetch(self, url: str, timeout: int = 15) -> Optional[requests.Response]:
        """Fetch a URL with retry logic. Returns None on non-retryable errors."""
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            time.sleep(self.request_delay)
            return resp
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (403, 404, 410):
                logger.warning(f"[{self.name}] Non-retryable HTTP {e.response.status_code} for {url}")
                return None
            raise

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def clean_text(self, text: str) -> str:
        """Remove excessive whitespace from scraped text."""
        import re
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @abstractmethod
    def scrape(self) -> list[ScrapedArticle]:
        """Scrape and return a list of ScrapedArticle objects."""
        ...
