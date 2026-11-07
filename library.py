"""Finding the game in VPinFE's library that a VPC table belongs to.

VPC's ``vpsId`` names one table file (a VPS release), not the game, so it is resolved to its
game through the VPS catalog VPinFE already keeps on disk: the game is found from VPC's table
name, then confirmed by that release being one of the game's table files.
"""

from __future__ import annotations

import logging

from . import client

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")


class Library:
    def __init__(self, games) -> None:
        self._games = games
        self._resolved: dict[str, str] = {}  # VPC release id -> VPS game id, for the run

    def releases_of(self, game_vps_id: str) -> set[str]:
        """The VPS table file ids of a game, empty for an id the catalog does not hold."""
        try:
            listed = self._games.vps_releases(game_vps_id, listed_as="tableFiles")
        except Exception:
            return set()
        return {str(one.get("vps_file_id") or "") for one in listed.get("releases") or []}

    def game_of(self, release_id: str, table: str) -> str:
        """The VPS game id `release_id` is a table file of, or "" where the catalog on disk
        cannot say."""
        if release_id in self._resolved:
            return self._resolved[release_id]
        found = ""
        if release_id in self.releases_of(release_id):
            found = release_id  # already a game id
        else:
            try:
                settled = self._games.vps_settle([client.settle_row(table)])
            except Exception:
                logger.warning("Could not look up %r in the VPS catalog", table, exc_info=True)
                return ""
            answer = settled[0] if settled else {}
            candidates = [answer.get("vps_id") or ""]
            candidates += [one.get("id") or one.get("vps_id") or ""
                           for one in answer.get("candidates") or []]
            for candidate in filter(None, candidates):
                if release_id in self.releases_of(candidate):
                    found = candidate
                    break
        if found:
            self._resolved[release_id] = found
        else:
            logger.info("Release %s (%s) is not in the VPS catalog on disk", release_id, table)
        return found


def search_terms(game: dict) -> list[str]:
    """What to search VPC for, most exact first. VPC names a table "Name (Maker Year)", so
    that is tried before the bare name."""
    name = str(game.get("name") or "").strip()
    if not name:
        return []
    maker = str(game.get("manufacturer") or "").strip()
    year = str(game.get("year") or "").strip()
    terms = []
    if maker and year:
        terms.append(f"{name} ({maker} {year})")
    terms.append(name)
    return terms


def belongs(raw: dict, term: str, game_vps_id: str, releases: set[str]) -> bool:
    """Whether a table VPC found for `term` is this game: its release is one of the game's
    table files, or the game itself, or it is named just as asked."""
    release = str(raw.get("vpsId") or "")
    if release and (release == game_vps_id or release in releases):
        return True
    return str(raw.get("tableName") or "").strip().lower() == term.strip().lower()
