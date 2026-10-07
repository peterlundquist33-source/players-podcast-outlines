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
    ("Trades + Waiver Moves", "[ needs ESPN transactions — not wired up ]"),
    ("Hot Seat", ""),
    ("Team of the Week", "[ pick TBD — workbook unreachable ]"),
    ("Matchups", ""),
    ("Lock of the Week", "[ lock + short reason ]"),
]

# (label, body, who) — rows 21-24, cols B/C/E
AWARDS = [
    ("Shit Cup Performance",
     "Leif — 82.82, the lowest score of Week 4 and 46.0 under his own 128.8 projection, "
     "the second-highest on the slate behind Adam's 133.2. All nine starters finished under: "
     "Josh Allen 18.5 (22.2 proj), McCaffrey 16.0 (20.3), Henry 15.9 (20.3), Davante Adams "
     "7.2 (15.6), Diggs 8.5 (12.8), Schultz 2.9 (9.0), Montgomery 4.3 (13.5), Texans D/ST "
     "3.0 (4.9), Myers 6.5 (10.2). Lost by 80.2, the widest margin of the week.",
     "Leif Engen"),
    ("Statement Win",
     "Peter — 162.98 over Leif's 82.82. Top score of Week 4, widest margin of the week "
     "(80.2), and he was the underdog on paper by 16.7 projected points. Three starters "
     "cleared projection by double digits: Kyle Monangai 28.0 (+19.7), Romeo Doubs 23.8 "
     "(+14.0) and Tee Higgins 26.7 (+13.0), with Bijan Robinson adding 27.7. Now 4-0 with "
     "350.7 points against, fewest in the league. Runner-up: Christian's 157.48, by 44.6.",
     "Peter Lundquist"),
    ("Biggest Disappointment",
     "Rashee Rice — 0.00 on a 14.9 projection, the worst projection-to-actual gap of any "
     "Week 4 starter, and he went in QUESTIONABLE. CJ survived it anyway, 114.64-110.50. "
     "Runner-up, and the one that actually decided a game: Ja'Marr Chase, 5.70 on a 20.4 "
     "projection (-14.7), in Isaac's 25.4-point loss. (Week 3 precedent: this award goes "
     "to the worst projection-to-actual gap among starters.)",
     "CJ Woda"),
    ("Shining Star",
     "Tetairoa McMillan — 45.20, the top starter score of Week 4 and +29.4 over projection, "
     "the biggest overperformance on the slate. It still wasn't enough: Logan lost "
     "112.92-157.48 and is 0-4. Runner-up: CeeDee Lamb, 41.30 (+24.4) for Christian, which "
     "did win its week.",
     "Logan Rezac"),
]

# rows 15-17, col B — order fixed by Peter: Noah, Logan, Mitch
HOT_SEAT = [
    "Maye Have Downs — Noah · 0-4, 89.9 ppg and 359.5 PF (both last in the league), "
    "all-play 7-37, power #12. Projected favorite again on Monday night, 117.1 to Kaleb's "
    "104.9 (57%) — that is four of five weeks as the projected favorite, at 0-4. "
    "No excuses left in that one.",
    "Runnin' Rezac — Logan · 0-4 with 603.6 points against, the most any team has "
    "allowed, luck -1.7, power #11. As of Wednesday morning his Week 5 lineup still has "
    "three empty starter slots, which is the only reason the card reads 69.6.",
    "Finding Nico — Mitchell · 1-3, 112.3 ppg, power #8, coming off a 44.3-point loss to "
    "Adam. Projected 80% to beat Logan. Lose this one and the playoff story gets hard "
    "to tell.",
]

# Fantasy slot -> (away owner, home owner), in the order the pipeline ranked them.
# Slot headings must match build.py's ORDER to sort correctly.
SLOTS = [
    ("THURSDAY NIGHT GAME",    "Isaac",     "Grant"),
    ("SUNDAY NOON GAME",       "John",      "CJ"),
    ("SUNDAY NOON GAME",       "Logan",     "Mitchell"),
    ("SUNDAY AFTERNOON GAME",  "Christian", "Leif"),
    ("SUNDAY NIGHT GAME",      "Adam",      "Peter"),
    ("MONDAY NIGHT GAME",      "Noah",      "Kaleb"),
]

# All-time head-to-head, read off js/teams-data.js in the players-league repo.
H2H = {
    ("Isaac", "Grant"):     "Grant leads Isaac 4-3.",
    ("John", "CJ"):         "Split 2-2.",
    ("Logan", "Mitchell"):  "Split 2-2.",
    ("Christian", "Leif"):  "Christian leads Leif 3-1.",
    ("Adam", "Peter"):      "Peter leads Adam 4-1 — the best record anyone holds on Adam "
                            "(Isaac 5-3, Grant 3-2 and Kaleb 4-3 are also ahead of him).",
    ("Noah", "Kaleb"):      "Noah leads Kaleb 5-1.",
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
    team_window, _, _ = nfl_windows(season, week)

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
