"""
news_risk.py
------------
Macro risk awareness layer for the senior analyst system.

Fetches financial news from Finnhub and Google News RSS for a given week,
then classifies macro risk level using an LLM-style keyword + scoring approach.

For live use:    fetch current week headlines → classify → adjust pick count
For backtest:    fetch historical week headlines via Finnhub date filter

Risk levels:
    LOW      → normal 5 picks
    MEDIUM   → 3 picks, prefer defensive sectors
    HIGH     → 2 picks max, ACCUMULATING only
    EXTREME  → skip week entirely
"""

import os
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional

# ── Config ────────────────────────────────────────────────────────────────────
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
CACHE_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                           "data", "predictor", "macro_risk_cache")

DEFENSIVE_SECTORS   = ["XLU", "XLP", "XLV", "XLB"]   # safe in risk-off
RISK_OFF_SECTORS    = ["XLK", "XLY", "XLRE", "XLC"]   # high beta, avoid

# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class Headline:
    source:   str
    headline: str
    date:     str
    tags:     List[str] = field(default_factory=list)


@dataclass
class MacroRisk:
    level:           str          # LOW | MEDIUM | HIGH | EXTREME
    reasoning:       str
    sectors_at_risk: List[str]
    safe_sectors:    List[str]
    top_headlines:   List[str]
    signal_counts:   dict


RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "EXTREME"]


# ── Headline fetching ──────────────────────────────────────────────────────────
def _fetch_finnhub_spy_news(date_from: str, date_to: str) -> List[Headline]:
    """Fetch SPY-tagged news from Finnhub for a date range (backtest or live)."""
    if not FINNHUB_KEY:
        return []
    url = (f"https://finnhub.io/api/v1/company-news?symbol=SPY"
           f"&from={date_from}&to={date_to}&token={FINNHUB_KEY}")
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.loads(r.read())
        return [Headline(source=a.get("source", ""),
                         headline=a.get("headline", ""),
                         date=a.get("datetime", ""))
                for a in data if a.get("headline")]
    except Exception as e:
        print(f"[news_risk] Finnhub fetch failed: {e}")
        return []


def _fetch_finnhub_general_news() -> List[Headline]:
    """Fetch current general market news from Finnhub (live use)."""
    if not FINNHUB_KEY:
        return []
    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=12) as r:
            data = json.loads(r.read())
        return [Headline(source=a.get("source", ""),
                         headline=a.get("headline", ""),
                         date=str(a.get("datetime", "")))
                for a in data if a.get("headline")]
    except Exception as e:
        print(f"[news_risk] Finnhub general fetch failed: {e}")
        return []


def _fetch_google_news_rss(query: str, max_items: int = 20) -> List[Headline]:
    """Fetch Google News RSS for a keyword query — no API key needed."""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = root.findall(".//item")[:max_items]
        results = []
        for item in items:
            title   = item.findtext("title", "")
            source  = item.findtext("source", "Google News")
            pub     = item.findtext("pubDate", "")
            results.append(Headline(source=source, headline=title, date=pub))
        return results
    except Exception as e:
        print(f"[news_risk] Google News RSS failed for '{query}': {e}")
        return []


def _fetch_marketwatch_rss() -> List[Headline]:
    """Fetch MarketWatch top stories RSS — no API key needed."""
    url = "https://feeds.marketwatch.com/marketwatch/topstories/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = root.findall(".//item")[:30]
        results = []
        for item in items:
            title  = item.findtext("title", "")
            source = "MarketWatch"
            pub    = item.findtext("pubDate", "")
            results.append(Headline(source=source, headline=title, date=pub))
        return results
    except Exception as e:
        print(f"[news_risk] MarketWatch RSS failed: {e}")
        return []


# ── Tag / classify headlines ───────────────────────────────────────────────────
# Keyword map → tag → base risk weight
KEYWORD_TAGS = {
    "TARIFF":      (["tariff", "trade war", "import duty", "section 122", "ieepa",
                     "trade policy", "reciprocal", "trade sanction"], 3),
    "FED":         (["federal reserve", "fomc", "interest rate", "rate hike",
                     "rate cut", "powell", "hawkish", "dovish", "inflation"], 2),
    "GEOPOLITICAL":(["war", "military", "iran", "strait of hormuz", "nuclear",
                     "china conflict", "taiwan strait", "sanctions", "attack"], 4),
    "OIL_SHOCK":   (["oil price", "crude oil", "opec", "energy shock",
                     "gasoline price", "oil supply", "wti", "brent"], 3),
    "RECESSION":   (["recession", "gdp contraction", "stagflation", "job loss",
                     "unemployment surge", "yield curve inversion", "credit crunch"], 4),
    "CREDIT_STRESS":(["credit default", "bank failure", "bank run", "withdrawal",
                      "private credit", "hedge fund", "margin call", "liquidity"], 3),
    "MARKET_CRASH": (["market crash", "black monday", "circuit breaker", "selloff",
                      "panic selling", "dow falls", "s&p 500 drop", "breadth collapse",
                      "deteriorating", "risk-off"], 3),
    "VOLATILITY":  (["vix", "volatility spike", "fear index", "uncertainty"], 2),
    "EARNINGS":    (["earnings season", "guidance cut", "revenue miss",
                     "earnings miss", "warning"], 1),
}


def _tag_headline(headline: str) -> List[str]:
    text = headline.lower()
    tags = []
    for tag, (keywords, _) in KEYWORD_TAGS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def _tag_all(headlines: List[Headline]) -> List[Headline]:
    for h in headlines:
        h.tags = _tag_headline(h.headline)
    return headlines


# ── Risk scoring ───────────────────────────────────────────────────────────────
def _score_headlines(headlines: List[Headline]) -> dict:
    """Count how many headlines fire each risk tag."""
    counts = {tag: 0 for tag in KEYWORD_TAGS}
    for h in headlines:
        for tag in h.tags:
            counts[tag] += 1
    return counts


def _determine_risk_level(counts: dict, total_headlines: int) -> tuple:
    """
    Returns (level, reasoning, sectors_at_risk, safe_sectors).

    Thresholds normalize against total article count to distinguish
    active crisis from background geopolitical noise (e.g. routine
    Iran/Taiwan mentions fire 'war' keyword but don't mean a crash).

    Logic:
    - EXTREME: geo >= 15% of headlines AND >= 15 absolute (active conflict dominating
               coverage), OR recession >= 5, OR tariff >= 8 AND crash >= 4
    - HIGH:    tariff >= 5 OR oil >= 5 OR credit >= 5 OR crash >= 6
               OR (geo_pct >= 8% AND tariff >= 3) [geo + trade combo]
    - MEDIUM:  tariff >= 3 OR fed >= 5 OR vol >= 4 OR 3+ categories firing at >= 3
    - LOW:     otherwise
    """
    geo       = counts.get("GEOPOLITICAL", 0)
    tariff    = counts.get("TARIFF", 0)
    recession = counts.get("RECESSION", 0)
    oil       = counts.get("OIL_SHOCK", 0)
    credit    = counts.get("CREDIT_STRESS", 0)
    crash     = counts.get("MARKET_CRASH", 0)
    fed       = counts.get("FED", 0)
    vol       = counts.get("VOLATILITY", 0)

    geo_pct      = (geo / total_headlines * 100) if total_headlines > 0 else 0
    active_risks = [t for t, c in counts.items() if c >= 4]
    sectors_at_risk = []
    safe_sectors    = list(DEFENSIVE_SECTORS)

    # EXTREME: active military conflict dominating news coverage, or major tariff + crash combo
    if (geo >= 15 and geo_pct >= 15) or recession >= 6 or (tariff >= 20 and crash >= 4):
        level     = "EXTREME"
        reasoning = (
            f"Severe macro disruption detected: "
            f"{'geopolitical conflict (' + str(geo) + ' signals, ' + f'{geo_pct:.0f}% of coverage), ' if geo >= 15 else ''}"
            f"{'recession risk (' + str(recession) + ' signals), ' if recession >= 5 else ''}"
            f"{'tariff shock + market panic, ' if tariff >= 8 and crash >= 4 else ''}"
            f"capital preservation required."
        ).strip(", ").rstrip(", ") + "."
        sectors_at_risk = RISK_OFF_SECTORS + ["XLI", "XLE"]
        safe_sectors    = ["XLU", "XLP", "XLV"]
        return level, reasoning, sectors_at_risk, safe_sectors

    # HIGH: tariff escalation, oil shock, credit stress, or breadth breakdown
    if tariff >= 10 or oil >= 6 or credit >= 6 or crash >= 7 or (geo_pct >= 8 and tariff >= 6):
        level = "HIGH"
        parts = []
        if tariff >= 5:                   parts.append(f"tariff escalation ({tariff} signals)")
        if oil >= 5:                      parts.append(f"oil/energy shock ({oil} signals)")
        if credit >= 5:                   parts.append(f"credit stress ({credit} signals)")
        if crash >= 6:                    parts.append(f"market breadth breakdown ({crash} signals)")
        if geo_pct >= 8 and tariff >= 3:
            parts.append(f"geopolitical + trade risk ({geo_pct:.0f}% geo coverage)")
        reasoning = "Elevated macro risk: " + ", ".join(parts) + ". Reduce exposure significantly."
        sectors_at_risk = RISK_OFF_SECTORS
        safe_sectors    = ["XLU", "XLP", "XLV", "XLB"]
        return level, reasoning, sectors_at_risk, safe_sectors

    # MEDIUM: moderate tariff/Fed/volatility signals — reduce but don't stop trading
    if tariff >= 6 or fed >= 8 or vol >= 5 or len(active_risks) >= 3:
        level = "MEDIUM"
        parts = []
        if tariff >= 3:                  parts.append(f"trade policy uncertainty ({tariff} signals)")
        if fed >= 5:                     parts.append(f"Fed policy risk ({fed} signals)")
        if vol >= 4:                     parts.append(f"elevated volatility ({vol} signals)")
        if len(active_risks) >= 3 and not parts:
            parts.append(f"multiple risk themes: {', '.join(active_risks[:3])}")
        reasoning = "Moderate macro risk: " + ", ".join(parts) + ". Reduce to 3 picks, favor defensives."
        sectors_at_risk = ["XLRE", "XLC"]
        safe_sectors    = DEFENSIVE_SECTORS
        return level, reasoning, sectors_at_risk, safe_sectors

    # LOW
    level     = "LOW"
    reasoning = "No significant macro risk signals detected. Normal trading environment."
    return level, reasoning, [], DEFENSIVE_SECTORS


# ── Public API ────────────────────────────────────────────────────────────────
def fetch_macro_news(as_of_date: str,
                     lookback_days: int = 7) -> List[Headline]:
    """
    Fetch financial news headlines for the week ending as_of_date.

    as_of_date: 'YYYY-MM-DD' (Friday before entry Monday)
    Returns: list of Headline objects with tags populated.
    """
    dt_to   = datetime.strptime(as_of_date, "%Y-%m-%d")
    dt_from = dt_to - timedelta(days=lookback_days)
    date_from = dt_from.strftime("%Y-%m-%d")
    date_to   = as_of_date

    headlines: List[Headline] = []

    # Primary: Finnhub SPY news (date-filtered, works for historical weeks)
    finnhub_news = _fetch_finnhub_spy_news(date_from, date_to)
    headlines.extend(finnhub_news)
    print(f"[news_risk] Finnhub SPY news {date_from} to {date_to}: {len(finnhub_news)} articles")
    time.sleep(0.3)  # rate limit

    # Secondary: Google News RSS for specific risk topics (current weeks only)
    is_recent = (datetime.now() - dt_to).days < 30
    if is_recent:
        for query in ["US tariffs trade war", "Federal Reserve interest rates",
                      "stock market volatility VIX", "oil price shock geopolitical"]:
            rss_news = _fetch_google_news_rss(query, max_items=15)
            headlines.extend(rss_news)
            time.sleep(0.2)

        mw_news = _fetch_marketwatch_rss()
        headlines.extend(mw_news)

    # Deduplicate by headline text
    seen = set()
    unique = []
    for h in headlines:
        key = h.headline[:60].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(h)

    return _tag_all(unique)


def classify_macro_risk(headlines: List[Headline],
                        as_of_date: Optional[str] = None) -> MacroRisk:
    """
    Classify macro risk level from a list of tagged headlines.
    Returns MacroRisk with level, reasoning, sector guidance.
    """
    counts = _score_headlines(headlines)
    level, reasoning, sectors_at_risk, safe_sectors = _determine_risk_level(
        counts, len(headlines)
    )

    # Top headlines that triggered risk tags
    risk_headlines = [h.headline for h in headlines if h.tags]
    top_headlines  = risk_headlines[:8]

    result = MacroRisk(
        level=level,
        reasoning=reasoning,
        sectors_at_risk=sectors_at_risk,
        safe_sectors=safe_sectors,
        top_headlines=top_headlines,
        signal_counts={k: v for k, v in counts.items() if v > 0},
    )

    # Cache result to disk
    if as_of_date:
        _save_cache(as_of_date, result)

    return result


def get_macro_risk(as_of_date: str,
                   use_cache: bool = True) -> MacroRisk:
    """
    High-level entry point: fetch news + classify risk for a given week.
    Caches result to avoid redundant API calls during backtest.
    """
    if use_cache:
        cached = _load_cache(as_of_date)
        if cached:
            print(f"[news_risk] Using cached macro risk for {as_of_date}: {cached.level}")
            return cached

    headlines = fetch_macro_news(as_of_date)
    risk      = classify_macro_risk(headlines, as_of_date=as_of_date)
    print(f"[news_risk] {as_of_date}: {risk.level} — {risk.reasoning}")
    return risk


# ── Pick count policy ─────────────────────────────────────────────────────────
def get_max_picks(risk: MacroRisk) -> int:
    return {"LOW": 5, "MEDIUM": 3, "HIGH": 2, "EXTREME": 0}[risk.level]


def should_prefer_defensive(risk: MacroRisk) -> bool:
    return risk.level in ("MEDIUM", "HIGH", "EXTREME")


# ── Cache helpers ─────────────────────────────────────────────────────────────
def _cache_path(as_of_date: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"macro_risk_{as_of_date}.json")


def _save_cache(as_of_date: str, risk: MacroRisk):
    path = _cache_path(as_of_date)
    with open(path, "w") as f:
        json.dump({
            "as_of_date":     as_of_date,
            "level":          risk.level,
            "reasoning":      risk.reasoning,
            "sectors_at_risk": risk.sectors_at_risk,
            "safe_sectors":   risk.safe_sectors,
            "top_headlines":  risk.top_headlines,
            "signal_counts":  risk.signal_counts,
        }, f, indent=2)


def _load_cache(as_of_date: str) -> Optional[MacroRisk]:
    path = _cache_path(as_of_date)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        return MacroRisk(
            level=d.get("level") or d.get("risk_level", "LOW"),
            reasoning=d.get("reasoning", ""),
            sectors_at_risk=d.get("sectors_at_risk", []),
            safe_sectors=d.get("safe_sectors", []),
            top_headlines=d.get("top_headlines", []),
            signal_counts=d.get("signal_counts", d.get("signals", {})),
        )
    except Exception:
        return None


# ── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    print(f"\nFetching macro risk for week ending {date}...\n")
    risk = get_macro_risk(date, use_cache=False)
    print(f"\n{'='*60}")
    print(f"MACRO RISK: {risk.level}")
    print(f"Reasoning:  {risk.reasoning}")
    print(f"Max picks:  {get_max_picks(risk)}")
    print(f"Sectors at risk: {', '.join(risk.sectors_at_risk) or 'none'}")
    print(f"Safe sectors:    {', '.join(risk.safe_sectors)}")
    print(f"\nSignal counts: {risk.signal_counts}")
    print(f"\nTop risk headlines:")
    for h in risk.top_headlines[:6]:
        print(f"  - {h[:90]}")
