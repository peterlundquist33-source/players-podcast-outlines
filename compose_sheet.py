#!/usr/bin/env python3
"""Compose a sheet-shaped export for build.py without touching Google Sheets.

`build.py` normally eats `gog sheets get ... --json`. When the workbook is
unreachable (expired OAuth, no network), this writes the same
`{"values": [[...]]}` payload from the players-league data files plus the
week's editorial content below, so the outline is still reproducible.

    python3 compose_sheet.py <deep.json> <league-data-dir> 5 wk5.json

Cell layout mirrors Peter's tab exactly — see build.py's `page()` for the
reader side. Anything the league data cannot supply is written as a
bracketed placeholder, never guessed.
"""
import json, sys, pathlib
from enrich import nfl_windows

COLS = 21          # A..U
ROWS = 48

# ---------------------------------------------------------------- week content

RECORDING = "[ date TBD ]"
GUEST = "[ guest TBD — not confirmed ]"
SONG = "[ intro song TBD ]"

AGENDA = [
    ("Welcome Back", ""),
    ("Last Week: Predictions vs. Results", ""),
    ("Weekly Awards + Analytics", ""),
    # Week 5's three verified trades are rendered from build.py's TRADES, which
    # inserts its own agenda row, so this no longer carries a placeholder.
    ("Trades + Waiver Moves", ""),
    ("Hot Seat", ""),
    ("Team of the Week", "[ pick TBD — workbook unreachable ]"),
    ("Matchups", ""),
    ("Lock of the Week", "[ lock + short reason ]"),
]

# (label, body, who) — rows 21-24, cols B/C/E
# Week 7 recap (this is what Week 8's show looks back on).
AWARDS = [
    ("Shit Cup Performance",
     "Mitchell — 79.38, the lowest score of Week 7 and 41.72 under his own 121.1 "
     "projection. Nico Collins 2.6 on a 16.7 projection (-14.1), Roschon Johnson 1.3 on "
     "9.1 (-7.8), and Matthew Golden 9.9 while Questionable — six of nine starters "
     "finished under 10 points. Fell to 1-6.",
     "Mitchell Max"),
    ("Statement Win",
     "Kaleb — 131.52 over Mitchell's 79.38, the week's largest margin (52.14). Tre "
     "Tucker 21.3 on a 10.5 projection from the FLEX spot (+10.8) and Ashton Jeanty 21.6 "
     "on 17.0 (+4.6) led the way; Harold Fannin Jr. added 13.1 from the TE spot.",
     "Kaleb Feahn"),
    ("Biggest Disappointment",
     "Adam — projected 135.6, the 2nd-highest pre-game number in the league, and "
     "managed just 103.02, a 32.58-point miss. Jalen Coker 1.9 on a 15.4 projection "
     "(-13.5) and Sam LaPorta 2.8 on 12.7 (-9.9) were the two biggest gaps; the "
     "Panthers D/ST went negative (-3.0). Dropped his first game of the season, "
     "falling to 6-1, outright to John.",
     "Adam Stockwell"),
    ("Shining Star",
     "Tony Pollard — 36.5 on a 13.8 projection, the biggest single overperformance of "
     "Week 7 (+22.7), off Grant's bench. Helped carry Amon that inhaler to the week's "
     "highest score (158.60) and a 36.34-point win over Christian.",
     "Grant Sawyer"),
]

# rows 15-17, col B — order fixed by power-rank severity: Mitchell, Noah, Isaac
# (power board ranks 12, 11, 10 of 12 after Week 7)
HOT_SEAT = [
    "Finding Nico — Mitchell · 1-6, dead last in the league on 35.1% all-play and "
    "10th in PF/G (106.7). Jahmyr Gibbs, Matthew Golden, DJ Moore and Tyler Warren all "
    "Questionable. Projected 120.5 against Noah's 122.2 — in the basement-bowl matchup, "
    "Mitchell's still a 51% favorite despite the lower number.",
    "Wilson Law Firm — Noah · 1-6, dead last in the league in PF/G (102.5) and dead "
    "last in all-play (31.2%) — the only team bottom of both. Faces 1-6 Mitchell, who "
    "leads their all-time series 7-2, and is still the underdog at 49% with the higher "
    "projection.",
    "A Slap in the Face — Isaac · 3-4, 11th in the league on 32.5% all-play and 11th "
    "in PF/G (103.6). Saquon Barkley and Ja'Marr Chase both Questionable. Projected "
    "86.6 against Adam's 134.1 — Adam's a 76% favorite.",
]

# Fantasy slot -> (away owner, home owner), in the order the pipeline ranked them.
# Slot headings must match build.py's ORDER to sort correctly. No international game
# touches any roster this week, so there's no Paris slot; Sunday Afternoon covers two
# matchups instead since the real NFL slate has multiple simultaneous late games.
SLOTS = [
    ("THURSDAY NIGHT GAME",     "Logan",     "Grant"),
    ("SUNDAY NOON GAME",        "Leif",      "Kaleb"),
    ("SUNDAY AFTERNOON GAME",   "Christian", "CJ"),
    ("SUNDAY AFTERNOON GAME",   "Peter",     "John"),
    ("SUNDAY NIGHT GAME",       "Adam",      "Isaac"),
    ("MONDAY NIGHT GAME",       "Mitchell",  "Noah"),
]

# All-time head-to-head, read off js/teams-data.js in the players-league repo.
# Checked for any current-season (2026) meeting between these pairs first — none yet.
H2H = {
    ("Logan", "Grant"):      "Grant leads Logan 5-4.",
    ("Leif", "Kaleb"):       "Kaleb leads Leif 4-3.",
    ("Christian", "CJ"):     "Christian leads CJ 6-2.",
    ("Peter", "John"):       "John leads Peter 6-3.",
    ("Adam", "Isaac"):       "Isaac leads Adam 5-3.",
    ("Mitchell", "Noah"):    "Mitchell leads Noah 7-2.",
}

# ---------------------------------------------------------------- composition


def key_players(side_rows, side, team_window, n=2):
    """Top-projected starters plus anything the host has to flag."""
    pl = [r[side] for r in side_rows if r[side]]
    pl.sort(key=lambda p: -p["proj"])
    out, seen = [], set()

    def line(p):
        w = team_window.get(p["pro"], "")
        pos = p.get("pos") or p["slot"]
        where = ", ".join(b for b in (p.get("opp", ""), w) if b) or f'{p["pro"]} on bye'
        flag = f' [{p["injury"].title()}]' if p["injury"] else ("" if w else " [BYE]")
        return f'{p["name"]} — {pos}, {where}, {p["proj"]:.1f} proj{flag}'

    for p in pl[:n]:
        seen.add(p["name"])
        out.append(line(p))
    for p in pl:                      # anything flagged that isn't already listed
        if p["name"] in seen:
            continue
        if p["injury"] or not team_window.get(p["pro"]):
            seen.add(p["name"])
            out.append(line(p))
    empty = sum(1 for r in side_rows if not r[side])
    if empty:
        out.append(f"{empty} starter slot(s) still empty — lineup not set")
    return out


def roster_cell(m, team_window):
    chunks = []
    for team, side in ((m["away"], "a"), (m["home"], "h")):
        lines = [team] + [f"• {b}" for b in key_players(m["lineup"], side, team_window)]
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)


def main(deep_path, week, out_path, season=2026):
    deep = json.load(open(deep_path))
    by_owner = {frozenset((m["away_owner"], m["home_owner"])): m for m in deep}
    team_window, _, _, _ = nfl_windows(season, week)

    V = [["" for _ in range(COLS)] for _ in range(ROWS)]

    def put(row, col, val):
        V[row - 1][ord(col) - 65] = val

    put(2, "E", RECORDING)
    put(5, "B", GUEST)
    put(5, "C", SONG)

    for i, (name, t) in enumerate(AGENDA):
        put(4 + i, "E", name)
        put(4 + i, "F", t)

    for i, h in enumerate(HOT_SEAT):
        put(15 + i, "B", h)

    for i, (label, body, who) in enumerate(AWARDS):
        put(21 + i, "B", label)
        put(21 + i, "C", body)
        put(21 + i, "E", who)

    # matchup blocks: rows 4/17/30, column pairs (I,K) and (N,P)
    anchors = [(r, L, R) for r in (4, 17, 30) for L, R in (("I", "K"), ("N", "P"))]
    for (slot, away_ow, home_ow), (r, L, R) in zip(SLOTS, anchors):
        m = by_owner[frozenset((away_ow, home_ow))]
        if m["away_owner"] != away_ow:          # keep the data's own home/away
            raise SystemExit(f"home/away mismatch for {away_ow} v {home_ow}")
        put(r, L, slot)
        put(r + 1, L, m["away"])
        put(r + 1, R, m["home"])
        put(r + 2, L, roster_cell(m, team_window))
        put(r + 4, L, "ALL-TIME H2H " + H2H[(away_ow, home_ow)])

    pathlib.Path(out_path).write_text(json.dumps({"values": V}, indent=1))
    print(f"wrote {out_path}: {len(SLOTS)} matchups, {len(AWARDS)} awards, "
          f"{len(HOT_SEAT)} hot-seat entries")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
