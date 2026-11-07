# Virtual Pinball Chat for VPinFE

A VPinFE 3 extension for [Virtual Pinball Chat](https://virtualpinballchat.com) (VPC): the weekly
competition, and the scores VPC holds for the tables in your library, with your own usernames
flagged.

## What it does

Two entries under **Community**:

- **VP Chat** lists the weekly table and every table in your library whose scores have been
  asked of VPC. Columns show the top score and player, a dot under **Scored** where one of your
  usernames has a score on the table, your best score and rank, and when it was last checked.
  Scores are shown with thousands separators. There is an **All Tables** view and a **My Scores**
  view. Click a row for the boards: one section per VPC version of the table, showing the top 10
  and then **your own line with the lines around it**, so a rank of 87 is visible in context.
  Your lines are marked with a star.
- **VPC Weekly** holds only this week's table. Core tags that game `vp-weekly` and moves the tag
  when the week changes. The tag lives on its own list because VPinFE tags the game of *every*
  row of a tagged list, which would tag every table in VP Chat.

## How scores are collected

There is no crawl of VPC. Scores are asked for one game at a time, as they are wanted:

| When | What happens |
|---|---|
| You browse to a game | Its scores are used from the cache. If they were never fetched, or are older than **Keep Table Scores For**, one request for that game is queued |
| You play a game | It is marked, and asked for again the next time you browse to it at least 5 minutes later (VPC scores are posted by hand, so right at exit is too early) |
| **Check Now** (title menu) | Reads the week, then queues every game already held, one after another |
| **Refresh Scores** (row menu) | Queues the selected games |
| The weekly table | Read when VPinFE starts and then at the **Check the Weekly Table** interval |

A game is searched as `Name (Maker Year)`, such as `24 (Stern 2009)`, then by name alone, and
only versions that are one of the game's VPS table files are kept. Requests are made by one
worker, a second apart. A game VPC does not know is remembered as having no scores for the same
time.

Scores are kept in full (not just the top 10), and between runs, in `cache/scores.json` in this
folder. Delete it to start again.

## Settings

Under **Settings > Extensions**:

- **Your VPC Usernames**: comma separated. Matched ignoring case.
- **Check the Weekly Table**: only when VPinFE starts, or every 30 minutes (the default), hour,
  3, 6 or 12 hours, or day. Core reads on a 30 minute tick, so a longer wait skips ticks.
- **Keep Table Scores For**: forever (the default), or 1, 3, 7 or 30 days, for every table that is not the
  weekly one.

## For theme authors

On the weekly game, `entry.ext.vpc_weekly` (empty on every other game):

```json
{"week": 334, "starts": "2026-11-02", "ends": "2026-11-08",
 "table": "Medieval Madness (Williams 1997)", "vps_release_id": "zbyQ01wi3L", "page": "https://...",
 "scores": [{"rank": 1, "player": "...", "score": 129846820, "posted": "2026-11-06T21:35:47",
             "url": "https://discord.com/...", "mine": false}]}
```

On any game with held scores, `entry.ext.vpc`:

```json
{"versions": [{"vps_release_id": "...", "version": "1.0.1", "authors": "...", "page": "https://...",
               "entries": 29, "scores": [{"rank": 1, "player": "...", "score": 1, "posted": "...",
                                          "url": "...", "mine": false}]}],
 "mine": [{"player": "...", "score": 1, "rank": 51, "of": 101, "version": "1.0.1",
           "vps_release_id": "..."}],
 "fetched": "2026-11-07T15:00:00Z"}
```

Each version's `scores` holds the top 25 plus your own lines, each with its true `rank`. The
version 0.1 weekly scores' `avatar`, `points` and `id` are no longer provided.

A collection of the weekly game still works as before: a Smart collection with a **Tags** rule
matching `vp-weekly`.

## Capabilities

| Capability | Why |
|---|---|
| `net:outbound` | To read the week and each game's scores from virtualpinballchat.com |
| `ui:mount` | For the VP Chat and VPC Weekly lists under Community |
| `config:own` | For the settings above |

| Scope | Why |
|---|---|
| `games:read` | To find which game a VPC table belongs to in VPinFE's VPS catalog. It changes nothing in your library |

## Code layout

`__init__.py` wires it up; `client.py` speaks to VPC; `library.py` finds the game; `store.py`
keeps scores in memory and on disk; `refresher.py` decides when to ask; `boards.py` ranks scores
and finds your lines; `community.py` draws the lists and theme entries.

## Install

Put this folder at `extensions/vpc_vpinfe` under the VPinFE config directory (the folder name
must stay `vpc_vpinfe`), restart VPinFE, and accept it under **Settings > Extensions**. It asks
again after an upgrade from 0.1 because of the new `config:own` capability.

Check it with:

```
vpinfe.exe --check-extension .
```
