"""Asking VPC for scores, only as they are wanted.

The week is read when its setting says it is due. A game's scores are read one game at a time
on a single worker thread: a game browsed to, a game just played, or the games the person asks
to check. There is no crawl of VPC's tables.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from common.extensions.contract import Unavailable

from . import client, library, settings

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")

PACE_SECONDS = 1.0  # between two games asked of VPC
RETRY_SECONDS = 15 * 60  # before a game VPC could not answer for is asked again
IDLE_SECONDS = 30  # the worker leaves after this long with nothing to do
WEEK_SLACK = 120  # core's ticks are not exact


class Refresher:
    def __init__(self, ctx, store, lib: library.Library) -> None:
        self._ctx = ctx
        self._store = store
        self._library = lib
        self._cv = threading.Condition()
        self._queue: deque[dict] = deque()
        self._pending: set[str] = set()
        self._failed: dict[str, float] = {}
        self._thread: threading.Thread | None = None
        self._week_read = False  # whether the week was read in this run
        self._week_lock = threading.Lock()

    # --- the week ---------------------------------------------------------------------

    def week_due(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if not self._week_read:
            return True
        interval = settings.week_interval(self._ctx)
        if interval is None:
            return False
        return now - self._store.week_read_at >= interval - WEEK_SLACK

    def ensure_week(self, force: bool = False) -> dict | None:
        """This week as held, read from VPC first when it is due (or `force`). Raises
        Unavailable where VPC is due to be asked and does not answer."""
        with self._week_lock:
            if force or self.week_due():
                self._read_week()
            return self._store.week()

    def _read_week(self) -> None:
        raw = client.current_week()
        if raw is None:
            changed = self._store.set_week(None)
        else:
            release = str(raw["vpsId"])
            game = self._library.game_of(release, str(raw.get("table") or "")) or release
            board = client.slim(raw.get("scores"))
            changed = self._store.set_week({
                "game": game,
                "week": raw.get("weekNumber"),
                "starts": raw.get("periodStart"),
                "ends": raw.get("periodEnd"),
                "table": raw.get("table") or "",
                "vps_release_id": release,
                "page": raw.get("tableUrl") or "",
                "scores": board,
            })
        self._week_read = True
        self._store.flush()
        if changed:
            self._ctx.entries.stale("vpc_weekly")
            self._ctx.entries.stale("vpc")

    # --- games ------------------------------------------------------------------------

    def ttl_for(self, vps_id: str) -> float:
        """How long a game's scores are kept: the weekly game follows the week's schedule,
        every other game the (much longer) keep setting."""
        keep = settings.keep_for(self._ctx)
        week = self._store.week()
        if week and week.get("game") == vps_id:
            interval = settings.week_interval(self._ctx)
            return keep if interval is None else min(keep, interval)
        return keep

    def request(self, game: dict, force: bool = False) -> bool:
        """Queue a game to be asked of VPC. False where it is queued already, was refused a
        moment ago, or has nothing to search by."""
        vps_id = str(game.get("vps_id") or "")
        if not vps_id or not library.search_terms(game):
            return False
        with self._cv:
            if vps_id in self._pending:
                return False
            if not force and self._failed.get(vps_id, 0) > time.time():
                return False
            self._pending.add(vps_id)
            self._queue.append(dict(game))
            if self._thread is None:
                self._thread = threading.Thread(target=self._work, name="vpc-scores",
                                                daemon=True)
                self._thread.start()
            self._cv.notify()
        return True

    def request_all(self) -> int:
        """Queue every game held to be asked again."""
        queued = 0
        for vps_id, held in self._store.games().items():
            if self.request({"vps_id": vps_id, **held}, force=True):
                queued += 1
        return queued

    def _work(self) -> None:
        while True:
            with self._cv:
                if not self._queue:
                    self._cv.wait(IDLE_SECONDS)
                if not self._queue:
                    self._thread = None
                    return
                game = self._queue.popleft()
            try:
                self._refresh(game)
            except Unavailable as exc:
                self._failed[game["vps_id"]] = time.time() + RETRY_SECONDS
                logger.warning("VPC did not give scores for %s: %s", game.get("name"), exc)
            except Exception:
                self._failed[game["vps_id"]] = time.time() + RETRY_SECONDS
                logger.exception("Could not read VPC scores for %s", game.get("name"))
            finally:
                with self._cv:
                    self._pending.discard(game["vps_id"])
            time.sleep(PACE_SECONDS)

    def _refresh(self, game: dict) -> None:
        vps_id = game["vps_id"]
        releases = self._library.releases_of(vps_id)
        versions: list[dict] = []
        for term in library.search_terms(game):
            found = client.game_versions(term)
            versions = [client.version(one) for one in found
                        if library.belongs(one, term, vps_id, releases)]
            if versions:
                logger.info("VPC scores for %s: %d version(s) via %r", game.get("name"),
                            len(versions), term)
                break
        else:
            logger.info("VPC has no scores for %s", game.get("name"))
        self._store.put_game(vps_id, game, versions)
        self._store.flush()
        self._ctx.entries.stale("vpc")
