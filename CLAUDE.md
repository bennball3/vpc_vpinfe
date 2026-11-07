# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [VPinFE](https://github.com/vpinfe/vpinfe) 3 extension that shows
[Virtual Pinball Chat](https://virtualpinballchat.com) (VPC) scores: the weekly competition and
the leaderboards for tables in the user's library. VPinFE loads it from
`extensions/vpc_vpinfe` in its config directory. The folder name must stay `vpc_vpinfe` (the same as
`name` in `extension.json`).

## Working rules

- **The repo is public on GitHub.** Treat every file, commit message and screenshot as
  world-readable. Keep personal paths, other people's VPC usernames and local config out of it.
  `cache/` holds the user's saved scores and is gitignored.
- **Always ask before committing or pushing**, every time, even if a commit was approved earlier
  in the session.
- Keep each file's existing line endings. `__init__.py` uses CRLF and the rest use LF. `sed -i`
  in Git Bash strips CR, so check `git diff --stat` after any shell edit.

## Commands

There is no build step, linter or test suite. VPinFE runs the code directly. To check that
VPinFE can load the extension, run this from the extension folder:

```bash
vpinfe.exe --check-extension .
```

The modules import `common.extensions.contract` (`Unavailable`, `get_json`, `why`) from VPinFE
itself, so they can't be imported or run outside VPinFE. A quick standalone check is
`python -m py_compile *.py` plus parsing `i18n/en.json`.

## Architecture

`register(ctx)` in `__init__.py` is the entry point. It wires up the modules below and
subscribes to VPinFE's `table.play_recorded` event. Everything talks to VPinFE through `ctx`:
`ctx.ui` (settings and lists), `ctx.games` (the library and VPS catalog), `ctx.config`,
`ctx.entries` (data passed to themes), `ctx.events` and `ctx.t` (i18n).

How the modules depend on each other:

- `client.py` is the stateless VPC API layer: `currentWeek` and a fuzzy table search. Network
  failures become `Unavailable`, which VPinFE reports as a service failure.
- `library.py` maps a VPC table to a library game. VPC's `vpsId` is a VPS *release* (one table
  file), not a game, so it is resolved through VPinFE's VPS catalog
  (`ctx.games.vps_releases` / `vps_settle`).
- `store.py` (`ScoreStore`) holds the week and each game's scores in memory and writes them
  atomically to `cache/scores.json`. VPinFE gives extensions no data folder of their own, so the
  cache lives next to the code. A play marks a game "dirty" and it's refetched after
  `SETTLE_SECONDS`, because VPC scores are posted by hand.
- `refresher.py` (`Refresher`) decides when to fetch. There is no crawl: one daemon worker
  thread fetches one game at a time, `PACE_SECONDS` apart, and exits when idle. Games are queued
  when browsed to (via the theme entry), when played, or from Check Now / Refresh Scores. The
  week is read a few seconds after launch (`start_launch_check`) and then on the
  `check_every` interval, measured against VPinFE's 30-minute ticks. After any change it calls
  `ctx.entries.stale("vpc")` / `stale("vpc_weekly")` so themes pick up the new data.
- `boards.py` holds pure functions that rank a leaderboard, flag the user's lines and pick the
  rows to show.
- `community.py` registers everything the user and themes see:
  - the **VP Chat** list (`ctx.ui.list(CHAT, ...)`) with its views, row actions and detail pane;
  - the one-row **VPC Weekly** list, registered with `tag="vpc-weekly"`. VPinFE tags the game
    of every row in a tagged list, so the tag must stay on this one-row list and never go on
    VP Chat;
  - the theme entries `entry.ext.vpc` and `entry.ext.vpc_weekly`. Building `vpc` for a game is
    also what queues a fetch when that game's scores are stale.
- `settings.py` defines the three settings. VPinFE sends no change event, so every reader calls
  `ctx.config` again each time.

User-facing strings live in `i18n/en.json` and are looked up with `ctx.t(key)`. Add new UI text
there rather than hard-coding it. The `vpc-weekly` tag and the shape of the `entry.ext` data are
documented in the README for users and theme authors, so update the README when either changes.
`extension.json` lists the capabilities and scopes. Adding one makes users accept the extension
again, and the README's Permissions table should match.

## README style

The README was rewritten to read naturally, following the Google developer documentation
style. Keep it that way: address the reader as "you", use active voice and sentence-case
headings, bold only UI labels, use numbered lists for steps, give every image alt text, and
avoid em dashes. Screenshots go in `docs/` as `.webp`.
