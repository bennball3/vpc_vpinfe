"""Virtual Pinball Chat's API: what is asked of it and how its answers are read.

Nothing here keeps state. Every call is one request, and a failure to reach the site is an
``Unavailable`` so core says so as the service's failure.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import datetime, timezone

import requests

from common.extensions.contract import Unavailable, get_json, why

BASE = "https://virtualpinballchat.com/vpc/api/v1"
CURRENT_WEEK = f"{BASE}/currentWeek"
FUZZY = f"{BASE}/scoresByTableAndAuthorUsingFuzzyTableSearch"
SITE = "https://virtualpinballchat.com"
TIMEOUT = 20

# "Medieval Madness (Williams 1997)" -> title, manufacturer, year
_TITLE = re.compile(r"^\s*(?P<title>.+?)\s*\((?P<maker>[^()]*?)\s*(?P<year>\d{4})\)\s*$")
# The weekly board writes a score's time month first; the others write ISO 8601.
_POSTED = "%m/%d/%Y %H:%M:%S"


def settle_row(table: str) -> dict:
    """The row VPS settling wants for a VPC table name."""
    found = _TITLE.match(table or "")
    if not found:
        return {"title": (table or "").strip()}
    return {"title": found["title"], "manufacturer": found["maker"].strip(),
            "year": found["year"]}


def posted(text) -> str:
    """A score's time as ISO 8601, whichever way VPC wrote it; what it said if neither."""
    said = str(text or "")
    try:
        return datetime.strptime(said, _POSTED).isoformat()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(said.replace("Z", "+00:00")).astimezone(
            timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    except ValueError:
        return said


def grouped(number) -> str:
    """129846820 -> "129,846,820"."""
    try:
        return f"{int(number):,}"
    except (TypeError, ValueError):
        return str(number or "")


def slim(scores) -> list[dict]:
    """Scores as kept: the player, the score and when, best first. The Discord profile VPC
    sends with each one is dropped, since it is most of the weight."""
    kept = []
    for one in scores or []:
        if not isinstance(one, dict):
            continue
        user = one.get("user") if isinstance(one.get("user"), dict) else {}
        player = one.get("userName") or one.get("username") or user.get("username") or ""
        kept.append({
            "player": str(player),
            "score": one.get("score") if isinstance(one.get("score"), (int, float)) else 0,
            "posted": posted(one.get("posted")),
            "url": str(one.get("postUrl") or ""),
        })
    kept.sort(key=lambda one: one["score"], reverse=True)
    return kept


def _get(url: str):
    try:
        return get_json(url, timeout=TIMEOUT)
    except (requests.RequestException, ValueError) as exc:
        raise Unavailable(why(exc, at=url)) from exc


def current_week() -> dict | None:
    """This week as VPC says it now, or None where it names no table."""
    week = _get(CURRENT_WEEK)
    if not isinstance(week, dict) or not week.get("vpsId"):
        return None
    return week


def game_versions(term: str) -> list[dict]:
    """Every VPC version a fuzzy search for `term` finds, with its scores, as VPC sent them."""
    found = _get(f"{FUZZY}?{urllib.parse.urlencode({'tableSearchTerm': term})}")
    return [one for one in found if isinstance(one, dict)] if isinstance(found, list) else []


def version(raw: dict) -> dict:
    """One version of a table as kept."""
    return {
        "vps_release_id": str(raw.get("vpsId") or ""),
        "table": str(raw.get("tableName") or ""),
        "version": str(raw.get("versionNumber") or ""),
        "authors": str(raw.get("authorName") or ""),
        "page": str(raw.get("tableUrl") or ""),
        "scores": slim(raw.get("scores")),
    }
