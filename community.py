"""What the person and a theme see: the VP Chat list, the small VPC Weekly list that carries
the ``vp-weekly`` tag, and the ``vpc`` and ``vpc_weekly`` entries.

VPinFE tags the game of every row of a tagged list, so the tag lives on its own list that
holds only this week's game. VP Chat holds every game with scores.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from common.extensions.contract import Unavailable

from . import boards, client, settings

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")

TAG = "vp-weekly"
WEEKLY = "weekly"
CHAT = "vp_chat"
WEEKLY_ENTRY = "vpc_weekly"
CHAT_ENTRY = "vpc"
ENTRY_TOP = 25  # lines of each board handed to a theme, besides the flagged player's own


def _iso(stamp) -> str:
    try:
        moment = datetime.fromtimestamp(float(stamp), timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return ""
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _local(stamp) -> str:
    try:
        return datetime.fromtimestamp(float(stamp)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


def install(ctx, store, refresher) -> None:
    def names() -> set[str]:
        return settings.usernames(ctx)

    def line(item: dict) -> dict:
        key = "pane.score.label.mine" if item["mine"] else "pane.score.label"
        return {"label": ctx.t(key, rank=item["rank"], player=item.get("player") or "?"),
                "under": client.grouped(item.get("score"))}

    def week_versions(week: dict) -> list[dict]:
        return [{"vps_release_id": week.get("vps_release_id") or "", "version": "",
                 "table": week.get("table") or "", "page": week.get("page") or "",
                 "scores": week.get("scores") or []}]

    # --- VP Chat ----------------------------------------------------------------------

    def chat_row(vps_id: str, name: str, versions: list[dict], fetched, weekly: bool,
                 refreshable: bool, flagged: set[str]) -> dict:
        everyone = [one for version in versions for one in version.get("scores") or []]
        best = max(everyone, key=lambda one: one.get("score") or 0) if everyone else None
        yours = boards.mine(versions, flagged)
        return {
            "id": vps_id, "vps_id": vps_id, "name": name,
            "weekly": "●" if weekly else "",
            # Text, not numbers: a number column cannot draw thousands separators.
            "top_score": client.grouped(best["score"]) if best else "",
            "top_player": best["player"] if best else "",
            "mine": "●" if yours else "",  # a dot, since a state column always draws a word
            "my_best": client.grouped(max(one["score"] for one in yours)) if yours else "",
            "my_rank": yours[0]["rank"] if yours else None,
            "entries": len(everyone),
            "fetched": _iso(fetched),
            "refreshable": refreshable,
        }

    def chat_rows() -> list[dict]:
        flagged = names()
        week = store.week()
        week_game = week["game"] if week else ""
        rows, shown = [], set()
        for vps_id, held in store.games().items():
            if not held.get("versions") and vps_id != week_game:
                continue
            versions = held.get("versions") or []
            if vps_id == week_game and not versions:
                versions = week_versions(week)
            rows.append(chat_row(vps_id, held.get("name") or "", versions,
                                 held.get("fetched_at"), vps_id == week_game, True, flagged))
            shown.add(vps_id)
        if week_game and week_game not in shown:
            rows.append(chat_row(week_game, week.get("table") or "", week_versions(week),
                                 store.week_read_at, True, False, flagged))
        return rows

    def chat_detail(row_id):
        flagged = names()
        week = store.week()
        held = store.game(str(row_id))
        is_week = bool(week and week["game"] == str(row_id))
        versions = (held or {}).get("versions") or []
        if not held and not is_week:
            return None
        sections = []
        if is_week:
            board = boards.ranked(week.get("scores") or [], flagged)
            sections.append({"key": "week", "label": ctx.t("pane.week.scores", week=week.get(
                "week") or "?"), "rows": [line(one) for one in board]
                or [{"label": ctx.t("pane.scores.none")}]})
        for index, version in enumerate(versions):
            board = boards.ranked(version.get("scores") or [], flagged)
            shown = [{"label": ctx.t("pane.gap")} if one is None else line(one)
                     for one in boards.window(board)]
            sections.append({
                "key": f"v{index}",
                "label": ctx.t("pane.version", version=version.get("version") or "?",
                               count=len(board)),
                "rows": shown or [{"label": ctx.t("pane.scores.none")}]})
        facts = []
        page = next((one["page"] for one in versions if one.get("page")), "") or (
            (week or {}).get("page") if is_week else "")
        if page:
            facts.append({"label": ctx.t("pane.table"), "kind": "link",
                          "value": ctx.t("pane.table.open"), "to": page})
        if held and held.get("fetched_at"):
            facts.append({"label": ctx.t("pane.fetched"), "kind": "date",
                          "value": _iso(held["fetched_at"])})
        if facts:
            sections.append({"key": "about", "label": ctx.t("pane.about"), "facts": facts})
        name = (held or {}).get("name") or (week or {}).get("table") or str(row_id)
        return {"title": name, "under": ctx.t("pane.under.chat"), "sections": sections}

    def status():
        count = sum(1 for held in store.games().values() if held.get("versions"))
        when = _local(store.week_read_at) or "-"
        text = ctx.t("list.vp_chat.status", when=when, count=count)
        if not names():
            return {"text": f"{text} · {ctx.t('list.vp_chat.status.no_name')}", "to": "settings"}
        return text

    def check_now() -> str:
        try:
            refresher.ensure_week(force=True)
        except Unavailable as exc:
            return ctx.t("act.check_now.failed", why=str(exc))
        return ctx.t("act.check_now.done", count=refresher.request_all())

    def refresh_rows(rows) -> str:
        queued = 0
        for row in rows:
            held = store.game(str(row.get("id") or ""))
            if held and refresher.request({"vps_id": str(row["id"]), **held}, force=True):
                queued += 1
        return ctx.t("verb.refresh.done", count=queued)

    chat_columns = [
        {"field": "vps_id", "kind": "game", "name_from": "name"},
        {"field": "weekly"},
        {"field": "top_score"},
        {"field": "top_player"},
        {"field": "mine"},
        {"field": "my_best"},
        {"field": "my_rank", "kind": "number"},
        {"field": "entries", "kind": "number"},
        {"field": "fetched", "kind": "date"},
    ]
    ctx.ui.list(
        CHAT, chat_rows, title="VP Chat", area="community", icon="leaderboard",
        columns=chat_columns,
        views=[
            {"key": "all", "sort": [{"field": "weekly", "desc": True},
                              {"field": "fetched", "desc": True}]},
            {"key": "mine", "columns": ["vps_id", "my_best", "my_rank", "entries", "top_score"],
             "sort": [{"field": "my_rank"}]},
        ],
        status=status, acts={"check_now": check_now, "open_site": client.SITE},
        verbs=[{"key": "refresh", "run": refresh_rows, "needs": "refreshable"}],
        detail=chat_detail,
    )

    # --- VPC Weekly: the list that carries the tag ------------------------------------

    def weekly_rows() -> list[dict]:
        week = refresher.ensure_week()
        if not week:
            return []
        release = str(week["vps_release_id"])
        return [{"id": release, "vps_id": week["game"], "name": week.get("table") or release,
                 "week": week.get("week"), "starts": week.get("starts"),
                 "ends": week.get("ends"), "page": week.get("page") or ""}]

    def weekly_detail(row_id):
        """The pane beside the week's row: the week, then its scores."""
        week = store.week()
        if week is None or str(row_id) != str(week.get("vps_release_id")):
            return None
        board = boards.ranked(week.get("scores") or [], names())
        facts = [{"label": ctx.t("pane.game"), "kind": "game", "value": week["game"],
                  "says": week.get("table") or week["game"]}]
        if week.get("starts"):
            facts.append({"label": ctx.t("pane.starts"), "kind": "date",
                          "value": week["starts"]})
        if week.get("ends"):
            facts.append({"label": ctx.t("pane.ends"), "kind": "date", "value": week["ends"]})
        if week.get("page"):
            facts.append({"label": ctx.t("pane.table"), "kind": "link",
                          "value": ctx.t("pane.table.open"), "to": week["page"]})
        return {
            "title": week.get("table") or week["game"],
            "under": ctx.t("pane.under", week=week.get("week") or "?"),
            "sections": [
                {"key": "scores", "label": ctx.t("pane.scores"),
                 "rows": [line(one) for one in board]
                 or [{"label": ctx.t("pane.scores.none")}]},
                {"key": "week", "label": ctx.t("pane.week"), "facts": facts},
            ],
        }

    ctx.ui.list(
        WEEKLY, weekly_rows, area="community", tag=TAG,
        columns=[
            {"field": "vps_id", "kind": "game", "name_from": "name"},
            {"field": "week", "kind": "number"},
            {"field": "ends", "kind": "date"},
            {"field": "page", "kind": "link"},
        ],
        acts={"check_now": check_now},
        detail=weekly_detail,
    )

    # --- what a theme reads -----------------------------------------------------------

    def for_weekly(game):
        week = store.week()
        if not week or not week.get("game") or str(game.get("vps_id") or "") != week["game"]:
            return None
        board = boards.ranked(week.get("scores") or [], names())
        return {"week": week.get("week"), "starts": week.get("starts"),
                "ends": week.get("ends"), "table": week.get("table") or "",
                "vps_release_id": week.get("vps_release_id") or "",
                "page": week.get("page") or "", "scores": board}

    def for_game(game):
        vps_id = str(game.get("vps_id") or "")
        if not vps_id:
            return None
        if store.needs_refresh(vps_id, refresher.ttl_for(vps_id)):
            refresher.request({"vps_id": vps_id, "name": game.get("name"),
                               "manufacturer": game.get("manufacturer"),
                               "year": game.get("year")})
        held = store.game(vps_id)
        if not held or not held.get("versions"):
            return None
        flagged = names()
        versions = []
        for version in held["versions"]:
            board = boards.ranked(version.get("scores") or [], flagged)
            versions.append({
                "vps_release_id": version.get("vps_release_id") or "",
                "version": version.get("version") or "",
                "authors": version.get("authors") or "",
                "page": version.get("page") or "",
                "entries": len(board),
                "scores": [one for index, one in enumerate(board)
                           if index < ENTRY_TOP or one["mine"]],
            })
        return {"versions": versions, "mine": boards.mine(held["versions"], flagged),
                "fetched": _iso(held.get("fetched_at"))}

    ctx.entries.contribute(WEEKLY_ENTRY, for_weekly)
    ctx.entries.contribute(CHAT_ENTRY, for_game)
