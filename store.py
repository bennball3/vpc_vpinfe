"""What has been learned from VPC, kept in memory and on disk between runs.

Core gives an extension no folder for data of its own, and ``ctx.config`` is for settings, not
leaderboards. So the scores live in ``cache/scores.json`` beside the extension, written whole
and atomically after every change. A file that cannot be read is set aside, and the scores are
fetched again as they are wanted.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")

SCHEMA = 1
# A play marks a game "dirty"; it is asked for again once this long has passed, since VPC's
# scores are posted by hand some time after the game ends.
SETTLE_SECONDS = 5 * 60


class ScoreStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._week: dict | None = None
        self._week_read_at = 0.0
        self._games: dict[str, dict] = {}
        self._load()

    # --- disk -------------------------------------------------------------------------

    def _load(self) -> None:
        try:
            held = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            logger.warning("Could not read %s; scores will be fetched again", self._path,
                           exc_info=True)
            return
        if not isinstance(held, dict) or held.get("schema") != SCHEMA:
            logger.info("Ignoring %s: it is from another version", self._path)
            return
        week = held.get("week")
        self._week = week if isinstance(week, dict) else None
        self._week_read_at = float(held.get("week_read_at") or 0)
        games = held.get("games")
        self._games = {str(key): value for key, value in games.items()
                       if isinstance(value, dict)} if isinstance(games, dict) else {}

    def flush(self) -> None:
        """Write everything held, whole and atomically."""
        with self._lock:
            body = json.dumps({"schema": SCHEMA, "week": self._week,
                               "week_read_at": self._week_read_at, "games": self._games},
                              separators=(",", ":"))
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix(".tmp")
            temp.write_text(body, encoding="utf-8")
            os.replace(temp, self._path)
        except OSError:
            logger.warning("Could not write %s", self._path, exc_info=True)

    # --- the week ---------------------------------------------------------------------

    def week(self) -> dict | None:
        with self._lock:
            return self._week

    @property
    def week_read_at(self) -> float:
        with self._lock:
            return self._week_read_at

    def set_week(self, week: dict | None, now: float | None = None) -> bool:
        """Hold the week as just read. True when it differs from what was held."""
        with self._lock:
            changed = week != self._week
            self._week = week
            self._week_read_at = time.time() if now is None else now
            return changed

    # --- games ------------------------------------------------------------------------

    def game(self, vps_id: str) -> dict | None:
        """A game's entry. Entries are replaced whole, never edited, so it is safe to read
        without the lock once handed out."""
        with self._lock:
            return self._games.get(vps_id)

    def games(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._games)

    def put_game(self, vps_id: str, info: dict, versions: list[dict],
                 now: float | None = None) -> None:
        with self._lock:
            self._games[vps_id] = {
                "name": str(info.get("name") or ""),
                "manufacturer": str(info.get("manufacturer") or ""),
                "year": str(info.get("year") or ""),
                "fetched_at": time.time() if now is None else now,
                "dirty_at": 0,
                "versions": versions,
            }

    def mark_dirty(self, vps_id: str, now: float | None = None) -> bool:
        """Note that a game was played since its scores were fetched. False where nothing is
        held for it, since it will be fetched when it is next browsed anyway."""
        with self._lock:
            held = self._games.get(vps_id)
            if held is None:
                return False
            self._games[vps_id] = {**held, "dirty_at": time.time() if now is None else now}
            return True

    def needs_refresh(self, vps_id: str, ttl: float, now: float | None = None) -> bool:
        """Whether a game's scores should be asked for again: never held, held longer than
        `ttl`, or played since and left to settle."""
        now = time.time() if now is None else now
        with self._lock:
            held = self._games.get(vps_id)
        if held is None:
            return True
        fetched = float(held.get("fetched_at") or 0)
        if now - fetched >= ttl:
            return True
        dirty = float(held.get("dirty_at") or 0)
        return bool(dirty and fetched < dirty and now - dirty >= SETTLE_SECONDS)
