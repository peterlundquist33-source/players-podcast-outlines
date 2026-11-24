#!/usr/bin/env python3
"""Compose the Week 12 2026 sheet payload without touching Google Sheets.

Peter's Google OAuth grant was revoked on 2026-11-24 (every gog call on
peterlundquist33@gmail.com returns invalid_grant), so the `Podcast Week 12
2026` tab could not be created or written. This emits the same
`{"values": [[...]]}` payload `build.py` eats, laid out cell-for-cell on the
`Podcast Week 6 2026` tab — the most complete finished tab in the workbook,
and the only recent one with the matchup bullets, the Trend/stat lines, the
all-time H2H lines and the Team of the Week draft-round/current-rank columns
all filled in. Weeks 9 and 11 leave those as bare labels, so copying either
would have shipped a half-empty format.

`compose_sheet.py` is the README's documented fallback but writes a reduced
subset of that layout (no Team of the Week block, no awards header row, hot
seat crammed into column B, no Peter's-notes block), and its editorial
constants still hold Week 7/8 content. Rewriting it in place would have
broken the Week 5/7/8 rebuilds it still reproduces, so Week 12 gets its own
composer and `compose_sheet.py` is left alone.

Every number here is read off the players-league data files and verified
against them; see `verify_wk12.py`, which re-derives each superlative from
the source data and fails loudly on a mismatch. Anything the league data
cannot supply — guest, recording date, Peter's six picks, the lock, the
Team of the Week call, his notes — stays a bracketed placeholder.

    python3 wk12_compose.py wk12.json
"""
import json, sys

COLS, ROWS = 21, 48          # A..U, matching the workbook's A1:U48 export

# --------------------------------------------------------------- week content

WEEK = 12
RECORDING = "Nov 24, 2026"
GUEST = "None"
# Arena rock, unused, and the lyric points at a real Week 12 fact: it is
# Thanksgiving week in a Minnesota league. Not one of SONGS.md's earmarked
# songs, which are held for a bad-beat / Monday-decided / playoff-run week.
SONG = "Immigrant Song — Led Zeppelin"

# Agenda rows D4:E11. Column F is the per-segment runtime; no finished tab in
# the workbook has ever filled it, so it is left empty rather than invented.
AGENDA = [
    "Welcome Back",
    "Last Week: Predictions vs. Results",
    "Weekly Awards + Analytics",
    "Trades + Waiver Moves",
    "Hot Seat",
    "Team of the Week",
    "Matchups",
    "Lock of the Week",
]

PREDICTION_RECORD = "0-0"
# Peter's max-confidence (6-pt) Beat the Board pick doubles as the Lock.
LOCK = ("Adam over Noah (6 pts) — ESPN has power-#1 Adam a 49% underdog to "
        "3-8 Noah on the strength of his set lineup, but Noah's last in the "
        "league in all-play at 31.4%. Fade the algorithm.")

# Hot seat, rows 15-17: team in column B, evidence in column E. Ordered by
# power-board severity after Week 11 — Noah #12, Peter #11, Kaleb #10.
HOT_SEAT = [
    ("I Didn't Hear No Bell — Noah",
     "3-8 and power #12. Last in the league in all-play at 38-83 (31.4%), and "
     "11th of 12 in PF/G at 104.6. Week 11's 89.16 was 21.3 under projection, "
     "a second straight loss. Draws Adam, whose 138.2 optimal is the highest "
     "number on the Week 12 board."),
    ("The Basement Of KK — Peter",
     "5-6 on an L4 skid, power #11, all-play 45-76 (37.2%, tied last). Week "
     "11's 66.30 was his season low and the third-lowest score anyone has "
     "posted in 2026; seven of nine starters finished under 7.5 points. Is a "
     "61% favorite this week, the biggest edge on the board."),
    ("PA Dive Your Way — Kaleb",
     "7-4 but power #10 — the record is running well ahead of the roster. "
     "Last in the league in PF/G at 103.7, all-play 45-76 (37.2%, tied last "
     "with Peter) and the league's highest luck rating at +2.9. Projects 93.1 "
     "as set, the lowest on the Week 12 board, with 17.0 more points "
     "available on his bench."),
]

# Weekly awards, rows 21-24: label in B, body in C, owner in E. All four
# describe Week 11, which is the week this episode looks back on.
AWARDS = [
    ("Shit Cup Performance",
     "66.30 — the lowest score of Week 11, and 21.7 under his own 88.0 "
     "projection, itself the lowest projection on the slate. Seven of nine "
     "starters finished under 7.5: Kyle Monangai 1.80, Cade Otton 1.80, "
     "Panthers D/ST 4.00, Emari Demercado 4.90, Adonai Mitchell 5.00, Pat "
     "Bryant 6.20, Kirk Cousins 7.40. George Pickens (23.80) was the only "
     "starter over 12. His season low, and the third-lowest score anyone has "
     "posted in 2026.",
     "Peter Lundquist"),
    ("Statement Win",
     "162.90 over Grant's 121.36 — the highest score of Week 11, the largest "
     "margin of the week (41.54) and the biggest beat on projection (+45.2). "
     "Travis Kelce 25.40 on 11.3 (+14.1), Dak Prescott 35.90 on 21.9 (+14.0) "
     "and DJ Moore 23.10 on 13.7 (+9.4). Third straight win, and the power "
     "board moved him up 3 spots to #4 at 4-7.",
     "Mitchell Max"),
    ("Biggest Disappointment",
     "Carried Week 11's highest projection at 135.2 and scored 113.76, losing "
     "to Leif by 6.00. Ja'Marr Chase 8.10 on a 25.4 projection was the week's "
     "worst starter bust (-17.3) and Cam Skattebo added 5.80 on 14.5. Second "
     "straight loss, down to 5-6. (Logan's 92.10 on 125.1 was the week's "
     "largest miss at -33.0 — and he still beat Noah by 2.94.)",
     "Isaac Douglas"),
    ("Shining Star",
     "Jonah Coleman 34.90 on a 19.4 projection — the biggest single-starter "
     "overperformance of Week 11 (+15.5), off an undrafted waiver add. Carried "
     "John to 134.34 and a 0.60-point win over Christian, the narrowest "
     "margin of the week.",
     "John Lundquist"),
]

# Team of the Week, rows 28-37. Eight of twelve owners have already had it
# (Logan W1, John W2, Adam W3, Isaac W4, Leif W6, CJ W7, Grant W10,
# Christian W11), so the rotation rule leaves Peter, Kaleb, Mitchell and Noah
# eligible, with Mitchell the strongest case (Week 11's league-high 162.90).
# Peter cut the segment for Week 12 (2026-11-24) rather than spend it on a
# default pick — TOTW_SKIPPED carries the note and the block below renders
# nothing else. Un-skip by filling TOTW_META/TOTW_ROSTER/IMPACT again.
TOTW_SKIPPED = ("Skipped this week. Still eligible: Peter, Kaleb, Mitchell, "
                "Noah — Mitchell's the strongest case (Week 11's league-high "
                "162.90) if it comes back.")
TOTW_META = []

# (slot, player, draft round, current rank). "FA" marks a player this owner
# did not draft — the convention Week 6 used for Leif's traded-in Mike Evans.
# Ranks are 2026 points scored among league-rostered players at that position.
TOTW_ROSTER = []

IMPACT = []

# Peter's Beat the Board picks for Week 12, in slate order (matches MATCHUPS
# below), with his confidence points out of 6. Pulled straight from his
# submitted Firestore entry, not invented.
PICK = [
    "Mitchell (4 pts) — backing the hot hand (league-high 162.90 last week) "
    "over CJ's depth.",
    "Logan (3 pts) — weird things keep happening for him, and he dodges the "
    "Coleman/Warren collision entirely.",
    "Christian (5 pts) — betting the bad-luck power #2 bounces back against "
    "Isaac's projection lead.",
    "Grant (1 pt) — lowest confidence on the board, leaning on the "
    "power-ranking gap over Leif's better record.",
    "Peter (2 pts) — the week's biggest favorite (61%) and he still only "
    "trusts himself for 2 points.",
    "Adam (6 pts) — also his Lock of the Week; see above.",
]

# Matchup blocks, in slate order. Each lands at rows r/r+1/r+2/r+3/r+4 and
# r+7/r+8 of its column pair, anchored at rows 4, 17 and 30 in columns I and N.
# Slot headings follow the real Week 12 slate: there is a genuine Wednesday
# night game and a Black Friday game this week, and all 32 teams play, so
# nobody is on bye. Each matchup takes the window that actually distinguishes
# it, since the Sunday noon window is the largest share of all six.
MATCHUPS = [
    dict(
        slot="THANKSGIVING GAME",
        away="Taylor Gang", home="Finding Nico",
        rosters=[
            ("TAYLOR GANG (CJ)", [
                "Deshaun Watson — vs. LV (SNF), 19.9 proj",
                "Parker Washington — vs. TEN (Sun noon), 17.7 proj",
                "Chuba Hubbard — at TB (MNF), 17.0 proj",
            ]),
            ("FINDING NICO (Mitchell)", [
                "Jahmyr Gibbs — vs. CHI (Thanksgiving noon), 25.6 proj",
                "Dak Prescott — vs. PHI (Thanksgiving 3:30), 19.5 proj",
                "Travis Kelce and DJ Moore — both vs. KC (Thanksgiving night), "
                "11.9 and 12.9 proj",
            ]),
        ],
        trend="Mitchell has 69.9 projected points on Thanksgiving Thursday — "
              "57.7% of his total, the biggest single-day dependency on the "
              "board, spread across all three Thursday games. CJ has 10.9 "
              "there, the smallest Thursday share of anyone, and is decided "
              "Sunday night and Monday instead. Mitchell is 4-7 but power #4 "
              "and on a W3 after the league-high 162.90; CJ is 6-5 but power "
              "#9 on 43.0% all-play.",
        h2h="CJ 5-3 Mitchell — CJ is Mitchell's listed rival. CJ took the Week "
            "6 meeting 125.46-85.52.",
    ),
    dict(
        slot="BLACK FRIDAY GAME",
        away="RIPukachu", home="Runnin' Rezac",
        rosters=[
            ("RIPUKACHU (John — was Pukachu)", [
                "Tee Higgins — vs. NO (Sun noon), 17.2 proj",
                "Kyren Williams — vs. GB (Wednesday night), 16.8 proj",
                "Jonah Coleman — at PIT (Black Friday), 16.0 proj",
            ]),
            ("RUNNIN' REZAC (Logan)", [
                "Joe Burrow — vs. NO (Sun noon), 24.8 proj",
                "Justin Jefferson — vs. ATL (Sun noon), 20.1 proj",
                "Jaylen Warren — vs. DEN (Black Friday), 14.8 proj",
            ]),
        ],
        trend="John's Jonah Coleman and Logan's Jaylen Warren start in the "
              "same NFL game — Denver at Pittsburgh, 2:00p CT Friday — on "
              "opposite sides. It is the most spread-out matchup of the week — "
              "six different game windows — and carries the largest Friday "
              "total on the board at 30.8 points, plus John's Kyren Williams "
              "in Wednesday night's opener against Green Bay. John "
              "is power #3 on 130.5 PF/G; Logan is 5-6 despite power #6, and "
              "posted Week 11's largest miss (92.10 on 125.1) and still won.",
        h2h="John 6-4 Logan — Logan won the Week 6 meeting 152.52-100.08.",
    ),
    dict(
        slot="SUNDAY NOON GAME",
        away="A Slap in the Face", home="The Aura Farm",
        rosters=[
            ("A SLAP IN THE FACE (Isaac)", [
                "Ja'Marr Chase — vs. NO (Sun noon), 25.9 proj",
                "C.J. Stroud — vs. BAL (Sun noon), 21.4 proj",
                "Saquon Barkley — at DAL (Thanksgiving 3:30, Questionable), "
                "14.2 proj",
            ]),
            ("THE AURA FARM (Christian)", [
                "Trevor Lawrence — vs. TEN (Sun noon), 23.3 proj",
                "CeeDee Lamb — vs. PHI (Thanksgiving 3:30), 20.3 proj",
                "Bhayshul Tuten — vs. TEN (Sun noon, Questionable), 18.6 proj",
            ]),
        ],
        trend="Isaac's 137.1 is the highest as-set projection on the Week 12 "
              "board and he is a 55% favorite, but he is power #7 on 45.5% "
              "all-play. Christian is power #2 on the league's worst luck "
              "rating (-2.2) and lost Week 11 by 0.60. 151 of their combined "
              "projected points — 57% — fall in the Sunday noon window, the "
              "most concentrated matchup on the board.",
        h2h="Christian 7-4 Isaac — a mutual rivalry game, each man's profile "
            "lists the other. Christian won the Week 6 meeting 124.34-78.98.",
    ),
    dict(
        slot="SUNDAY AFTERNOON GAME",
        away="Amon that inhaler", home="Joey Lunchbox",
        rosters=[
            ("AMON THAT INHALER (Grant)", [
                "Patrick Mahomes — at BUF (Thanksgiving night), 18.5 proj",
                "Amon-Ra St. Brown — vs. CHI (Thanksgiving noon), 17.8 proj",
                "Quinshon Judkins — vs. LV (SNF), 15.3 proj",
            ]),
            ("JOEY LUNCHBOX (Leif)", [
                "Josh Allen — vs. KC (Thanksgiving night), 18.7 proj",
                "Christian McCaffrey — vs. SEA (Sun 3:25), 18.1 proj",
                "Mike Evans — vs. SEA (Sun 3:25), 14.9 proj",
            ]),
        ],
        trend="Leif has the league's best record at 8-3 and sits power #8, on "
              "48.8% all-play and a +2.6 luck rating, second-highest in the "
              "league. Grant is 5-6 at power #5 and projects 124.2 to Leif's "
              "117.4. 46.8 of Leif's points — 40% — are in the Sunday 3:25 "
              "window, where McCaffrey and Evans are 49ers teammates in the "
              "same game and Diggs is in the other. Mahomes faces Allen head "
              "to head on Thanksgiving night.",
        h2h="Leif 6-3 Grant — Leif won the Week 6 meeting 112.30-105.52.",
    ),
    dict(
        slot="SUNDAY NIGHT GAME",
        away="PA Dive Your Way", home="The Basement Of KK",
        rosters=[
            ("PA DIVE YOUR WAY (Kaleb)", [
                "Jared Goff — vs. CHI (Thanksgiving noon), 16.9 proj",
                "Ashton Jeanty — at CLE (SNF), 15.3 proj",
                "Breece Hall — at MIA (Sun noon), 13.8 proj",
            ]),
            ("THE BASEMENT OF KK (Peter)", [
                "Bijan Robinson — at MIN (Sun noon), 17.7 proj",
                "Kirk Cousins — vs. ATL (Sun noon), 17.4 proj",
                "Brock Bowers — at CLE (SNF, Questionable), 15.1 proj",
            ]),
        ],
        trend="Both teams run through Cleveland-Las Vegas on Sunday night: "
              "Kaleb starts Jeanty, Tre Tucker and Michael Mayer, Peter starts "
              "Bowers and Denzel Boston. 57 combined points, 28% of the "
              "matchup, the highest Sunday-night share on the board. Peter "
              "also has both sides of Atlanta at Minnesota in Robinson and "
              "Cousins. Kaleb is 7-4 but projects 93.1, the lowest number of "
              "the week; Peter is a 61% favorite, the biggest edge of the "
              "week, and is 5-6 on an L4.",
        h2h="Peter 7-2 Kaleb — still Peter's best record against anyone in "
            "the league. Kaleb won the Week 6 meeting 94.36-69.78.",
    ),
    dict(
        slot="MONDAY NIGHT GAME",
        away="I Didn't Hear No Bell", home="Uncut Cokerr",
        rosters=[
            ("I DIDN'T HEAR NO BELL (Noah)", [
                "Jayden Daniels — at ARI (Sun 3:25), 22.5 proj",
                "James Cook III — vs. KC (Thanksgiving night), 14.5 proj",
                "Sam LaPorta — vs. CHI (Thanksgiving noon, Questionable), "
                "10.8 proj",
            ]),
            ("UNCUT COKERR (Adam)", [
                "Bucky Irving — vs. CAR (MNF), 21.0 proj",
                "Chris Olave — at CIN (Sun noon), 14.4 proj",
                "Bryce Young — at TB (MNF), 14.2 proj",
            ]),
        ],
        trend="Adam's 138.2 optimal is the highest number on the Week 12 "
              "board, but his lineup as currently set projects 104.3 — a "
              "33.9-point gap, the largest on the slate as of Tuesday, with "
              "the difference sitting on his bench. That is why ESPN has "
              "power-#1 Adam a 49% underdog to 3-8 Noah. Adam owns both sides "
              "of the Monday nighter in Irving and Young, 35.2 points, the "
              "biggest Monday exposure of the week. Noah is last in the league "
              "in all-play at 38-83 (31.4%) and 11th in PF/G at 104.6.",
        h2h="Adam 7-1 Noah — Adam won the Week 6 meeting 132.66-108.50.",
    ),
]

NOTES = [
    ("What surprised me?", "[ note ]"),
    ("Who deserves praise?", "[ note ]"),
    ("Who deserves heat?", "[ note ]"),
    ("Best joke / callback", "[ note ]"),
    ("Episode theme", "[ one sentence ]"),
]

# ----------------------------------------------------------------- composition


def compose():
    V = [["" for _ in range(COLS)] for _ in range(ROWS)]

    def put(row, col, val):
        V[row - 1][ord(col) - 65] = val

    # header
    put(1, "B", "PLAYERS FF PODCAST — 2026")
    put(2, "B", "Week")
    put(2, "C", WEEK)
    put(2, "D", "Recording Date")
    put(2, "E", RECORDING)
    put(3, "E", "AGENDA")
    put(4, "B", "Guest")
    put(4, "C", "Intro Song")
    put(5, "B", GUEST)
    put(5, "C", SONG)

    # agenda, rows 4-11
    for i, name in enumerate(AGENDA):
        put(4 + i, "D", i + 1)
        put(4 + i, "E", name)
    put(11, "C", "Prediction Record")
    put(12, "C", PREDICTION_RECORD)
    put(12, "E", LOCK)

    # hot seat, rows 15-17
    put(14, "B", "HOT SEAT")
    put(15, "D", "Why")
    for i, (team, why) in enumerate(HOT_SEAT):
        put(15 + i, "A", i + 1)
        put(15 + i, "B", team)
        put(15 + i, "E", why)

    # weekly awards, rows 19-24
    put(19, "B", "WEEKLY AWARDS")
    put(20, "B", "Award")
    put(20, "C", "Player / Moment")
    put(20, "E", "Team Owner")
    for i, (label, body, who) in enumerate(AWARDS):
        put(21 + i, "B", label)
        put(21 + i, "C", body)
        put(21 + i, "E", who)

    # team of the week, rows 27-39 — cut for Week 12 (2026-11-24, Peter's
    # call); just the header and a skip note, no roster headers or rows.
    put(27, "B", "TEAM OF THE WEEK")
    put(28, "B", TOTW_SKIPPED)
    for i, (label, val) in enumerate(TOTW_META):
        put(29 + i, "B", label)
        put(29 + i, "C", val)
    for i, (slot, name, rd, rank) in enumerate(TOTW_ROSTER):
        put(29 + i, "D", slot)
        put(29 + i, "E", name)
        put(29 + i, "F", rd)
        put(29 + i, "G", rank)
    for i, line in enumerate(IMPACT):
        put(35 + i, "B", i + 1)
        put(35 + i, "C", line)

    # matchup blocks: rows 4/17/30, column pairs (I,K) and (N,P)
    anchors = [(r, L, R) for r in (4, 17, 30) for L, R in (("I", "K"), ("N", "P"))]
    if len(MATCHUPS) != len(anchors):
        raise SystemExit(f"{len(MATCHUPS)} matchups for {len(anchors)} blocks")
    if len(PICK) != len(MATCHUPS):
        raise SystemExit(f"{len(PICK)} picks for {len(MATCHUPS)} matchups")
    for m, pick, (r, L, R) in zip(MATCHUPS, PICK, anchors):
        put(r, L, m["slot"])
        put(r + 1, L, m["away"])
        put(r + 1, "J" if L == "I" else "O", "vs.")
        put(r + 1, R, m["home"])
        body = "\n\n".join(
            "\n".join([team] + [f"• {b}" for b in bullets])
            for team, bullets in m["rosters"])
        put(r + 2, L, body)
        put(r + 3, L, "Trend / stat\n" + m["trend"])
        put(r + 4, L, "ALL-TIME H2H\n" + m["h2h"])
        put(r + 7, L, "PREDICTION")
        put(r + 8, L, pick)

    # Peter's notes, rows 43-48
    put(43, "B", "PETER'S NOTES / VOICE DUMP")
    for i, (label, val) in enumerate(NOTES):
        put(44 + i, "B", label)
        put(44 + i, "C", val)

    return V


def main(out_path):
    V = compose()
    filled = sum(1 for row in V for c in row if str(c).strip())
    with open(out_path, "w") as fh:
        json.dump({"range": f"'Podcast Week {WEEK} 2026'!A1:U{ROWS}",
                   "values": V}, fh, indent=1)
    print(f"wrote {out_path}: {filled} filled cells, "
          f"{len(MATCHUPS)} matchups, {len(AWARDS)} awards, "
          f"{len(HOT_SEAT)} hot-seat entries, {len(TOTW_ROSTER)} roster slots")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "wk12.json")
