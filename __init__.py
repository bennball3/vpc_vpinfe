"""Virtual Pinball Chat: the current VPC weekly table and its scores.

- The VPC Weekly list (Community) names this week's game. Core tags that game with
  ``vp-weekly`` and moves the tag when the week changes, so only one game carries it at a time.
  Core reads the list shortly after start and every 30 minutes, which is also what keeps the
  scores fresh.
- Clicking the week's row opens a pane beside it with the week's leaderboard. Refresh on the
  page reads it again.
- A theme reads the week and its scores on the weekly game as ``entry.ext.vpc_weekly``.

VPC's ``vpsId`` names one table file (a VPS release), not the game, so it is resolved to its
game through the VPS catalog VPinFE already keeps on disk: the game is found from VPC's table
name, then confirmed by that release being one of the game's table files.
"""

import logging
import re
import threading
from datetime import datetime

import requests

from common.extensions.contract import Unavailable, get_json

CURRENT_WEEK = "https://virtualpinballchat.com/vpc/api/v1/currentWeek"
TAG = "vp-weekly"
WEEKLY = "weekly"
ENTRY_KEY = "vpc_weekly"

# "Medieval Madness (Williams 1997)" -> title, manufacturer, year
_TITLE = re.compile(r"^\s*(?P<title>.+?)\s*\((?P<maker>[^()]*?)\s*(?P<year>\d{4})\)\s*$")
# VPC writes a score's time as "11/06/2026 21:35:43" (month first).
_POSTED = "%m/%d/%Y %H:%M:%S"

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")


def _settle_row(table: str) -> dict:
    found = _TITLE.match(table or "")
    if not found:
        return {"title": (table or "").strip()}
    return {"title": found["title"], "manufacturer": found["maker"].strip(),
            "year": found["year"]}


def _posted(text) -> str:
    try:
        return datetime.strptime(str(text), _POSTED).isoformat()
    except (TypeError, ValueError):
        return str(text or "")


def _grouped(number) -> str:
    """129846820 -> "129,846,820"."""
    try:
        return f"{int(number):,}"
    except (TypeError, ValueError):
        return str(number or "")


def _score_rows(week: dict) -> list:
    rows = []
    for rank, one in enumerate(week.get("scores") or [], start=1):
        if not isinstance(one, dict):
            continue
        rows.append({
            "id": str(one.get("userId") or f"rank-{rank}"),
            "rank": rank,
            "player": one.get("username") or "",
            "avatar": one.get("userAvatarUrl") or "",
            "score": one.get("score"),
            "points": one.get("points"),
            "posted": _posted(one.get("posted")),
        })
    return rows


def register(ctx):
    games = ctx.games
    lock = threading.Lock()
    resolved: dict = {}  # VPC release id -> VPS game id, for the run
    # What a theme is handed: the weekly game's VPS id and the week with its scores.
    held = {"game": "", "week": None}

    def releases_of(game_vps_id: str) -> set:
        try:
            listed = games.vps_releases(game_vps_id, listed_as="tableFiles")
        except Exception:  # an id the catalog does not hold
            return set()
        return {str(one.get("vps_file_id") or "") for one in listed.get("releases") or []}

    def game_of(release_id: str, table: str) -> str:
        """The VPS game id `release_id` is a table file of, or "" where the catalog on disk
        cannot say."""
        if release_id in resolved:
            return resolved[release_id]
        found = ""
        if release_id in releases_of(release_id):
            found = release_id  # already a game id
        else:
            try:
                settled = games.vps_settle([_settle_row(table)])
            except Exception:
                logger.warning("Could not look up %r in the VPS catalog", table, exc_info=True)
                return ""
            answer = settled[0] if settled else {}
            candidates = [answer.get("vps_id") or ""]
            candidates += [one.get("id") or one.get("vps_id") or ""
                           for one in answer.get("candidates") or []]
            for candidate in filter(None, candidates):
                if release_id in releases_of(candidate):
                    found = candidate
                    break
        if found:
            resolved[release_id] = found
        else:
            logger.info("Release %s (%s) is not in the VPS catalog on disk", release_id, table)
        return found

    def hold(game: str, week) -> None:
        with lock:
            changed = (game, week) != (held["game"], held["week"])
            held["game"], held["week"] = game, week
        if changed:
            ctx.entries.stale(ENTRY_KEY)

    def read_week():
        """This week as VPC says it now, and the VPS game it is played on."""
        try:
            week = get_json(CURRENT_WEEK, timeout=15)
        except (requests.RequestException, ValueError) as exc:
            raise Unavailable(ctx.why(exc, at=CURRENT_WEEK)) from exc
        if not isinstance(week, dict) or not week.get("vpsId"):
            hold("", None)
            return None, ""
        release = str(week["vpsId"])
        game = game_of(release, str(week.get("table") or "")) or release
        hold(game, {
            "week": week.get("weekNumber"),
            "starts": week.get("periodStart"),
            "ends": week.get("periodEnd"),
            "table": week.get("table") or "",
            "vps_release_id": release,
            "page": week.get("tableUrl") or "",
            "scores": _score_rows(week),
        })
        return week, game

    def weekly():
        week, game = read_week()
        if week is None:
            return []
        release = str(week["vpsId"])
        return [{
            "id": release,
            "vps_id": game,
            "name": week.get("table") or release,
            "week": week.get("weekNumber"),
            "starts": week.get("periodStart"),
            "ends": week.get("periodEnd"),
            "page": week.get("tableUrl") or "",
            # Not a column: kept with the row so the theme has scores straight after a restart.
            "scores": _score_rows(week),
        }]

    def detail(row_id):
        """The pane beside the week's row: the week, then its scores."""
        with lock:
            game, week = held["game"], held["week"]
        if week is None or str(row_id) != week.get("vps_release_id"):
            return None
        facts = [{"label": ctx.t("pane.game"), "kind": "game", "value": game,
                  "says": week.get("table") or game}]
        if week.get("starts"):
            facts.append({"label": ctx.t("pane.starts"), "kind": "date",
                          "value": week["starts"]})
        if week.get("ends"):
            facts.append({"label": ctx.t("pane.ends"), "kind": "date", "value": week["ends"]})
        if week.get("page"):
            facts.append({"label": ctx.t("pane.table"), "kind": "link",
                          "value": ctx.t("pane.table.open"), "to": week["page"]})
        # The Manager draws each line as label | value: rank and player, then the score.
        lines = [{"label": ctx.t("pane.score.label", rank=one["rank"],
                                 player=one.get("player") or "?"),
                  "under": _grouped(one.get("score"))}
                 for one in week.get("scores") or []]
        if not lines:
            lines = [{"label": ctx.t("pane.scores.none")}]
        return {
            "title": week.get("table") or game,
            "under": ctx.t("pane.under", week=week.get("week") or "?"),
            "sections": [
                {"key": "scores", "label": ctx.t("pane.scores"), "rows": lines},
                {"key": "week", "label": ctx.t("pane.week"), "facts": facts},
            ],
        }

    def for_entry(game):
        with lock:
            if held["week"] is None or not held["game"]:
                return None
            if str(game.get("vps_id") or "") != held["game"]:
                return None
            return dict(held["week"])

    # Until core's first read after start, answer the theme from the last good read.
    kept_weekly = ctx.ui.kept(WEEKLY)
    if kept_weekly and kept_weekly.get("rows"):
        row = kept_weekly["rows"][0]
        held["game"] = str(row.get("vps_id") or "")
        held["week"] = {
            "week": row.get("week"), "starts": row.get("starts"), "ends": row.get("ends"),
            "table": row.get("name") or "", "vps_release_id": str(row.get("id") or ""),
            "page": row.get("page") or "",
            "scores": list(row.get("scores") or []),
        }

    ctx.entries.contribute(ENTRY_KEY, for_entry)

    ctx.ui.list(
        WEEKLY, weekly, area="community", tag=TAG,
        columns=[
            {"field": "vps_id", "kind": "game", "name_from": "name"},
            {"field": "week", "kind": "number"},
            {"field": "ends", "kind": "date"},
            {"field": "page", "kind": "link"},
        ],
        detail=detail,
    )
