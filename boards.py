"""Leaderboards: ranking scores and finding the flagged players' lines. Pure functions, so
they know nothing of VPinFE or the network."""

from __future__ import annotations

TOP = 10  # lines shown from the top of a board
AROUND = 2  # lines shown either side of a flagged player's line


def ranked(scores: list[dict], names: set[str]) -> list[dict]:
    """`scores` best first, each with its `rank` (equal scores share one) and whether it is a
    flagged player's. `names` are lower case."""
    out, rank, last = [], 0, None
    for place, one in enumerate(sorted(scores, key=lambda s: s.get("score") or 0, reverse=True),
                                start=1):
        if one.get("score") != last:
            rank, last = place, one.get("score")
        out.append({**one, "rank": rank,
                    "mine": str(one.get("player") or "").strip().lower() in names})
    return out


def mine(versions: list[dict], names: set[str]) -> list[dict]:
    """The flagged players' lines across a game's versions, best first."""
    if not names:
        return []
    lines = []
    for one in versions:
        board = ranked(one.get("scores") or [], names)
        for line in board:
            if line["mine"]:
                lines.append({"player": line["player"], "score": line["score"],
                              "rank": line["rank"], "of": len(board),
                              "version": one.get("version") or "",
                              "vps_release_id": one.get("vps_release_id") or ""})
    lines.sort(key=lambda line: (line["rank"], -(line["score"] or 0)))
    return lines


def window(board: list[dict]) -> list[dict | None]:
    """The lines of a ranked board worth drawing: the top, and each flagged line with those
    around it. A `None` stands for lines left out between two shown."""
    if not board:
        return []
    wanted = set(range(min(TOP, len(board))))
    for index, line in enumerate(board):
        if line["mine"]:
            wanted.update(range(max(0, index - AROUND), min(len(board), index + AROUND + 1)))
    out, last = [], -1
    for index in sorted(wanted):
        if last >= 0 and index > last + 1:
            out.append(None)
        out.append(board[index])
        last = index
    if last < len(board) - 1:
        out.append(None)
    return out
