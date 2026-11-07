# Virtual Pinball Chat for VPinFE

A VPinFE 3 extension that tags the current [Virtual Pinball Chat](https://virtualpinballchat.com)
weekly competition table with `vp-weekly` and shows that week's scores.

## What it does

- Reads the current week from `https://virtualpinballchat.com/vpc/api/v1/currentWeek`.
- Shows it under **Community > VPC Weekly**: the game, the week number, when the week ends and
  a link to the table download.
- Declares the list with `tag="vp-weekly"`, so VPinFE itself puts the tag on that game in your
  library. Core reads the list shortly after startup and every 30 minutes, and takes the tag off
  a game once it is no longer the weekly table, so only one game carries it at a time. The
  extension never writes tags itself.
- Click the week's row and a pane opens beside it with the week's leaderboard (rank and
  player beside their score, with thousands separators) and the week's details: the game, when
  it starts and ends, and a link to download the table.
- Hands the week and its scores to the frontend theme, on the weekly game (see below).

VPC's `vpsId` is the VPS id of one table file (a release), not of the game. The extension
looks it up in the VPS catalog VPinFE already keeps on disk: it finds the game from VPC's table
name ("Medieval Madness (Williams 1997)") and keeps it only if that release is one of the
game's table files. No extra download is made. The tag goes on the whole game, so it is there
whichever version of the table you have. If the catalog can't place the release, the row still
shows but no game is tagged.

If VPC has no table for the week, the list is empty and no game is tagged. If the site does
not answer, the list says so and the last good read (and its tag) stays.

## Scores and refreshing

The scores are downloaded when VPinFE starts (with the weekly read, about 15 seconds in) and
again every 30 minutes. To get the latest straight away, open **Community > VPC Weekly** and
press **Refresh**. Opening the page also reads them again, and the page shows the last good
read at once while it does.

## A collection of the weekly game

The `vp-weekly` tag works anywhere a tag filter does. To have the weekly table on the frontend
as its own collection:

1. In the Manager, open **Library > Collections** and choose **New collection**.
2. Make it **Smart**, so it fills itself from its rules.
3. Add a rule on **Tags** that matches `vp-weekly`, and save.

The collection then always holds the current weekly game, and follows it to the next one when
the week changes, with nothing to edit by hand.

## For theme authors

On the weekly game, a theme reads `entry.ext.vpc_weekly`. It is empty on every other game, so
`if (entry.ext.vpc_weekly)` is enough to tell whether a game is this week's table:

```json
{
  "week": 334,
  "starts": "2026-11-02",
  "ends": "2026-11-08",
  "table": "Medieval Madness (Williams 1997)",
  "vps_release_id": "zbyQ01wi3L",
  "page": "https://vpuniverse.com/files/file/...",
  "scores": [
    {"id": "…", "rank": 1, "player": "…", "avatar": "https://…", "score": 129846820,
     "points": 12, "posted": "2026-11-06T21:35:43"}
  ]
}
```

`score` is a plain number, for the theme to format as it likes. It is refreshed whenever the
list is read. The tag is in `game.derived_tags` for a theme
that wants only that.

## Capabilities

| Capability | Why |
|---|---|
| `net:outbound` | To fetch the current week and its scores from virtualpinballchat.com |
| `ui:mount` | To show the VPC Weekly list and its scores pane under Community. The list is what carries the tag |

| Scope | Why |
|---|---|
| `games:read` | To look up which game VPC's table file belongs to in VPinFE's VPS catalog (`vps_settle`, `vps_releases`). It changes nothing in your library |

## Install

Put this folder at `extensions/vpc_vpinfe` under the VPinFE config directory (the folder name
must stay `vpc_vpinfe`), restart VPinFE, and accept it under **Settings > Extensions**.

Check it with:

```
vpinfe.exe --check-extension .
```
