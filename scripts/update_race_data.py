#!/usr/bin/env python3
"""Refreshes swing-Senate race data for the website.

Data sources:
- Cook Political Report (race ratings)
- NCSL (state primary dates)
- Polymarket + Kalshi (market odds, when available)
- Wikipedia election pages + RealClearPolitics links (polling aggregator references)
- Google News RSS (recent storylines)
"""

from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "races.json"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

DEFAULT_SWING = {
    "NH": {"state_name": "New Hampshire", "cook_rating": "Lean Democrat"},
    "GA": {"state_name": "Georgia", "cook_rating": "Toss Up"},
    "ME": {"state_name": "Maine", "cook_rating": "Toss Up"},
    "MI": {"state_name": "Michigan", "cook_rating": "Toss Up"},
    "NC": {"state_name": "North Carolina", "cook_rating": "Toss Up"},
    "AK": {"state_name": "Alaska", "cook_rating": "Lean Republican"},
    "OH": {"state_name": "Ohio", "cook_rating": "Lean Republican"},
}

DEFAULT_PRIMARY_DATES = {
    "AK": "August 18, 2026",
    "GA": "May 19, 2026",
    "ME": "June 9, 2026",
    "MI": "August 4, 2026",
    "NC": "March 3, 2026",
    "NH": "September 8, 2026",
    "OH": "May 5, 2026",
}

DEFAULT_POLL_TOPLINES = {
    "GA": [
        {
            "contest": "2026 Georgia Senate",
            "race_name": "2026 Georgia Senate - Republican Primary",
            "candidates": ["Collins", "Carter", "Dooley"],
            "polls": [
                {"pollster": "RCP Average", "date": "7/28 - 2/18", "sample": "—", "values": ["29.5", "17.8", "10.3"], "spread": "Collins +11.7"},
                {"pollster": "Quantus Insights", "date": "2/17 - 2/18", "sample": "1337 LV", "values": ["36", "11", "9"], "spread": "Collins +25"},
                {"pollster": "InsiderAdvantage/Rosetta", "date": "12/18 - 12/19", "sample": "1000 LV", "values": ["25", "20", "12"], "spread": "Collins +5"},
                {"pollster": "Atlanta Journal-Constitution", "date": "10/13 - 10/21", "sample": "1000 LV", "values": ["30", "20", "12"], "spread": "Collins +10"},
                {"pollster": "TIPP**", "date": "7/28 - 8/1", "sample": "RV", "values": ["27", "20", "8"], "spread": "Collins +7"},
            ],
        }
    ]
}

# 2026 Senate election map coverage (regular + expected specials surfaced in ratings).
ALL_SENATE_ELECTION_STATES = [
    "AL", "AK", "AR", "CO", "DE", "GA", "ID", "IL", "IA", "KS", "KY", "LA",
    "ME", "MA", "MI", "MN", "MS", "MT", "NE", "NH", "NJ", "NM", "NC", "OH",
    "OK", "OR", "RI", "SC", "SD", "TN", "TX", "VA", "WV", "WY",
]

# Fallback primary dates for 2026 Senate-election states. Live NCSL parsing overrides these when available.
ALL_DEFAULT_PRIMARY_DATES = {
    "AL": "May 19, 2026",
    "AK": "August 18, 2026",
    "AR": "March 3, 2026",
    "CO": "June 30, 2026",
    "DE": "September 10, 2026",
    "GA": "May 19, 2026",
    "ID": "May 19, 2026",
    "IL": "March 17, 2026",
    "IA": "June 2, 2026",
    "KS": "August 4, 2026",
    "KY": "May 19, 2026",
    "LA": "November 3, 2026",
    "ME": "June 9, 2026",
    "MA": "September 8, 2026",
    "MI": "August 4, 2026",
    "MN": "August 11, 2026",
    "MS": "March 10, 2026",
    "MT": "June 2, 2026",
    "NE": "May 12, 2026",
    "NH": "September 8, 2026",
    "NJ": "June 2, 2026",
    "NM": "June 2, 2026",
    "NC": "March 3, 2026",
    "OH": "May 5, 2026",
    "OK": "June 16, 2026",
    "OR": "May 19, 2026",
    "RI": "September 8, 2026",
    "SC": "June 9, 2026",
    "SD": "June 2, 2026",
    "TN": "August 6, 2026",
    "TX": "March 3, 2026",
    "VA": "June 16, 2026",
    "WV": "May 12, 2026",
    "WY": "August 18, 2026",
}

STATE_TO_CODE = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
    "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def parse_cook_swing() -> Dict[str, Dict[str, str]]:
    url = "https://www.cookpolitical.com/ratings/senate-race-ratings"
    try:
        raw = fetch_text(url)
        text = re.sub(r"<[^>]+>", " ", raw)
        text = html.unescape(re.sub(r"\s+", " ", text))

        out: Dict[str, Dict[str, str]] = {}

        section_patterns = [
            ("Lean D", "Toss Up", "Lean Democrat"),
            ("Toss Up", "Lean R", "Toss Up"),
            ("Lean R", "Likely R", "Lean Republican"),
        ]

        for start, end, label in section_patterns:
            m = re.search(start + r"(.*?)" + end, text, flags=re.IGNORECASE)
            if not m:
                continue
            chunk = m.group(1)
            for st, candidate in re.findall(r"\b([A-Z]{2})\s+([A-Za-z\-’' ]{2,35})\b", chunk):
                if st in STATE_TO_CODE.values():
                    out[st] = {"state_name": code_to_name(st), "cook_rating": label}

        if len(out) >= 4:
            return out
    except Exception:
        pass
    return DEFAULT_SWING.copy()


def code_to_name(code: str) -> str:
    for state_name, c in STATE_TO_CODE.items():
        if c == code:
            return state_name
    return code


def parse_ncsl_primary_dates() -> Dict[str, str]:
    url = "https://www.ncsl.org/elections-and-campaigns/2026-state-primary-election-dates"
    dates: Dict[str, str] = {}
    try:
        raw = fetch_text(url)
        # Matches table rows like: <td>Georgia</td><td>05/19/2026</td>
        for state_name, date_val in re.findall(r">([A-Za-z ]+)</td>\s*<td>\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*</td>", raw):
            state_name = html.unescape(state_name.strip())
            if state_name in STATE_TO_CODE:
                code = STATE_TO_CODE[state_name]
                dates[code] = fmt_mmddyyyy(date_val)
    except Exception:
        pass
    merged = ALL_DEFAULT_PRIMARY_DATES.copy()
    merged.update(dates)
    return merged


def fmt_mmddyyyy(mmddyyyy: str) -> str:
    month, day, year = mmddyyyy.split("/")
    d = dt.date(int(year), int(month), int(day))
    return d.strftime("%B %-d, %Y")


def maybe_parse_price(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
        if x > 1:
            x = x / 100.0
        return max(0.0, min(1.0, x))
    except Exception:
        return None


def extract_poly_price(mkt: Dict[str, Any]) -> float | None:
    if isinstance(mkt.get("outcomePrices"), str):
        try:
            arr = json.loads(mkt["outcomePrices"])
            if isinstance(arr, list) and arr:
                return maybe_parse_price(arr[0])
        except Exception:
            pass
    if isinstance(mkt.get("outcomePrices"), list) and mkt["outcomePrices"]:
        return maybe_parse_price(mkt["outcomePrices"][0])
    return maybe_parse_price(mkt.get("lastTradePrice"))


def get_polymarket(state_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        markets = fetch_json("https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=1000")
        candidates = []
        for mkt in markets:
            title = str(mkt.get("question") or mkt.get("title") or "")
            lo = title.lower()
            if "senate" in lo and state_name.lower() in lo and ("primary" in lo or "nomination" in lo):
                candidates.append(mkt)
        candidates = sorted(candidates, key=lambda x: float(x.get("liquidity", 0) or 0), reverse=True)[:4]
        for mkt in candidates:
            slug = mkt.get("slug")
            url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"
            out.append(
                {
                    "title": str(mkt.get("question") or mkt.get("title") or "Market"),
                    "yes_price": extract_poly_price(mkt),
                    "url": url,
                }
            )
    except Exception:
        pass
    return out


def get_kalshi(state_name: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    endpoints = [
        "https://api.elections.kalshi.com/trade-api/v2/markets?limit=1000",
        "https://trading-api.kalshi.com/trade-api/v2/markets?limit=1000",
    ]
    for endpoint in endpoints:
        try:
            payload = fetch_json(endpoint)
            markets = payload.get("markets") if isinstance(payload, dict) else payload
            if not isinstance(markets, list):
                continue
            filtered = []
            for mkt in markets:
                title = str(mkt.get("title") or mkt.get("subtitle") or mkt.get("ticker") or "")
                lo = title.lower()
                if "senate" in lo and state_name.lower() in lo and ("primary" in lo or "nomination" in lo):
                    filtered.append(mkt)
            filtered = filtered[:4]
            for mkt in filtered:
                yes_price = maybe_parse_price(mkt.get("yes_ask") or mkt.get("yes_bid") or mkt.get("last_price"))
                ticker = str(mkt.get("ticker") or "")
                url = f"https://kalshi.com/markets/{ticker}" if ticker else "https://kalshi.com/markets"
                out.append(
                    {
                        "title": str(mkt.get("title") or mkt.get("subtitle") or ticker or "Market"),
                        "yes_price": yes_price,
                        "url": url,
                    }
                )
            if out:
                return out
        except Exception:
            continue
    return out


def get_polling_refs(state_name: str) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    wiki_title = f"2026_United_States_Senate_election_in_{state_name.replace(' ', '_')}"
    wiki_url = f"https://en.wikipedia.org/wiki/{wiki_title}"

    try:
        page = fetch_text(wiki_url)
        if "RealClearPolitics" in page:
            refs.append({"source": "RealClearPolitics", "value": "See aggregate on race page", "url": wiki_url})
        if "Race to the WH" in page or "RaceToTheWH" in page:
            refs.append({"source": "Race to the WH", "value": "See aggregate on race page", "url": wiki_url})
        if "Decision Desk HQ" in page:
            refs.append({"source": "Decision Desk HQ", "value": "See aggregate on race page", "url": wiki_url})
    except Exception:
        pass

    rcp_query = urllib.parse.quote(f"{state_name} senate race polls 2026 realclearpolitics")
    race_to_wh_query = urllib.parse.quote(f"{state_name} senate race 2026 polling")
    ddhq_query = urllib.parse.quote(f"{state_name} senate race 2026 polling aggregate")

    refs.append(
        {
            "source": "RealClearPolitics",
            "value": "Latest polling links",
            "url": f"https://www.realclearpolitics.com/search/?q={rcp_query}",
        }
    )
    refs.append(
        {
            "source": "Race to the WH",
            "value": "Polling + forecast search",
            "url": f"https://www.racetothewh.com/search?q={race_to_wh_query}",
        }
    )
    refs.append(
        {
            "source": "Decision Desk HQ",
            "value": "Polling aggregate search",
            "url": f"https://duckduckgo.com/?q=site%3Adecisiondeskhq.com+{ddhq_query}",
        }
    )
    return refs


def parse_rss(url: str, state_name: str, limit: int = 5) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    raw = fetch_text(url)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        return out

    for item in channel.findall("item")[:limit]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source_name = source_el.text.strip() if source_el is not None and source_el.text else ""

        if " - " in title:
            title = title.split(" - ", 1)[0]
        if title.startswith("CDATA["):
            title = title.replace("CDATA[", "").rstrip("]")

        title_l = title.lower()
        state_l = state_name.lower()
        if state_l not in title_l:
            continue

        date_fmt = ""
        if pub_date:
            try:
                parsed = email.utils.parsedate_to_datetime(pub_date)
                date_fmt = parsed.date().isoformat()
            except Exception:
                date_fmt = pub_date

        if title and link:
            out.append(
                {
                    "point": title,
                    "date": date_fmt,
                    "source": source_name,
                    "url": link,
                }
            )
    return out


def get_storylines(state_name: str) -> List[Dict[str, str]]:
    query = urllib.parse.quote(f"{state_name} Senate race 2026 primary")
    google_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    bing_url = f"https://www.bing.com/news/search?q={query}&format=RSS"
    out: List[Dict[str, str]] = []
    seen: set[str] = set()

    for feed_url in [google_url, bing_url]:
        try:
            items = parse_rss(feed_url, state_name=state_name, limit=12)
            for item in items:
                key = item["point"].lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
                if len(out) >= 4:
                    break
            if len(out) >= 4:
                break
        except Exception:
            continue

    if not out:
        out = [
            {
                "point": f"Track the latest {state_name} Senate primary coverage (Google News).",
                "date": "",
                "source": "Google News",
                "url": f"https://news.google.com/search?q={query}&hl=en-US&gl=US&ceid=US%3Aen",
            },
            {
                "point": f"Track the latest {state_name} Senate primary coverage (Bing News).",
                "date": "",
                "source": "Bing News",
                "url": f"https://www.bing.com/news/search?q={query}",
            },
            {
                "point": f"Review campaign reporting and updates for the {state_name} race.",
                "date": "",
                "source": "News search",
                "url": f"https://duckduckgo.com/?q={query}",
            },
        ]

    return out


def get_poll_toplines(state_code: str) -> List[Dict[str, Any]]:
    rows = DEFAULT_POLL_TOPLINES.get(state_code, [])
    return json.loads(json.dumps(rows))


def parse_float(value: Any) -> float | None:
    try:
        return float(str(value).strip().replace("%", ""))
    except Exception:
        return None


def summarize_race(state_code: str, state_name: str, cook_rating: str, polls_toplines: List[Dict[str, Any]], odds: Dict[str, Any]) -> List[str]:
    bullets: List[str] = []

    if polls_toplines and polls_toplines[0].get("polls"):
        block = polls_toplines[0]
        candidates = block.get("candidates", [])
        rows = block.get("polls", [])
        avg = rows[0]
        values = [parse_float(v) for v in avg.get("values", [])]

        leader = ""
        if values and candidates and all(v is not None for v in values):
            max_idx = max(range(len(values)), key=lambda i: float(values[i]))
            leader = candidates[max_idx]
            bullets.append(
                f"Polling toplines show {leader} ahead in the {state_name} Republican primary (RCP Average: {avg.get('spread', 'lead noted')})."
            )

        if len(rows) > 1:
            latest = rows[1]
            bullets.append(
                f"Latest listed survey is {latest.get('pollster')} ({latest.get('date')}, {latest.get('sample')}), showing {latest.get('spread')}."
            )

        if leader:
            bullets.append(
                f"Across listed polls, {leader} leads each release, indicating a clear name-recognition and vote-intent advantage at this stage."
            )
    else:
        bullets.append(f"{state_name} is currently rated {cook_rating} by Cook Political Report.")
        bullets.append("No standardized primary topline table has been loaded yet for this race page.")

    poly_n = len(odds.get("polymarket", []))
    kalshi_n = len(odds.get("kalshi", []))
    if poly_n + kalshi_n > 0:
        bullets.append(f"Prediction market coverage is active ({poly_n} Polymarket / {kalshi_n} Kalshi listings currently matched).")
    else:
        bullets.append("Prediction market activity for this specific primary appears limited or not yet listed in the matched feeds.")

    bullets.append("Fundraising toplines are not yet integrated in this release; adding FEC candidate receipts/disbursements is the next data upgrade.")
    return bullets


def main() -> None:
    cook = parse_cook_swing()
    primary_dates = parse_ncsl_primary_dates()

    swing_states: List[Dict[str, Any]] = []
    for code, info in sorted(cook.items(), key=lambda kv: kv[0]):
        state_name = info["state_name"]
        odds = {
            "polymarket": get_polymarket(state_name),
            "kalshi": get_kalshi(state_name),
        }
        polls_toplines = get_poll_toplines(code)
        swing_states.append(
            {
                "state": code,
                "state_name": state_name,
                "cook_rating": info["cook_rating"],
                "primary_date": primary_dates.get(code, "Not available"),
                "odds": odds,
                "polls_toplines": polls_toplines,
                "polls": get_polling_refs(state_name),
                "storylines": get_storylines(state_name),
                "race_summary": summarize_race(code, state_name, info["cook_rating"], polls_toplines, odds),
            }
        )

    senate_map_states: List[Dict[str, Any]] = []
    for code in ALL_SENATE_ELECTION_STATES:
        state_name = code_to_name(code)
        swing_info = cook.get(code)
        senate_map_states.append(
            {
                "state": code,
                "state_name": state_name,
                "primary_date": primary_dates.get(code, "Not available"),
                "competitive": bool(swing_info),
                "cook_rating": swing_info["cook_rating"] if swing_info else "Not rated competitive",
            }
        )

    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "refresh_target": "24-48 hours",
        "sources": {
            "cook": "https://www.cookpolitical.com/ratings/senate-race-ratings",
            "ncsl": "https://www.ncsl.org/elections-and-campaigns/2026-state-primary-election-dates",
            "polymarket": "https://polymarket.com",
            "kalshi": "https://kalshi.com",
            "polls": "https://www.realclearpolitics.com",
            "news": "https://news.google.com",
        },
        "senate_election_states": senate_map_states,
        "swing_states": swing_states,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {OUT_PATH} with {len(swing_states)} states")


if __name__ == "__main__":
    main()
