#!/usr/bin/env python3
"""Build Alabama primary tracker data for the homepage.

Outputs: data/alabama_tracker.json
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List

from lxml import html as lxml_html

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "alabama_tracker.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

PRIMARY_DAY = "2026-05-19"

RACES = [
    {
        "id": "us_senate_gop",
        "name": "U.S. Senate (Republican Primary)",
        "page": "2026_United_States_Senate_election_in_Alabama",
        "headers_must_include": ["Poll source", "Date(s)", "Jared Hudson", "Steve Marshall", "Barry Moore"],
        "candidates": ["Steve Marshall", "Barry Moore", "Jared Hudson"],
    },
    {
        "id": "governor_gop",
        "name": "Governor (Republican Primary)",
        "page": "2026_Alabama_gubernatorial_election",
        "headers_must_include": ["Poll source", "Date(s)", "Ken McFeeters", "Tommy Tuberville"],
        "candidates": ["Tommy Tuberville", "Ken McFeeters"],
    },
    {
        "id": "lt_governor_gop",
        "name": "Lieutenant Governor (Republican Primary)",
        "page": "2026_Alabama_lieutenant_gubernatorial_election",
        "headers_must_include": ["Poll source", "Date(s)", "Wes Allen", "A.J. McCarron", "Rick Pate"],
        "candidates": ["Wes Allen", "A.J. McCarron", "Rick Pate", "Nicole Wadsworth", "John Wahl"],
    },
    {
        "id": "attorney_general_gop",
        "name": "Attorney General (Republican Primary)",
        "page": "2026_Alabama_Attorney_General_election",
        "headers_must_include": ["Poll source", "Date(s)", "Pamela Casey", "Jay Mitchell", "Katherine Robertson"],
        "candidates": ["Jay Mitchell", "Katherine Robertson", "Pamela Casey"],
    },
    {
        "id": "secretary_of_state_gop",
        "name": "Secretary of State (Republican Primary)",
        "page": "2026_Alabama_Secretary_of_State_election",
        "headers_must_include": ["Poll source", "Date(s)", "Caroleene Dobson", "Andrew Sorrell"],
        "candidates": ["Andrew Sorrell", "Caroleene Dobson"],
    },
    {
        "id": "al1_house_gop",
        "name": "AL-1 Congressional District (Republican Primary)",
        "page": "2026_United_States_House_of_Representatives_elections_in_Alabama",
        "headers_must_include": ["Poll source", "Date(s)", "Jerry Carl", "Rhett Marques"],
        "candidates": ["Jerry Carl", "Rhett Marques", "Jimmy Dees", "Joshua McKee", "John Mills", "James Richardson", "Austin Sidwell"],
    },
]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def clean_text(text: str) -> str:
    text = re.sub(r"\[[^\]]+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def as_float_percent(v: str) -> float | None:
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", v)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def extract_notes(doc: Any) -> Dict[str, str]:
    notes: Dict[str, str] = {}
    for li in doc.xpath("//li[starts-with(@id,'cite_note-')]"):
        note_id = li.attrib.get("id", "")
        links = li.xpath(".//a[starts-with(@href,'http')]/@href")
        if links:
            notes[note_id] = links[0]
    return notes


def find_table(doc: Any, must_include: List[str]) -> Any | None:
    for t in doc.xpath("//table[contains(@class,'wikitable')]"):
        headers = [clean_text(" ".join(th.xpath(".//text()"))) for th in t.xpath(".//tr[1]/th")]
        h = " | ".join(headers)
        if all(tok in h for tok in must_include):
            return t
    return None


def parse_table(table: Any, notes: Dict[str, str], target_candidates: List[str], race_id: str) -> Dict[str, Any]:
    headers = [clean_text(" ".join(th.xpath(".//text()"))) for th in table.xpath(".//tr[1]/th")]
    candidate_headers: List[str] = []
    for h in headers[4:]:
        if h.lower() in {"other", "undecided"}:
            break
        candidate_headers.append(h)

    # preserve requested display order where possible
    ordered_candidates = [c for c in target_candidates if c in candidate_headers]
    for c in candidate_headers:
        if c not in ordered_candidates:
            ordered_candidates.append(c)
    idx = [candidate_headers.index(c) for c in ordered_candidates]

    rows: List[Dict[str, Any]] = []
    for tr in table.xpath(".//tr[position()>1]"):
        tds = tr.xpath("./td")
        if len(tds) < 4 + len(candidate_headers):
            continue

        pollster = clean_text(" ".join(tds[0].xpath(".//text()")))
        if not pollster:
            continue

        date = clean_text(" ".join(tds[1].xpath(".//text()")))
        sample = clean_text(" ".join(tds[2].xpath(".//text()")))

        pollster_url = ""
        ref = tds[0].xpath(".//sup[contains(@class,'reference')]/a/@href")
        if ref and ref[0].startswith("#"):
            pollster_url = notes.get(ref[0][1:], "")

        raw_values = [clean_text(" ".join(td.xpath(".//text()"))) for td in tds[4:4 + len(candidate_headers)]]
        values = [raw_values[i] for i in idx]

        # exclude speculative AL-1 row per user request (Heather Moore not candidate)
        if race_id == "al1_house_gop" and "Heather Moore" in " ".join(headers):
            continue

        numeric = [as_float_percent(v) for v in values]
        spread = "—"
        if all(v is not None for v in numeric) and len(numeric) >= 2:
            max_val = max(numeric)
            winner_i = numeric.index(max_val)
            sorted_vals = sorted(numeric, reverse=True)
            lead = sorted_vals[0] - sorted_vals[1]
            winner = ordered_candidates[winner_i].split()[-1]
            spread = f"{winner} +{lead:.1f}".replace(".0", "")

        rows.append(
            {
                "pollster": re.sub(r"\s*\(R\)\s*$", "", pollster).strip(),
                "pollster_url": pollster_url,
                "date": date,
                "sample": sample,
                "values": values,
                "spread": spread,
            }
        )

    # keep most recent visible rows
    return {
        "headers": ordered_candidates,
        "rows": rows[:8],
    }


def build_snapshot(race_name: str, headers: List[str], rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return [f"No currently published polling table was found for {race_name}."]

    first = rows[0]
    vals = [as_float_percent(v) for v in first["values"]]
    bullets: List[str] = []

    if all(v is not None for v in vals) and len(vals) >= 2:
        winner_i = max(range(len(vals)), key=lambda i: vals[i])
        leader = headers[winner_i]
        bullets.append(f"{leader} leads the most recent published poll row ({first['spread']}).")
    else:
        bullets.append("The most recent poll row shows a fragmented field with no clear majority.")

    if len(rows) > 1:
        second = rows[1]
        bullets.append(f"Next-most-recent row is {second['pollster']} ({second['date']}, {second['sample']}).")

    if all(v is not None for v in vals) and max(vals) < 50:
        bullets.append("No candidate is near an outright majority in recent toplines, keeping runoff dynamics relevant.")
    else:
        bullets.append("Recent toplines show a clear front-runner advantage." )

    return bullets


def format_display_name(name: str) -> str:
    # compact candidate display in tables
    if name == "A.J. McCarron":
        return "McCarron"
    if name == "Steve Marshall":
        return "Marshall"
    if name == "Barry Moore":
        return "Moore"
    if name == "Jared Hudson":
        return "Hudson"
    if name == "Tommy Tuberville":
        return "Tuberville"
    if name == "Ken McFeeters":
        return "McFeeters"
    if name == "Jay Mitchell":
        return "Mitchell"
    if name == "Katherine Robertson":
        return "Robertson"
    if name == "Pamela Casey":
        return "Casey"
    if name == "Andrew Sorrell":
        return "Sorrell"
    if name == "Caroleene Dobson":
        return "Dobson"
    if name == "Jerry Carl":
        return "Carl"
    if name == "Rhett Marques":
        return "Marques"
    return name.split()[-1]


def build_race_entry(defn: Dict[str, Any]) -> Dict[str, Any]:
    api = (
        "https://en.wikipedia.org/w/api.php?action=parse"
        f"&page={urllib.parse.quote(defn['page'])}"
        "&prop=text&formatversion=2&format=json"
    )

    raw = fetch_json(api)
    html_text = raw.get("parse", {}).get("text", "")
    if not html_text:
        return {
            "id": defn["id"],
            "name": defn["name"],
            "snapshot": ["Polling data is not currently available from the configured source."],
            "columns": [],
            "polls": [],
        }

    doc = lxml_html.fromstring(html_text)
    notes = extract_notes(doc)
    table = find_table(doc, defn["headers_must_include"])
    if table is None:
        return {
            "id": defn["id"],
            "name": defn["name"],
            "snapshot": ["Polling table not found for this race on the source page."],
            "columns": [],
            "polls": [],
        }

    parsed = parse_table(table, notes, defn["candidates"], defn["id"])
    columns = [format_display_name(c) for c in parsed["headers"]]
    return {
        "id": defn["id"],
        "name": defn["name"],
        "snapshot": build_snapshot(defn["name"], parsed["headers"], parsed["rows"]),
        "columns": columns,
        "polls": parsed["rows"],
    }


def main() -> None:
    races = []
    for race in RACES:
        try:
            races.append(build_race_entry(race))
        except Exception:
            races.append(
                {
                    "id": race["id"],
                    "name": race["name"],
                    "snapshot": ["Unable to load this race in the current refresh."],
                    "columns": [],
                    "polls": [],
                }
            )

    payload = {
        "updated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "primary_day": PRIMARY_DAY,
        "races": races,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {OUT_PATH} with {len(races)} races")


if __name__ == "__main__":
    main()
