"""The extension's settings and how they are read. Core sends no change event, so every
reader asks ctx.config afresh."""

from __future__ import annotations

HOUR = 3600
DAY = 24 * HOUR

# value -> seconds; None means only when VPinFE starts.
WEEK_EVERY = {"launch": None, "30m": 1800, "1h": HOUR, "3h": 3 * HOUR, "6h": 6 * HOUR,
              "12h": 12 * HOUR, "24h": DAY}
KEEP_FOR = {"forever": float("inf"), "1d": DAY, "3d": 3 * DAY, "7d": 7 * DAY, "30d": 30 * DAY}

DEFAULT_WEEK = "30m"
DEFAULT_KEEP = "forever"


def fields() -> list[dict]:
    return [
        {"key": "usernames", "type": "string", "default": ""},
        {"key": "check_every", "type": "select", "default": DEFAULT_WEEK,
         "choices": [[key, key] for key in WEEK_EVERY]},
        {"key": "keep_scores", "type": "select", "default": DEFAULT_KEEP,
         "choices": [[key, key] for key in KEEP_FOR]},
    ]


def usernames(ctx) -> set[str]:
    """The flagged VPC usernames, lower case."""
    text = str(ctx.config.get("usernames") or "")
    return {one.strip().lower() for one in text.replace(";", ",").split(",") if one.strip()}


def week_interval(ctx):
    """Seconds between reads of the week, or None for only when VPinFE starts."""
    return WEEK_EVERY.get(str(ctx.config.get("check_every") or DEFAULT_WEEK),
                          WEEK_EVERY[DEFAULT_WEEK])


def keep_for(ctx) -> float:
    """Seconds a table's scores are kept before they are asked for again; infinite when kept
    forever, so only a play, Check Now or Refresh Scores asks again."""
    return KEEP_FOR.get(str(ctx.config.get("keep_scores") or DEFAULT_KEEP),
                        KEEP_FOR[DEFAULT_KEEP])
