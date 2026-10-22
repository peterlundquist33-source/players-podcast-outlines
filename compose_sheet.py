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
AWARDS = [
    ("Shit Cup Performance",
     "Peter — 69.78, the lowest score of Week 6 and 49.1 under his own 118.9 projection. "
     "Bijan Robinson 7.3 on a 23.0 projection (-15.7), A.J. Brown 5.7 on 12.7 while "
     "Questionable, Denzel Boston 2.5 on 13.5, and Cam Ward 6.8 on 13.0 — four of nine "
     "starters finished in single digits. Lost to Kaleb by 24.58 as the betting favorite.",
     "Peter Lundquist"),
    ("Statement Win",
     "Logan — 152.52 over John's 100.08, the week's largest margin (52.44) and Logan's "
     "2nd-highest score of the season. Germie Bernard 25.7 on a 9.9 projection (+15.8, "
     "the week's single biggest overperformance) and Isaiah Likely 23.9 on 14.7 (+9.2) "
     "both nearly doubled their numbers; Chase McLaughlin added 18.6 from the kicker spot.",
     "Logan Rezac"),
    ("Biggest Disappointment",
     "John — projected 138.0, the week's highest pre-game number, and managed just "
     "100.08, a 37.9-point miss. Kyren Williams 9.7 on a 21.0 projection and Brock Bowers "
     "11.0 on 19.8 were the two biggest gaps; the Jaguars D/ST went negative (-2.0). "
     "Fell to 3-3 off the week's steepest favorite-to-underperform.",
     "John Lundquist"),
    ("Shining Star",
     "Germie Bernard — 25.7 on a 9.9 projection, the biggest single overperformance of "
     "Week 6 (+15.8), off Logan's bench. Helped carry Runnin' Rezac to the week's "
     "largest margin of victory and Logan's 2nd-highest score of the season.",
     "Logan Rezac"),
]

# rows 15-17, col B — order fixed by power-rank severity: Isaac, Noah, Mitchell
HOT_SEAT = [
    "A Slap in the Face — Isaac · 2-4, dead last in the league on 25.8% all-play, the "
    "worst mark in Players League, and 12th in PF/G (99.8). Saquon Barkley and T.J. "
    "Hockenson both Questionable. Projected 128.3 against Logan's 123.2 — Logan still "
    "favored at 53%.",
    "Wilson Law Firm — Noah · 1-5, 2nd-worst in the league in PF/G (101.6) and "
    "2nd-worst all-play (30.3%). Faces 4-2 Peter — but Noah actually leads their "
    "all-time series 6-2.",
    "Finding Nico — Mitchell · 1-5 but 111.3 PF/G with a -1.5 luck rating — the record "
    "undersells the roster. Jordan Mason on IR, Travis Kelce and Matthew Golden both "
    "Questionable. Projected 121.7 against Kaleb's 116.5.",
]

# Fantasy slot -> (away owner, home owner), in the order the pipeline ranked them.
# Slot headings must match build.py's ORDER to sort correctly.
SLOTS = [
    ("THURSDAY NIGHT GAME",           "Isaac",     "Logan"),
    ("SUNDAY NOON GAME",              "Kaleb",     "Mitchell"),
    ("PARIS GAME — SUNDAY MORNING",   "Grant",     "Christian"),
    ("SUNDAY AFTERNOON GAME",         "Noah",      "Peter"),
    ("SUNDAY NIGHT GAME",             "CJ",        "Leif"),
    ("MONDAY NIGHT GAME",             "John",      "Adam"),
]

# All-time head-to-head, read off js/teams-data.js in the players-league repo.
H2H = {
    ("Isaac", "Logan"):     "Isaac leads Logan 6-1.",
    ("Kaleb", "Mitchell"):  "Kaleb leads Mitchell 4-3.",
    ("Grant", "Christian"): "Christian leads Grant 5-2.",
    ("Noah", "Peter"):      "Noah leads Peter 6-2.",
    ("CJ", "Leif"):         "CJ and Leif are dead even 4-4 — CJ is Leif's listed rival.",
    ("John", "Adam"):       "Adam leads John 6-1.",
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
