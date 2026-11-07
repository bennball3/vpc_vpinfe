# Virtual Pinball Chat for VPinFE

> [!WARNING]
> This extension is a work in progress. Settings, cached data and the data passed to themes may
> change between versions, and an update may break your setup.

A [VPinFE](https://github.com/vpinfe/vpinfe) 3 extension that brings
[Virtual Pinball Chat](https://virtualpinballchat.com) (VPC) into your cabinet. It shows the VPC
weekly competition and the VPC leaderboards for the tables in your library, and highlights your
own scores.

It also tags the current weekly table `vpc-weekly`, so you can build a collection that always
holds this week's table. See [Collect the weekly table](#collect-the-weekly-table).

![VP Chat in VPinFE Manager: the weekly table listed first, with the week's leaderboard open beside it](docs/vp-chat.webp)

## Features

- **VP Chat list.** Under **Community** in VPinFE Manager, a list of the weekly table and every
  table you have VPC scores for. For each table you see the top score and who holds it, your best
  score and rank, and when the scores were last updated. The weekly table is always first.
  Switch between the **All Tables** and **My Scores** views.
- **Leaderboards in context.** Click a table to see its leaderboard for each VPC version of it:
  the top 10, then your own score with the scores just above and below it. If you're 87th,
  you see who you need to beat. Your scores are marked with a star.
- **Weekly tag.** The current weekly table is tagged `vpc-weekly`, and the tag moves when a new
  week starts.
- **Scores for themes.** Themes can read each table's leaderboard and the weekly competition, so
  they can show them in the frontend. See [For theme authors](#for-theme-authors).

## Install

1. Clone or download this repository into the `extensions` folder of your VPinFE config
   directory. On Windows this is `%LOCALAPPDATA%\vpinfe\vpinfe\extensions`. The folder must be
   named `vpc_vpinfe`:

   ```bash
   git clone https://github.com/bennball3/vpc_vpinfe.git
   ```

2. Restart VPinFE.
3. In VPinFE Manager, go to **Settings > Extensions** and accept the extension.

To check that VPinFE can load the extension, run this from the extension folder:

```bash
vpinfe.exe --check-extension .
```

## Settings

Find these in VPinFE Manager under **Settings > Extensions**.

| Setting | What it does |
|---|---|
| **Your VPC Usernames** | Your VPC usernames, separated by commas. Scores from these names are highlighted. Case doesn't matter. |
| **Check the Weekly Table** | How often to check for a new weekly table: only at startup, every 30 minutes (default), every 1, 3, 6 or 12 hours, or once a day. VPinFE runs this check on a 30-minute cycle, so intervals are rounded up to the next cycle. |
| **Keep Table Scores For** | How long to keep a table's scores before fetching them again: forever (default), or 1, 3, 7 or 30 days. Doesn't apply to the weekly table. |

## Collect the weekly table

The extension tags the current weekly table `vpc-weekly`. When a new week starts, the tag moves to
the new table. No other games get the tag.

You can see the tag on the game in the **Games** view:

![The Games view in VPinFE Manager: Medieval Madness, the week's table, has the vpc-weekly tag](docs/weekly-tag.webp)

To make a collection that always holds the weekly table:

1. In VPinFE Manager, go to **Library > Collections**.
2. Add a **Smart** collection.
3. Add one rule: **Tags**, **Is any of**, `vpc-weekly`.

![A Smart collection named Competitions in VPinFE Manager, with the rule Tags is any of vpc-weekly, holding Medieval Madness](docs/weekly-smart-collection.webp)

The collection updates by itself each week.

The tag comes from the extension's **VPC Weekly** list, which you'll also see under
**Community**. VPinFE tags every game in a tagged list, so the tag is on this one-table list
rather than on VP Chat, where it would tag every table.

## How scores are updated

The extension doesn't download all of VPC. It fetches scores for one table at a time, only when
you need them:

| When | What happens |
|---|---|
| You browse to a table | The extension shows the saved scores. If there are none yet, or they're older than **Keep Table Scores For**, it fetches them. |
| You play a table | The next time you browse to it, at least 5 minutes later, it fetches the scores again. The wait is there because players post VPC scores by hand after a game. |
| You choose **Check Now** (title menu) | It checks the weekly table, then fetches scores again for every table it has saved. |
| You choose **Refresh Scores** (row menu) | It fetches scores again for the selected tables. |
| VPinFE starts | It shows the weekly table it saved last time straight away, then checks VPC for the current week a few seconds later, and again at the **Check the Weekly Table** interval. |

To find a table on VPC, the extension searches for `Name (Manufacturer Year)`, for example
`24 (Stern 2009)`, and then for the name alone. It keeps only the VPC versions that match one of
the game's table files in VPS. It sends one request at a time, a second apart. If VPC has no
scores for a table, the extension remembers that and doesn't ask again until the
**Keep Table Scores For** time has passed.

Scores are saved in full in `cache/scores.json` in the extension folder. To start fresh, delete
that file.

## For theme authors

The extension adds two fields to the game entries a theme receives.

`entry.ext.vpc` is set on every game with saved scores:

```json
{"versions": [{"vps_release_id": "...", "version": "1.0.1", "authors": "...", "page": "https://...",
               "entries": 29, "scores": [{"rank": 1, "player": "...", "score": 1, "posted": "...",
                                          "url": "...", "mine": false}]}],
 "mine": [{"player": "...", "score": 1, "rank": 51, "of": 101, "version": "1.0.1",
           "vps_release_id": "..."}],
 "fetched": "2026-11-07T15:00:00Z"}
```

- `versions` has one entry per VPC version of the table. Each version's `scores` holds the top 25
  plus your own scores, each with its real `rank`. `mine` is `true` for your scores.
- `mine` lists all your scores across the versions, best rank first. `of` is the number of
  scores on that version's leaderboard.

`entry.ext.vpc_weekly` is set only on the weekly game, and is empty on every other game:

```json
{"week": 334, "starts": "2026-11-02", "ends": "2026-11-08",
 "table": "Medieval Madness (Williams 1997)", "vps_release_id": "zbyQ01wi3L", "page": "https://...",
 "scores": [{"rank": 1, "player": "...", "score": 129846820, "posted": "2026-11-06T21:35:47",
             "url": "https://discord.com/...", "mine": false}]}
```

## Permissions

VPinFE asks you to accept these when you install the extension.

| Permission | Why the extension needs it |
|---|---|
| `net:outbound` | To fetch the weekly table and scores from virtualpinballchat.com. |
| `ui:mount` | To add the VP Chat and VPC Weekly lists under **Community**. |
| `config:own` | To store its settings. |
| `games:read` (scope) | To match VPC tables to games in your library using VPinFE's VPS data. It doesn't change your library. |

## Project layout

| File | Purpose |
|---|---|
| `__init__.py` | Sets up the extension. |
| `client.py` | Talks to the VPC API. |
| `library.py` | Matches VPC tables to games in your library. |
| `store.py` | Keeps scores in memory and saves them to disk. |
| `refresher.py` | Decides when to fetch scores. |
| `boards.py` | Ranks scores and finds yours. |
| `community.py` | Builds the lists and the data for themes. |
