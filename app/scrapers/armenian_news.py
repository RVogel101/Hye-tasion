"""
Scrapers for Armenian news media sources and international outlets.
Covers: Armenpress, Asbarez, Armenian Weekly, Azatutyun, Hetq,
        Panorama.am, EVN Report, OC Media, Civilnet,
        Massis Post, Armenian Mirror-Spectator, Horizon Weekly, Agos.
International (keyword-filtered):
        Google News Armenia, Al Jazeera, Al-Monitor, BBC World,
        France 24, Deutsche Welle, Euronews.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import feedparser

from app.scrapers.base_scraper import BaseScraper, ScrapedArticle
from app.scrapers.utils import parse_rss_date

logger = logging.getLogger(__name__)



# the RSS date parser and auto-tag logic have been moved to
# ``app.scrapers.utils``; the import above provides ``parse_rss_date``.


class RSSNewsScraper(BaseScraper):
    """
    Generic RSS-feed scraper.  All Armenian news sources that expose an RSS
    feed use this class; source-specific behaviour is handled by subclasses.
    """

    def __init__(self, name: str, base_url: str, rss_url: str, category: str = "news"):
        super().__init__(name, base_url)
        self.rss_url = rss_url
        self.category = category

    def scrape(self) -> list[ScrapedArticle]:
        logger.info(f"[{self.name}] Fetching RSS feed: {self.rss_url}")
        try:
            feed = feedparser.parse(self.rss_url)
        except Exception as exc:
            logger.error(f"[{self.name}] RSS parse error: {exc}")
            return []

        articles: list[ScrapedArticle] = []
        for entry in feed.entries:
            # feedparser may return lists for some fields; coerce to str first
            title = str(entry.get("title", "")).strip()
            url = str(entry.get("link", "")).strip()
            if not title or not url:
                continue

            summary = str(entry.get("summary", entry.get("description", "")))
            summary = self.clean_text(summary)
            # Strip HTML tags from summary
            from bs4 import BeautifulSoup
            summary = BeautifulSoup(summary, "lxml").get_text(separator=" ")
            summary = self.clean_text(summary)

            published_at = _parse_rss_date(
                str(entry.get("published", entry.get("updated", "")) or "")
            )

            # entry.get may return None; ensure we have a list before iterating
            raw_tags = entry.get("tags") or []
            tags = [str(t.get("term", "")) for t in raw_tags if t and t.get("term")]

            articles.append(
                ScrapedArticle(
                    title=title,
                    url=url,
                    content="",  # Full content fetched on demand
                    summary=summary[:1000],
                    published_at=published_at,
                    category=self.category,
                    tags=tags,
                )
            )

        logger.info(f"[{self.name}] Collected {len(articles)} articles from RSS.")
        return articles

    def fetch_full_content(self, url: str) -> str:
        """Fetch and extract the main article text from the article page."""
        resp = self.fetch(url)
        if not resp:
            return ""
        soup = self.parse_html(resp.text)
        # Remove boilerplate elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "aside", "form", "iframe", "noscript"]):
            tag.decompose()
        # Try common article content containers
        for selector in ["article", ".article-body", ".entry-content",
                         ".post-content", ".content", "main"]:
            container = soup.select_one(selector)
            if container:
                return self.clean_text(container.get_text(separator=" "))
        return self.clean_text(soup.body.get_text(separator=" ") if soup.body else "")


# ---------------------------------------------------------------------------
# Armenian keyword list — used to filter international feeds
# ---------------------------------------------------------------------------

ARMENIAN_KEYWORDS: list[str] = [
    # ===================================================================
    # Country / people / demonyms
    # ===================================================================
    r"\barmenia\b", r"\barmenian[s]?\b", r"\bhay(?:astan)?\b",
    r"\bhay(?:er|ots|eri|otz|u)?\b",

    # ===================================================================
    # Cities & regions inside Armenia
    # ===================================================================
    r"\byerevan\b", r"\beveran\b",                       # W. Arm. transliteration
    r"\bgyumri\b", r"\bkumayri\b", r"\bghewmri\b", r"\bleninakan\b",
    r"\bvanadzor\b", r"\bkirovakan\b",
    r"\bdilijan\b", r"\btilisan\b",
    r"\bjermuk\b", r"\bkapan\b", r"\bgabann?\b",
    r"\bgoris\b", r"\bkoriss?\b",
    r"\bsevan\b", r"\bsevana?\s*lich\b",
    r"\btsaghkadzor\b", r"\bdzaghgadzor\b",
    r"\barmavir\b",
    r"\blori\b", r"\bsyunik\b", r"\bsissian\b", r"\bsisian\b",
    r"\btavush\b", r"\bdavush\b",
    r"\bararat\b", r"\bmeghri\b", r"\bmeghr[iu]\b",
    r"\bechmiadzin\b", r"\betchmiadzin\b", r"\bvagharshapat\b",

    # ===================================================================
    # Artsakh / Karabakh (incl. common transliterations)
    # ===================================================================
    r"\bartsakh\b", r"\bkarabakh\b", r"\bnagorno[- ]?karabakh\b",
    r"\bstepanakert\b", r"\bshushi\b", r"\bshusha\b",
    r"\bhadrut\b", r"\bberdzor\b", r"\blachin\b",
    r"\bkhankendi\b", r"\baskeran\b",
    r"\bmartakert\b", r"\bmardagerd\b",
    r"\bmartuni\b", r"\bmardouni\b",
    r"\bgandzasar\b", r"\bgantsasar\b",
    r"\btigranakert\b",

    # ===================================================================
    # Political figures — Eastern (‑yan) AND Western (‑ian) spellings
    # ===================================================================
    # Republic of Armenia leaders
    r"\bpash[iy]n[iy]an\b",                               # Pashinyan / Pashinian
    r"\bkoch?ar[iy]an\b",                                  # Kocharyan / Kocharian
    r"\bsark?[iy]ss?[iy]an\b",                             # Sargsyan / Sarkissian
    r"\bter[- ]?petross?[iy]an\b",                         # Ter-Petrosyan / Ter-Petrossian
    r"\bsimon[iy]an\b",                                     # Simonyan / Simonian
    r"\bmirzo[iy]an\b",                                     # Mirzoyan / Mirzoian

    # ===================================================================
    # Genocide / historical events & earlier massacres
    # ===================================================================
    r"\barmenian[- ]?genocide\b", r"\b1915\b.*(?:ottoman|turkey|armenian)",
    r"\bmedz\s*yeghern\b", r"\baghet\b",
    r"\bsevres\b", r"\btreaty\s+of\s+sevres\b",
    r"\bkars\b.*treaty", r"\btreaty\s+of\s+kars\b",
    r"\bwilsonian\s+armenia\b",
    r"\bapril\s*24\b",                                      # Genocide remembrance day
    # Hamidian massacres (1894-1896)
    r"\bhamidian\s*massacre[s]?\b",
    r"\b1894\b.*(?:armenian|massacre|ottoman)",
    r"\b1895\b.*(?:armenian|massacre|ottoman)",
    r"\b1896\b.*(?:armenian|massacre|ottoman|bank)",
    r"\babdul\s*hamid\b.*(?:armenian|massacre)",
    r"\bsultan\s*hamid\b",
    r"\bsassoun\b", r"\bsasun\b",                           # Sassoun resistance / massacre
    r"\bsasna\s*dzrer\b", r"\bsasna\s*tsrer\b",             # Sasna Tsrer (Daredevils of Sassoun) — E. & W.
    r"\bzeytun\s*(?:rebellion|uprising|resist)\b",
    # Adana massacre (1909)
    r"\badana\s*massacre[s]?\b",
    r"\b1909\b.*(?:armenian|massacre|adana|cilicia)",
    r"\bcilicia\b.*(?:massacre|1909|pogrom)",
    # Ottoman oppression / broader persecution
    r"\bottoman\b.*(?:armenian|persecution|massacre|oppression|deportation)",
    r"\barmenian\b.*(?:ottoman|deportation|death\s*march)",
    r"\byoung\s*turk[s]?\b.*(?:armenian|massacre|genocide)",
    r"\bcommittee\s+of\s+union\s+and\s+progress\b",
    r"\bittihadist[s]?\b",
    r"\btalaat\b", r"\benver\b.*(?:pasha|ottoman)", r"\bcemal\b.*pasha",  # Three Pashas
    r"\bspecial\s+organi[sz]ation\b.*(?:ottoman|armenian)",
    r"\bte[sş]kilat[- ]?[iı]\s*mahsusa\b",                  # Teşkilât-ı Mahsusa
    r"\bdeath\s*march\b.*(?:armenian|deir|syrian\s*desert)",
    r"\barmenian\s*(?:question|reform)\b",
    r"\bberlin\s*(?:congress|treaty)\b.*armenian",
    r"\b1878\b.*(?:armenian|berlin|san\s*stefano)",
    r"\bsan\s*stefano\b.*armenian",
    r"\bhunchakian\s*demonstrat\b",                          # 1890 Kum Kapi demo
    r"\bkum\s*kap[iı]\b",
    r"\bottoman\s*bank\s*(?:takeover|siege|raid)\b",         # 1896 bank seizure

    # ===================================================================
    # Modern conflict & diplomacy
    # ===================================================================
    r"\bazerbaijan\b.*(?:armenia|ceasefire|border|peace|corridor)",
    r"\bturkey\b.*(?:armenia|border|protocol|normali[sz])",
    r"\bzangezur\s*corridor\b", r"\bpeace\s*treaty\b.*(?:armenia|baku|aliyev)",
    r"\blavrov\b.*(?:armenia|caucasus)", r"\bminsk\s*group\b",
    r"\b44[- ]?day\s*war\b", r"\b2020\s*(?:war|ceasefire|nagorno)\b",
    r"\bseptember\s*2023\b.*(?:artsakh|karabakh|ethnic\s*cleans)",

    # ===================================================================
    # Diaspora & church — with western transliterations
    # ===================================================================
    r"\barmenian[- ]?diaspora\b", r"\barmenian[- ]?apostolic\b",
    r"\betchmiadzin\b", r"\bechmiadz[iy]n\b", r"\bcatholic[ao]ss?(?:ate)?\b",
    r"\bkarekin\b", r"\bgaregin\b",
    r"\baram\s+i\b",
    r"\bantelias\b", r"\bcilicia\b.*(?:catholicosate|armenian)",
    r"\bkhachkar\b", r"\bkhatchkar\b",
    r"\bduduk\b", r"\btoudouk\b",
    r"\blavash\b",
    r"\barak[ae]l\b.*(?:church|patriarch)",
    r"\barmenian[- ]?evangelical\b",
    r"\barmenian[- ]?catholic\b",
    r"\barmenian[- ]?protestant\b",

    # ===================================================================
    # South Caucasus context
    # ===================================================================
    r"\bsouth[- ]?caucasus\b", r"\bcaucasus\b.*armenian",

    # ===================================================================
    # Armenian Jerusalem / heritage under threat
    # ===================================================================
    r"\barmenian[- ]?quarter\b", r"\barmenian[- ]?patriarch",
    r"\bjerusalem\b.*armenian", r"\barmenian\b.*jerusalem",
    r"\bcows[- ]?garden\b", r"\bkovun?\s*bah[cç]e\b",
    r"\bxotorjur\b",

    # ===================================================================
    # Western Armenia — historical regions & cities
    # ===================================================================
    r"\bwestern\s+armenia\b",
    r"\beastern\s+anatolia\b.*armenian",
    r"\bvan\b.*(?:armenian|massacre|province|church|lake)",
    r"\bbitlis\b", r"\bpaghesh\b",
    r"\bmus[h]?\b.*(?:armenian|plain)", r"\bmush\b",
    r"\berzurum\b", r"\bkarin\b",
    r"\bersinga\b", r"\berzincan\b", r"\berzingan\b",
    r"\btrebizond\b", r"\btrabzon\b", r"\btrapezunt\b",
    r"\bkharpert\b", r"\bharput\b", r"\belaz[iı]g\b",
    r"\bmarash\b", r"\bmaras\b", r"\bgermanicia\b",
    r"\badana\b.*armenian", r"\barmenian\b.*adana",
    r"\bsis\b.*(?:catholicosate|armenian|cilicia)",
    r"\btarsus\b.*armenian",
    r"\bcessarea\b", r"\bkayseri\b", r"\bgessaria\b",
    r"\bakn\b", r"\bkemaliye\b",
    r"\barapkir\b",
    r"\bsivas\b.*armenian", r"\bsepastia\b",
    r"\btokat\b.*armenian",
    r"\btigranakert\b", r"\bdiarbek[iı]r\b", r"\bamida\b",
    r"\burfa\b.*armenian", r"\bedessa\b.*armenian",
    r"\bantep\b", r"\baintab\b",
    r"\bzeytun\b",
    r"\bhadjin\b", r"\bhajin\b",
    r"\bdortyol\b", r"\bd[oö]rtyol\b",
    r"\bsamson\b.*armenian", r"\bsamsun\b.*armenian",

    # ===================================================================
    # Heritage sites — churches, monasteries, archaeological sites
    # ===================================================================
    # Inside modern Armenia
    r"\bgarni\b", r"\bgeghard\b",
    r"\bnoravank\b",
    r"\btatev\b",
    r"\bhaghpat\b", r"\bsanahin\b",
    r"\bkhor\s*virap\b",
    r"\bzvart?nots\b", r"\bzvart?notz\b",
    r"\bamberd\b",
    r"\blake\s*sevan\b",
    r"\bsaghmosavank\b", r"\bhovhannavank\b",

    # In Western Armenia / Turkey (destroyed or at risk)
    r"\bani\b.*(?:ruins?|cathedral|armenian|mediev|citadel)",
    r"\bakhtamar\b", r"\bakdamar\b",              # Holy Cross Church, Lake Van
    r"\bsurb\s+khach\b",                           # Holy Cross
    r"\bsurp\s+giragos\b", r"\bsurp\s+kirakos\b", # Diyarbakir church
    r"\bsurb\s+giragos\b",
    r"\bvaragavank\b",
    r"\bnarekavank\b", r"\bnarek\s+monastery\b",
    r"\bsurb\s+karapet\b",                         # Mush
    r"\bargina\b.*(?:monastery|armenian)",
    r"\btekor\b",
    r"\bkecharis\b",
    r"\bdadivank\b", r"\bdadi\s*vank\b",           # Artsakh
    r"\bghazanchetsots\b",                          # Shushi cathedral
    r"\btsitsernavank\b",
    r"\bamaras\b.*(?:monastery|armenian)",

    # Diaspora heritage
    r"\b40\s*days\s*of\s*musa\s*dagh\b",
    r"\bmusa\s*dagh\b", r"\bmusa\s*ler\b", r"\bmusaler\b",
    r"\bdeir\s*[ez]+[- ]?zor\b",
    r"\bmontebello\b.*(?:armenian|genocide\s*memorial)",

    # ===================================================================
    # ARF / Dashnak — ALL variant spellings
    # ===================================================================
    r"\bdashnaktsutyun\b", r"\btashnagtzoutioun\b",        # E. vs W. spelling
    r"\btashnagtsoutioun\b",
    r"\bdashnak(?:ist|s|utyun)?\b",
    r"\btashnak\b", r"\btashnag\b",
    r"\btashbag\b",
    r"\barf\b.*(?:dashnak|tashna[gk]|armenian|party)",

    # Other parties & orgs
    r"\bramkavar\b", r"\bramgavar\b",                       # E. vs W.
    r"\bhnchak(?:ian)?\b", r"\bhenchag(?:ian)?\b",          # E. vs W.
    r"\banca\b", r"\barmenian\s+national\s+committee\b",
    r"\bassembly\s+of\s+armenians\b", r"\barmenian\s+assembly\b",
    r"\bagbu\b",                                             # Armenian General Benevolent Union
    r"\bharootioun\b.*armenian", r"\bhomenetmen\b",
    r"\bhayortyats\b", r"\bhaigazian\b",
    r"\bhamazkayin\b",
    r"\barmenian\s+relief\s+society\b", r"\bars\b.*armenian",
    r"\barmenian\s+youth\s+federation\b", r"\bayf\b.*armenian",
    r"\barmenian\s+missionary\s+association\b",

    # ===================================================================
    # Diaspora events & commemorations
    # ===================================================================
    r"\barmenian\s+heritage\s+month\b",
    r"\bapril\s*24\b.*(?:commem|march|vigil|rally|genocide)",
    r"\barmenian\s+(?:food|culture|heritage|film)\s+festival\b",
    r"\barmenian\s+(?:genocide|martyrs)\s+(?:memorial|monument|museum)\b",
    r"\btsitsernakaberd\b",                                    # Yerevan genocide memorial
    r"\barmenian\s+(?:independence|flag)\s+day\b",
    r"\bsardarabad\b", r"\bsardarapat\b",                     # E. vs W.
    r"\bmay\s*28\b.*(?:armenia|republic|independence)",
    r"\bfirst\s+republic\b.*armenia",
    r"\barmenian\s+book\s+day\b",
    r"\bargentine[- ]?armenian\b.*(?:communit|event|march)",
    r"\blebanese[- ]?armenian\b",
    r"\bsyrian[- ]?armenian\b",
    r"\biranian[- ]?armenian\b",
    r"\bfrench[- ]?armenian\b",
    r"\brussian[- ]?armenian\b",
    r"\bcanadian[- ]?armenian\b",
    r"\baustrali(?:an)?[- ]?armenian\b",
    r"\bbrazilian[- ]?armenian\b",
    r"\buruguayan[- ]?armenian\b",

    # ===================================================================
    # Prominent western diaspora figures (‑ian surnames)
    # ===================================================================
    # Business / philanthropy
    r"\bmanoogian\b",                                        # Alex Manoogian (Masco)
    r"\bkerkorian\b",                                        # Kirk Kerkorian
    r"\bhovnanian\b",                                        # Hovnanian Enterprises
    r"\bharoutounian\b",
    r"\bboghossian\b",                                       # Albert Boghossian (jeweler)
    r"\beurnekian\b",                                        # Eduardo Eurnekian (Argentina)

    # Politics / activism / public life
    r"\bkrikorian\b",                                        # several diaspora activists
    r"\bderian\b",                                           # Abp. Vicken Aykazian/Derian
    r"\bchobanian\b",                                        # Archag Chobanian
    r"\byelda\b.*armenian",
    r"\bdink\b",                                             # Hrant Dink
    r"\bpamboukian\b",
    r"\bderounian\b",                                        # Steven Derounian (US Congressman)
    r"\bdeukme[dj]ian\b",                                    # George Deukmejian (CA Governor)
    r"\bsaroyan\b", r"\bsaroian\b",                          # William Saroyan
    r"\bgorky\b.*armenian", r"\barshile\s+gorky\b",

    # UK / Western Armenian Centre
    r"\bmisak\s+(?:manushian|manouchian)\b",                 # Missak Manouchian
    r"\bmanouchian\b", r"\bmanushian\b",
    r"\bwestern\s+armenian\s+centre\b",
    r"\bhra[iy]r\s+hawk\b",                                  # Hrair Hawk Khatcherian
    r"\bkhatch?erian\b",
    r"\blondon\b.*armenian", r"\barmenian\b.*london",
    r"\buk\b.*armenian", r"\barmenian\b.*(?:united\s+kingdom|britain)",

    # Arts & culture (western diaspora)
    r"\bchar(?:les)?\s+aznavour\b", r"\baznavour\b",
    r"\bdjivan\s+gaspar[iy]an\b", r"\bgaspar[iy]an\b",
    r"\bserj\s+tankian\b", r"\btankian\b",
    r"\bsystem\s+of\s+a\s+down\b",
    r"\bsher\b.*(?:armenian|halfbreed)", r"\bcher\b.*armenian",
    r"\bkardashian\b",
    r"\beric\s+bogos[iy]an\b", r"\bbogos[iy]an\b",
    r"\batom\s+egoyan\b", r"\begoyan\b",
    r"\bpeter\s+bala[gk]ian\b", r"\bbala[gk]ian\b",
    r"\bvahan\s+tekeyan\b", r"\bteke[iy]an\b",
    r"\bdaniel\s+varoujan\b", r"\bvaroujan\b",
    r"\bsiamanto\b",
    r"\bkomitas\b", r"\bgomidas\b",                          # E. vs W.
    r"\bhovhannes\s+shiraz\b", r"\bhovhanness?\b.*poet",
    r"\bparajanov\b", r"\bparajanian\b",
    r"\bharoutioun\s+muratian\b",
    r"\bmourad[iy]an\b",
    r"\bgregory\s+(?:david\s+)?roberts\b",                   # Half-Armenian author
    r"\bnora\s+armani\b",

    # Academics & intellectuals
    r"\btaner\s+ak[cç]am\b",                                 # Genocide scholar
    r"\bak[cç]am\b",
    r"\braymond\s+k[eé]vork[iy]an\b", r"\bk[eé]vork[iy]an\b",
    r"\bvahakn\s+dadrian\b", r"\bdadrian\b",
    r"\brichard\s+hovann[iy]s[iy]an\b", r"\bhovannisian\b",

    # ===================================================================
    # Mount Ararat (cultural symbol)
    # ===================================================================
    r"\bmount\s+ararat\b", r"\bararat\b.*(?:armenia|symbolic|sacred)",
    r"\bmasis\b",                                              # Armenian name for Ararat
    r"\bagri\s*dagh?\b",
]

_ARMENIAN_PATTERN: re.Pattern[str] = re.compile(
    "|".join(ARMENIAN_KEYWORDS), re.IGNORECASE
)


def _matches_armenian_keywords(text: str) -> bool:
    """Return True if *text* contains at least one Armenian-related keyword."""
    return bool(_ARMENIAN_PATTERN.search(text))


# ---------------------------------------------------------------------------
# Blocked & duplicate source filters for Google News aggregator
# ---------------------------------------------------------------------------

# State-sponsored / propaganda outlets — Russia, Azerbaijan, Turkey, Georgia
BLOCKED_SOURCES: set[str] = {
    # Russia
    "rt", "russia today", "rt.com", "sputnik", "sputniknews",
    "tass", "ria novosti", "ria news", "interfax",
    "rossiyskaya gazeta", "izvestia", "kommersant",
    # Azerbaijan
    "azernews", "azertag", "apa.az", "report.az", "caliber.az",
    "trend.az", "news.az", "latest news from azerbaijan",
    "baku research institute", "caspian news",
    "day.az", "axar.az", "haqqin.az",
    # Turkey
    "trt", "trt world", "trt haber", "anadolu agency",
    "daily sabah", "türkiye today", "turkiye today",
    "yeni safak", "yeni şafak", "turkish minute",
    # Georgia (state-sponsored)
    "georgia today", "1tv.ge", "georgian journal",
    "agenda.ge",
}

# Sources we already scrape directly — skip duplicates from Google News
DUPLICATE_SOURCES: set[str] = {
    "armenpress", "asbarez", "the armenian weekly", "armenian weekly",
    "azatutyun", "radio free europe", "rfe/rl",
    "hetq", "hetq.am", "panorama.am",
    "evn report", "oc media", "civilnet",
    "massis post", "the armenian mirror-spectator", "armenian mirror-spectator",
    "mirror-spectator", "mirrorspectator",
    "horizon weekly", "agos",
    "euronews", "euronews.com",
    "france 24", "al jazeera", "al-monitor",
    "bbc", "bbc world", "bbc news",
    "deutsche welle", "dw",
}

_BLOCKED_PATTERN: re.Pattern[str] = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in BLOCKED_SOURCES) + r")\s*$",
    re.IGNORECASE,
)

_DUPLICATE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:" + "|".join(re.escape(s) for s in DUPLICATE_SOURCES) + r")\s*$",
    re.IGNORECASE,
)


def _is_blocked_source(title: str) -> bool:
    """Check if a Google News title ends with a blocked source name."""
    # Google News titles look like: "Headline text - Source Name"
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    source = parts[-1].strip()
    return bool(_BLOCKED_PATTERN.search(source))


def _is_duplicate_source(title: str) -> bool:
    """Check if a Google News title ends with a source we already scrape."""
    parts = title.rsplit(" - ", 1)
    if len(parts) < 2:
        return False
    source = parts[-1].strip()
    return bool(_DUPLICATE_PATTERN.search(source))


class KeywordFilteredRSSScraper(RSSNewsScraper):
    """
    RSS scraper that **only** keeps articles matching Armenian-related
    keywords in their title or summary.  Used for large international feeds
    (BBC, Al Jazeera, France 24 …) where only a fraction of output is
    relevant to the Armenian beat.
    """

    def scrape(self) -> list[ScrapedArticle]:
        all_articles = super().scrape()
        filtered = [
            a for a in all_articles
            if _matches_armenian_keywords(a.title)
            or _matches_armenian_keywords(a.summary)
        ]
        logger.info(
            f"[{self.name}] Keyword filter: {len(filtered)}/{len(all_articles)} "
            "articles matched Armenian keywords."
        )
        return filtered


# ---------------------------------------------------------------------------
# Named scrapers (thin wrappers for discoverability / future customisation)
# ---------------------------------------------------------------------------

class ArmenPressScraper(RSSNewsScraper):
    SOURCE_NAME = "Armenpress"
    BASE_URL = "https://armenpress.am/eng/news/"
    RSS_URL = "https://armenpress.am/eng/rss/news/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class AsbarezScraper(RSSNewsScraper):
    SOURCE_NAME = "Asbarez"
    BASE_URL = "https://asbarez.com"
    RSS_URL = "https://asbarez.com/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class ArmenianWeeklyScraper(RSSNewsScraper):
    SOURCE_NAME = "Armenian Weekly"
    BASE_URL = "https://armenianweekly.com"
    RSS_URL = "https://armenianweekly.com/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class AzatutyunScraper(RSSNewsScraper):
    SOURCE_NAME = "Azatutyun (RFE/RL Armenia)"
    BASE_URL = "https://www.azatutyun.am"
    RSS_URL = "https://www.azatutyun.am/api/zijrreypui"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class HetqScraper(RSSNewsScraper):
    SOURCE_NAME = "Hetq"
    BASE_URL = "https://hetq.am/en/news"
    RSS_URL = "https://hetq.am/en/rss"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "investigative")


class PanoramaScraper(RSSNewsScraper):
    SOURCE_NAME = "Panorama.am"
    BASE_URL = "https://www.panorama.am/en/news/"
    RSS_URL = "https://www.panorama.am/en/rss/news.xml"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class EVNReportScraper(RSSNewsScraper):
    SOURCE_NAME = "EVN Report"
    BASE_URL = "https://evnreport.com"
    RSS_URL = "https://evnreport.com/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "analysis")


class OCMediaScraper(RSSNewsScraper):
    SOURCE_NAME = "OC Media"
    BASE_URL = "https://oc-media.org"
    RSS_URL = "https://oc-media.org/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "news")


class CivilnetScraper(RSSNewsScraper):
    SOURCE_NAME = "Civilnet"
    BASE_URL = "https://www.civilnet.am/en/"
    RSS_URL = "https://www.civilnet.am/en/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "culture")


# ---------------------------------------------------------------------------
# Diaspora sources
# ---------------------------------------------------------------------------

class MassisPostScraper(RSSNewsScraper):
    """Massis Post — Los Angeles-based Armenian diaspora news."""
    SOURCE_NAME = "Massis Post"
    BASE_URL = "https://massispost.com"
    RSS_URL = "https://massispost.com/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "diaspora")


class MirrorSpectatorScraper(RSSNewsScraper):
    """Armenian Mirror-Spectator — Boston/Watertown, oldest Armenian weekly in the US."""
    SOURCE_NAME = "Armenian Mirror-Spectator"
    BASE_URL = "https://mirrorspectator.com"
    RSS_URL = "https://mirrorspectator.com/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "diaspora")


class HorizonWeeklyScraper(RSSNewsScraper):
    """Horizon Weekly — Canada's ARF Armenian weekly publication."""
    SOURCE_NAME = "Horizon Weekly"
    BASE_URL = "https://horizonweekly.ca"
    RSS_URL = "https://horizonweekly.ca/feed/"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "diaspora")


class AgosScraper(RSSNewsScraper):
    """Agos — Istanbul Armenian bilingual newspaper (English section)."""
    SOURCE_NAME = "Agos"
    BASE_URL = "https://www.agos.com.tr/en"
    RSS_URL = "https://www.agos.com.tr/en/rss"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "diaspora")


# ---------------------------------------------------------------------------
# International / regional keyword-filtered sources
# ---------------------------------------------------------------------------

class GoogleNewsArmenianScraper(RSSNewsScraper):
    """
    Google News pre-filtered RSS for 'Armenia OR Armenian'.
    Already keyword-filtered by Google, so uses plain RSSNewsScraper.
    Aggregates coverage from NYT, Jerusalem Post, Reuters, CFR, etc.

    Applies two extra filters:
    - **Blocked**: removes state-sponsored media from Russia, Azerbaijan,
      Turkey, and Georgia.
    - **Dedup**: removes articles from sources we already scrape directly
      (Armenian Weekly, Hetq, Euronews, etc.).
    """
    SOURCE_NAME = "Google News - Armenia"
    BASE_URL = "https://news.google.com"
    RSS_URL = (
        "https://news.google.com/rss/search?"
        "q=Armenia+OR+Armenian+OR+Artsakh+OR+Karabakh&hl=en-US&gl=US&ceid=US:en"
    )

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")

    def scrape(self) -> list[ScrapedArticle]:
        all_articles = super().scrape()
        clean: list[ScrapedArticle] = []
        blocked_count = 0
        dup_count = 0
        for a in all_articles:
            if _is_blocked_source(a.title):
                blocked_count += 1
                continue
            if _is_duplicate_source(a.title):
                dup_count += 1
                continue
            clean.append(a)
        logger.info(
            f"[{self.name}] Source filter: kept {len(clean)}/{len(all_articles)} "
            f"(blocked={blocked_count}, duplicate={dup_count})."
        )
        return clean


class AlJazeeraScraper(KeywordFilteredRSSScraper):
    """Al Jazeera English — Middle East focused, keyword-filtered for Armenian content."""
    SOURCE_NAME = "Al Jazeera (Armenian)"
    BASE_URL = "https://www.aljazeera.com"
    RSS_URL = "https://www.aljazeera.com/xml/rss/all.xml"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


class AlMonitorScraper(KeywordFilteredRSSScraper):
    """Al-Monitor — Middle East policy news, keyword-filtered for Armenian content."""
    SOURCE_NAME = "Al-Monitor (Armenian)"
    BASE_URL = "https://www.al-monitor.com"
    RSS_URL = "https://www.al-monitor.com/rss"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


class BBCWorldScraper(KeywordFilteredRSSScraper):
    """BBC World News — keyword-filtered for Armenian content."""
    SOURCE_NAME = "BBC World (Armenian)"
    BASE_URL = "https://www.bbc.co.uk/news/world"
    RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


class France24Scraper(KeywordFilteredRSSScraper):
    """France 24 English — EU/international news, keyword-filtered for Armenian content."""
    SOURCE_NAME = "France 24 (Armenian)"
    BASE_URL = "https://www.france24.com/en/"
    RSS_URL = "https://www.france24.com/en/rss"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


class DWWorldScraper(KeywordFilteredRSSScraper):
    """Deutsche Welle — German international broadcaster, keyword-filtered for Armenian content."""
    SOURCE_NAME = "Deutsche Welle (Armenian)"
    BASE_URL = "https://www.dw.com/en/"
    RSS_URL = "https://rss.dw.com/xml/rss-en-world"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


class EuronewsScraper(KeywordFilteredRSSScraper):
    """Euronews — pan-European news, keyword-filtered for Armenian content."""
    SOURCE_NAME = "Euronews (Armenian)"
    BASE_URL = "https://www.euronews.com"
    RSS_URL = "https://www.euronews.com/rss"

    def __init__(self):
        super().__init__(self.SOURCE_NAME, self.BASE_URL, self.RSS_URL, "international")


# ---------------------------------------------------------------------------
# Registry — used by the scraping service to iterate all news sources
# ---------------------------------------------------------------------------

ALL_NEWS_SCRAPERS = [
    # Armenia-based
    ArmenPressScraper,
    AsbarezScraper,
    ArmenianWeeklyScraper,
    AzatutyunScraper,
    HetqScraper,
    PanoramaScraper,
    EVNReportScraper,
    OCMediaScraper,
    CivilnetScraper,
    # Diaspora
    MassisPostScraper,
    MirrorSpectatorScraper,
    HorizonWeeklyScraper,
    AgosScraper,
    # International / regional (keyword-filtered)
    GoogleNewsArmenianScraper,
    AlJazeeraScraper,
    AlMonitorScraper,
    BBCWorldScraper,
    France24Scraper,
    DWWorldScraper,
    EuronewsScraper,
]
