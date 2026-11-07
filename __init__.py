"""Virtual Pinball Chat: the weekly competition and the scores VPC holds for your tables.

- **VP Chat** (Community) lists the weekly table and every table in your library whose scores
  have been asked of VPC, with your own usernames flagged.
- **VPC Weekly** (Community) holds only this week's table. Core tags that game ``vpc-weekly``
  and moves the tag when the week changes, because VPinFE tags the game of every row of a
  tagged list, which is why the tag cannot live on VP Chat.
- Scores are asked of VPC one game at a time, as they are wanted: a game browsed to, a game
  just played, or the games the person asks to check. They are kept on disk between runs.
- A theme reads ``entry.ext.vpc_weekly`` on the weekly game and ``entry.ext.vpc`` on any game
  whose scores are held.

The work is split by what it does: ``client`` speaks to VPC, ``library`` finds the game,
``store`` keeps what was learned, ``refresher`` decides when to ask, ``boards`` ranks scores
and ``community`` draws it all.
"""

import logging
from pathlib import Path

from . import community, settings
from .library import Library
from .refresher import Refresher
from .store import ScoreStore

PLAY_RECORDED = "table.play_recorded"

logger = logging.getLogger("vpinfe.ext.vpc_vpinfe")


def register(ctx):
    ctx.ui.settings(settings.fields())

    store = ScoreStore(Path(__file__).parent / "cache" / "scores.json")
    refresher = Refresher(ctx, store, Library(ctx.games))

    def played(**payload):
        """A game was played: its scores are asked for again the next time it is browsed to,
        once VPC has had time to hear of them."""
        if payload.get("private") or not payload.get("game_id"):
            return
        try:
            vps_id = str(ctx.games.get_game(payload["game_id"]).get("vps_id") or "")
        except Exception:
            logger.debug("Could not look up the game just played", exc_info=True)
            return
        if vps_id and store.mark_dirty(vps_id):
            store.flush()

    ctx.events.subscribe(PLAY_RECORDED, played)
    community.install(ctx, store, refresher)
    refresher.start_launch_check()
