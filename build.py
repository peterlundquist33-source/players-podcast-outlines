#!/usr/bin/env python3
"""Build podcast outline pages from a Google Sheet export (tools/wk*.json)."""
import json, html, re, sys, pathlib

ORDER = ["THURSDAY NIGHT GAME", "SUNDAY NOON GAME", "SUNDAY AFTERNOON GAME",
         "SUNDAY NIGHT GAME", "MONDAY NIGHT GAME"]

# Team name -> owner. Keeps picks working even when a team gets renamed.
OWNERS = {
    "Uncut Cokerr": "Adam", "Joey Lunchbox": "Leif", "The Aura Farm": "Christian",
    "The Basement Of KK": "Peter", "Runnin' Rezac": "Logan", "Pukachu": "John",
    "Amon that inhaler": "Grant", "PA Dive Your Way": "Kaleb",
    "Finding Nico": "Mitchell", "A Slap in the Face": "Isaac",
    "Maye Be Cook'd": "Noah", "Maye, Quit Football": "Noah",
    "Maye Have Downs": "Noah", "Taylor Gang": "CJ",
}
# Names the sheet still has under an old label.
RENAMES = {"Achane Smokin CiGarretts": "Maye, Quit Football",
           "Maye Be Cook'd": "Maye, Quit Football",
           "Burrowed Treasure": "Taylor Gang"}

# Peter's weekly picks, by owner.
PICKS = {
    3: ["Logan", "CJ", "Grant", "Kaleb", "Christian", "Leif"],
}

# Last week's results, by the week the outline is for. The sheet has no cells for
# this, and it has to survive a sheet rebuild, so it lives here like TEAM_OF_WEEK.
#   lead     — one line the host opens on
#   results  — (matchup, final, preview pick, verdict) rows, as played
#   notes    — standings/trend bullets
RECAP = {
    5: {
        "title": "Last Week — Week 4",
        "lead": "The preview went 4–2 on picks. Both misses were blowouts the other way: "
                "Kaleb over Grant, and Peter over Leif by 80.2.",
        "results": [
            ("CJ 114.6 — Noah 110.5",        "CJ by 4.1",        "CJ by 19",        "hit"),
            ("Grant 104.4 — Kaleb 109.6",    "Kaleb by 5.2",     "Grant by 9",      "miss"),
            ("Isaac 110.3 — John 135.7",     "John by 25.4",     "John by 11",      "hit"),
            ("Mitchell 102.5 — Adam 146.8",  "Adam by 44.3",     "Adam by 21",      "hit"),
            ("Leif 82.8 — Peter 163.0",      "Peter by 80.2",    "Leif by 16",      "miss"),
            ("Christian 157.5 — Logan 112.9", "Christian by 44.6", "Christian by 21", "hit"),
        ],
        "notes": [
            "Two unbeatens left: Adam 4–0 (610.7 PF, most in the league) and Peter 4–0 "
            "(350.7 PA, fewest in the league). They play each other Sunday night.",
            "Peter's 162.98 was the top score of the week; Leif's 82.82 was the lowest, and "
            "all nine of Leif's starters finished under their projection.",
            "Christian is 2nd on the power board at 1–3 — 538.6 PF is 2nd-most in the league "
            "and his luck sits at −1.6. The schedule, not the roster.",
            "Logan is 0–4 having been hit for 603.6 points against, the most any team has "
            "allowed. Luck −1.7.",
            "Noah is 0–4 at 89.9 ppg and an all-play record of 7–37. That one is the roster.",
        ],
    },
}

# Beach-drink segment, by week. Every owner exactly once, ordered by power rank.
# The sheet has no cells for this, so it lives here to survive a sheet rebuild.
#   items — (power rank, owner, team, drink, note)
BEACH_DRINKS = {
    5: {
        "title": "Beach Drink Draft",
        "lead": "Twelve teams, twelve drinks, served in power-board order on a "
                "Saint Lucia beach. Earn your pour.",
        "items": [
            (1, "Adam", "Uncut Cokerr",
             "Chairman's Reserve 1931, neat, brought to your chair",
             "4–0, 152.7 ppg, 610.7 PF and an all-play of 40–4. He has beaten "
             "essentially every lineup in the league every week. Nobody asks what "
             "he wants anymore; it just shows up."),
            (2, "Christian", "The Aura Farm",
             "A flawless piña colada handed to the guy in the next chair over",
             "134.7 ppg and 538.6 PF, both 2nd in the league, all-play 29–15 — "
             "and a 1–3 record with luck −1.6. The drink is perfect. The schedule "
             "keeps giving it away."),
            (3, "John", "Pukachu",
             "Ice-cold Piton, straight from the cooler",
             "2–2, 124.6 ppg, all-play 26–18, power #3. Not a thing on the menu is "
             "more reliable and nobody writes home about it. Coming off a 25.4-point "
             "win over Isaac."),
            (4, "Peter", "The Basement Of KK",
             "Rum punch the bartender over-poured and hasn't noticed",
             "4–0 on 125.3 ppg — fine, not #1 fine — while allowing 350.7 points, "
             "fewest in the league, with luck +1.5. Undefeated and tilting the glass "
             "away so nobody looks in it."),
            (5, "CJ", "Taylor Gang",
             "Frozen strawberry daiquiri, no notes, no questions",
             "3–1, 116.3 ppg, all-play 24–20, power #5. Nobody's drink of the trip, "
             "nobody sends it back either. Beat Noah by 4.1 in Week 4, which is about "
             "how much rum is in it."),
            (6, "Kaleb", "PA Dive Your Way",
             "The 2-for-1 happy hour special",
             "3–1 and riding W2 on an all-play of 21–23 — he has lost more weekly "
             "head-to-heads than he's won. Great value. Do not watch the pour."),
            (7, "Leif", "Joey Lunchbox",
             "A coconut you hack open yourself",
             "123.5 ppg, 494.0 PF — a real drink in there most weeks. Then Week 4 "
             "came back dry: 82.8, the week's low, with all nine starters under "
             "projection. L2."),
            (8, "Mitchell", "Finding Nico",
             "Mango daiquiri from the beach cart, 90% ice, gone in four minutes",
             "112.3 ppg is middle of the pack, but 502.1 points allowed and a 44.3-point "
             "loss to Adam leave him 1–3. Looks like a drink from six feet away."),
            (9, "Isaac", "A Slap in the Face",
             "The free welcome cocktail from the plastic gun at check-in",
             "2–2 on 102.7 ppg and an all-play of 13–31 — only Noah has beaten fewer "
             "lineups. The record is hospitality, not quality."),
            (10, "Grant", "Amon that inhaler",
             "Piton you set in the sand 40 minutes ago",
             "2–2, 105.1 ppg, power #10, and his headline number is 389.0 points "
             "against, 2nd-fewest in the league. The schedule has been kind and he is "
             "still .500. Nobody is coming back for the second one."),
            (11, "Logan", "Runnin' Rezac",
             "An empty cup, a lime wedge, and a seagull",
             "0–4 with 603.6 points against, the most any team has allowed, luck −1.7. "
             "As of Wednesday the Week 5 lineup still had three empty starter slots, "
             "so this one isn't entirely the beach's fault."),
            (12, "Noah", "Maye Have Downs",
             "Pineapple left in the sun since Tuesday, filled with seawater",
             "0–4, 89.9 ppg and 359.5 PF, both last, all-play 7–37, power #12 — and "
             "projected favorite in four of five weeks. Hand-crafted. Locally sourced. "
             "Nobody is finishing it."),
        ],
    },
}

# Completed Team of the Week profiles. These preserve a finished profile when
# the source sheet is later rebuilt from its weekly template.
TEAM_OF_WEEK = {
    4: {
        "meta": [
            ("Team Name", "A Slap in the Face"),
            ("Owner", "Isaac Douglas"),
            ("Record", "2–1"),
            ("Best Finish", "Runner-up, #2 seed, 11–3 (2022)"),
            ("Playoff Appearances", "1"),
            ("Fun Fact", "His only playoff trip was the inaugural 2022 season, when he went 11–3 and finished runner-up. A Slap in the Face has kept the same name all five seasons."),
        ],
        "roster": [
            ("QB", "Bo Nix", "10", "QB #14"),
            ("RB", "Javonte Williams", "2", "RB #11"),
            ("RB", "Cam Skattebo", "5", "RB #20"),
            ("WR", "Ja'Marr Chase", "1", "WR #8"),
            ("WR", "Malik Nabers", "3", "WR #44"),
            ("TE", "Dalton Kincaid", "12", "TE #5"),
            ("FLEX", "Jaylen Warren", "7", "RB #17"),
            ("D/ST", "Lions D/ST", "16", "D/ST #12"),
            ("K", "Chris Boswell", "15", "K #6"),
        ],
        "impact": [
            "Ja'Marr Chase — 54.5 through three weeks, WR #8; coming off 24.8 in Week 3",
            "Javonte Williams — 50.5 through three weeks, RB #11; 18.3 in Week 3",
            "Dalton Kincaid — 44.3 through three weeks, TE #5 as a 12th-round pick",
            "Jaylen Warren — 40.6 through three weeks, RB #17 as a 7th-round pick",
            "Cam Skattebo — 36.6 through three weeks, RB #20 as a 5th-round pick",
        ],
    },
}

def load(path):
    return (json.load(open(path)).get("values") or [])

def cell(V, r, c):
    ci = ord(c) - 65
    row = V[r - 1] if r - 1 <= len(V) - 1 else []
    return str(row[ci]).strip() if ci < len(row) and row[ci] is not None else ""

def rosters(txt):
    """One cell holds both rosters, separated by a blank line."""
    out, cur = [], None
    for line in txt.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("•"):
            if cur:
                cur[1].append(s.lstrip("• ").strip())
        else:
            cur = (s, [])
            out.append(cur)
    return out

def fix_team(name):
    return RENAMES.get(name.strip(), name.strip())

def strip_label(txt, label):
    t = txt.strip()
    return t[len(label):].strip() if t.upper().startswith(label) else t

def matchups(V):
    blocks = []
    for r in (4, 17, 30):
        for L, R in (("I", "K"), ("N", "P")):
            slot = cell(V, r, L)
            if not slot:
                continue
            blocks.append({
                "slot": slot,
                "away": fix_team(cell(V, r + 1, L)),
                "home": fix_team(cell(V, r + 1, R)),
                "rosters": rosters(cell(V, r + 2, L)),
                "h2h": strip_label(cell(V, r + 4, L), "ALL-TIME H2H"),
            })
    blocks.sort(key=lambda b: ORDER.index(b["slot"]) if b["slot"] in ORDER else 99)
    return blocks

def attach_picks(blocks, week):
    picks = PICKS.get(int(week), [])
    for i, b in enumerate(blocks):
        owner = picks[i] if i < len(picks) else ""
        b["pick_owner"] = owner
        b["pick_team"] = next(
            (t for t in (b["away"], b["home"]) if OWNERS.get(t) == owner), "")
    return blocks

def rows_from(V, start, cols, stop_blank=True):
    out = []
    r = start
    while r <= len(V):
        vals = [cell(V, r, c) for c in cols]
        if stop_blank and not any(vals):
            break
        out.append(vals)
        r += 1
    return out

E = html.escape

def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")

def total(agenda):
    """Sum m:ss agenda durations -> 'M:SS'."""
    secs = 0
    for _, t in agenda:
        m = re.match(r"^\s*(\d+):(\d{2})\s*$", t or "")
        if m:
            secs += int(m.group(1)) * 60 + int(m.group(2))
    return f"{secs // 60}:{secs % 60:02d}"

def render_deep(A, E, m, slug):
    """Lineup card + window split + season form for one matchup."""
    W = ["Thu", "Sun AM", "Sun Noon", "Sun Aft", "SNF", "MNF"]

    fa, fh = m["form"]["away"], m["form"]["home"]
    if fa and fh:
        A('<div class="form">')
        for f, who in ((fa, m["away_owner"]), (fh, m["home_owner"])):
            A('<div><b>#%d</b> %s · %s (%s) · %.1f ppg · all-play %s · luck %+.1f</div>'
              % (f["rank"], E(who), E(f["record"]), E(f["streak"]),
                 f["ppg"], E(f["allplay"]), f["luck"]))
        wp = m.get("win_prob")
        if wp is not None:
            A('<div><b>Win prob</b> %s %.0f%% · %s %.0f%%</div>'
              % (E(m["away_owner"]), wp * 100, E(m["home_owner"]), (1 - wp) * 100))
        A('</div>')

    def nm(pl):
        if not pl:
            return '<span class="dim">—</span>'
        flag = ' <i class="inj" title="%s">!</i>' % E(pl["injury"]) if pl["injury"] else ''
        pro = E(pl["pro"])
        if pl.get("opp"):
            pro += ' <span class="opp">%s</span>' % E(pl["opp"])
        return '%s <span class="dim">%s</span>%s' % (E(pl["name"]), pro, flag)

    A('<table class="lc"><thead><tr>')
    A('<th class="l">%s</th><th class="c">Proj</th><th class="c">Slot</th>'
      '<th class="c">Proj</th><th class="r">%s</th></tr></thead><tbody>'
      % (E(m["away"]), E(m["home"])))
    for row in m["lineup"]:
        a, h = row["a"], row["h"]
        ca = ' win' if row["edge"] > 0 else ''
        ch = ' win' if row["edge"] < 0 else ''
        pa = '%.1f' % a["proj"] if a else '—'
        ph = '%.1f' % h["proj"] if h else '—'
        A('<tr><td class="l%s">%s</td><td class="c%s">%s</td>'
          '<td class="c slotc">%s</td>'
          '<td class="c%s">%s</td><td class="r%s">%s</td></tr>'
          % (ca, nm(a), ca, pa, E(row["slot"]), ch, ph, ch, nm(h)))
    A('<tr class="tot"><td class="l">Projected</td><td class="c">%.1f</td>'
      '<td class="c"></td><td class="c">%.1f</td><td class="r">Projected</td></tr>'
      % (m["away_proj"], m["home_proj"]))
    A('</tbody></table>')

    A('<div class="win"><h5>Points by game window</h5><table class="wt"><thead><tr><th></th>')
    for w in W:
        A('<th>%s</th>' % w)
    A('</tr></thead><tbody>')
    for side, who in (("away", m["away_owner"]), ("home", m["home_owner"])):
        vals = m["windows"][side]
        peak = max(vals.values()) if vals else 0
        total = sum(vals.values()) or 0
        A('<tr><td class="who">%s</td>' % E(who))
        for w in W:
            v = vals.get(w, 0)
            if not v:
                A('<td class="zero">·</td>')
            else:
                pct = (v / total * 100) if total else 0
                A('<td class="%s">%.0f<span class="pct">%.0f%%</span></td>'
                  % ("hot" if v == peak else "", v, pct))
        A('</tr>')
    A('</tbody></table></div>')


def load_deep(path):
    try:
        return json.load(open(path))
    except Exception:
        return []

def match_deep(block, deep):
    """Find the deep record for a sheet matchup block, by owner pair."""
    want = {OWNERS.get(block["away"]), OWNERS.get(block["home"])}
    for m in deep:
        if {m["away_owner"], m["home_owner"]} == want:
            return m
    return None


def page(V, week, season, deep=()):
    b = attach_picks(matchups(V), week)
    guest = cell(V, 5, "B")
    song = cell(V, 5, "C")
    rec = cell(V, 2, "E")
    SKIP = ("overreaction", "total time")
    agenda = [(cell(V, r, "E"), cell(V, r, "F")) for r in range(4, 14)
              if cell(V, r, "E")
              and not any(k in cell(V, r, "E").lower() for k in SKIP)]
    awards = [(cell(V, r, "B"), cell(V, r, "C"), cell(V, r, "E"))
              for r in range(21, 25) if cell(V, r, "B")]
    totw_meta = [(cell(V, r, "B"), cell(V, r, "C")) for r in range(28, 34)
                 if cell(V, r, "B")]
    totw_roster = [(cell(V, r, "D"), cell(V, r, "E"), cell(V, r, "F"), cell(V, r, "G"))
                   for r in range(29, 38) if cell(V, r, "D")]
    impact = [(cell(V, r, "B"), cell(V, r, "C")) for r in range(35, 40)
              if cell(V, r, "C")]
    hotseat = [cell(V, r, "B") for r in range(15, 18) if cell(V, r, "B")]
    recap = RECAP.get(int(week))
    drinks = BEACH_DRINKS.get(int(week))
    if drinks and agenda:
        agenda.append((drinks["title"] + " — all 12 teams", ""))
    totw_override = TEAM_OF_WEEK.get(int(week))
    if totw_override:
        totw_meta = totw_override["meta"]
        totw_roster = totw_override["roster"]
        impact = [("", text) for text in totw_override["impact"]]

    P = []
    A = P.append
    A(f'<!doctype html><html lang="en"><head><meta charset="utf-8">')
    A(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    A(f'<meta name="robots" content="noindex,nofollow">')
    A(f'<title>Week {week} — Players FF Podcast Outline</title>')
    cssv = ""
    try:
        import hashlib
        cssv = "?v=" + hashlib.md5(
            pathlib.Path(__file__).with_name("style.css").read_bytes()
        ).hexdigest()[:8]
    except Exception:
        pass
    A('<link rel="stylesheet" href="style.css%s"></head><body>' % cssv)
    nav = [("Agenda", "agenda")] if agenda else []
    if recap:       nav.append((recap["title"], "recap"))
    for m in b:
        nav.append((f'{m["slot"].replace(" GAME","").title()} · {m["away"]} v {m["home"]}',
                    slug(m["away"] + "-" + m["home"])))
    if awards:      nav.append(("Weekly Awards", "awards"))
    if totw_roster: nav.append(("Team of the Week", "totw"))
    if hotseat:     nav.append(("Hot Seat", "hotseat"))
    if drinks:      nav.append((drinks["title"], "drinks"))

    A('<div class="bar"><a class="back" href="index.html">← Weeks</a>')
    A('<details class="menu"><summary>Jump to<span class="car">▾</span></summary><nav>')
    for label, sid in nav:
        A(f'<a href="#{sid}">{E(label)}</a>')
    A('</nav></details></div>')
    A('<header class="top">')
    A(f'<h1>Week {week}<span class="yr">{season}</span></h1>')
    A('<div class="meta">')
    if rec:   A(f'<span><b>Recording</b> {E(rec)}</span>')
    if guest: A(f'<span><b>Guest</b> {E(guest)}</span>')
    if song:  A(f'<span><b>Intro</b> {E(song)}</span>')
    A('</div></header><main>')

    if agenda:
        A('<section id="agenda" class="card agenda"><h2>Agenda</h2><ol>')
        for name, t in agenda:
            A(f'<li><span>{E(name)}</span><em>{E(t)}</em></li>')
        A('</ol>')
        A(f'<p class="total"><span>Total</span><em>{E(total(agenda))}</em></p>')
        A('</section>')

    if recap:
        A(f'<section id="recap" class="card"><h2>{E(recap["title"])}</h2>')
        if recap.get("lead"):
            A(f'<p class="h2h">{E(recap["lead"])}</p>')
        if recap.get("results"):
            A('<table><thead><tr><th>Matchup</th><th>Final</th><th>Preview pick</th>'
              '<th>Call</th></tr></thead><tbody>')
            for game, final, pick, verdict in recap["results"]:
                A(f'<tr><td>{E(game)}</td><td>{E(final)}</td><td>{E(pick)}</td>'
                  f'<td>{"✓" if verdict == "hit" else "✗"}</td></tr>')
            A('</tbody></table>')
        if recap.get("notes"):
            A('<h4>Where that leaves everyone</h4><ul class="over">')
            for n in recap["notes"]:
                A(f'<li>{E(n)}</li>')
            A('</ul>')
        A('</section>')

    A('<h2 class="hdr">Matchups</h2>')
    for m in b:
        A(f'<section id="{slug(m["away"] + "-" + m["home"])}" class="card game">')
        A(f'<div class="slot">{E(m["slot"].replace(" GAME",""))}</div>')
        A(f'<h3>{E(m["away"])} <i>vs</i> {E(m["home"])}</h3>')
        A('<div class="teams">')
        for tname, players in m["rosters"]:
            A(f'<div class="team"><h4>{E(tname)}</h4><ul>')
            for p in players:
                A(f'<li>{E(p)}</li>')
            A('</ul></div>')
        A('</div>')
        dm = match_deep(m, deep)
        if dm:
            render_deep(A, E, dm, slug)
        if m["h2h"]:
            A(f'<p class="h2h"><b>All-time H2H</b> {E(m["h2h"])}</p>')
        if m.get("pick_team"):
            A(f'<p class="pick"><b>Pick</b> <span class="won">{E(m["pick_team"])}</span>'
              f'<span class="ow">{E(m["pick_owner"])}</span></p>')
        else:
            A('<p class="pick"><b>Pick</b> <span class="blank">—</span></p>')
        A('</section>')

    if awards:
        A('<section id="awards" class="card"><h2>Weekly Awards</h2><dl class="awards">')
        for label, body, who in awards:
            A(f'<dt>{E(label)}</dt><dd>{E(body)}<span class="who">{E(who)}</span></dd>')
        A('</dl></section>')

    if totw_roster:
        A('<section id="totw" class="card"><h2>Team of the Week</h2>')
        if totw_meta:
            A('<dl class="kv">')
            for k, v in totw_meta:
                A(f'<dt>{E(k)}</dt><dd>{E(v)}</dd>')
            A('</dl>')
        A('<table><thead><tr><th>Pos</th><th>Player</th><th>Rd</th><th>Rank</th></tr></thead><tbody>')
        for pos, nm, rd, rk in totw_roster:
            A(f'<tr><td>{E(pos)}</td><td>{E(nm)}</td><td>{E(rd)}</td><td>{E(rk)}</td></tr>')
        A('</tbody></table>')
        if impact:
            A('<h4>Impact players</h4><ol class="impact">')
            for n, t in impact:
                A(f'<li>{E(t)}</li>')
            A('</ol>')
        A('</section>')

    if hotseat:
        A('<section id="hotseat" class="card"><h2>Hot Seat</h2><ul>')
        for h in hotseat:
            A(f'<li>{E(h)}</li>')
        A('</ul></section>')

    if drinks:
        A(f'<section id="drinks" class="card"><h2>{E(drinks["title"])}</h2>')
        if drinks.get("lead"):
            A(f'<p class="h2h">{E(drinks["lead"])}</p>')
        A('<dl class="drinks">')
        for rank, owner, team, drink, note in drinks["items"]:
            A(f'<dt><span class="rk">#{rank}</span>{E(drink)}</dt>'
              f'<dd>{E(note)}<span class="who">{E(team)} · {E(owner)}</span></dd>')
        A('</dl></section>')

    A('</main><footer>Players FF Podcast · outline</footer></body></html>')
    return "\n".join(P)

if __name__ == "__main__":
    src, week, season, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    deep = load_deep(sys.argv[5]) if len(sys.argv) > 5 else []
    V = load(src)
    pathlib.Path(out).write_text(page(V, week, season, deep))
    print("wrote", out)
