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
    "Maye Be Cook'd": "Noah", "Taylor Gang": "CJ",
}
# Names the sheet still has under an old label.
RENAMES = {"Achane Smokin CiGarretts": "Maye Be Cook'd",
           "Burrowed Treasure": "Taylor Gang"}

# Peter's weekly picks, by owner.
PICKS = {
    3: ["Logan", "CJ", "Grant", "Kaleb", "Christian", "Leif"],
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
                "trend": strip_label(cell(V, r + 3, L), "TREND / STAT"),
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
    W = ["Thu", "Sun Noon", "Sun Aft", "SNF", "MNF"]

    fa, fh = m["form"]["away"], m["form"]["home"]
    if fa and fh:
        A('<div class="form">')
        for f, who in ((fa, m["away_owner"]), (fh, m["home_owner"])):
            A('<div><b>#%d</b> %s · %s (%s) · %.1f ppg · all-play %s · luck %+.1f</div>'
              % (f["rank"], E(who), E(f["record"]), E(f["streak"]),
                 f["ppg"], E(f["allplay"]), f["luck"]))
        A('</div>')

    def nm(pl):
        if not pl:
            return '<span class="dim">—</span>'
        flag = ' <i class="inj" title="%s">!</i>' % E(pl["injury"]) if pl["injury"] else ''
        return '%s <span class="dim">%s</span>%s' % (E(pl["name"]), E(pl["pro"]), flag)

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
        A('<tr><td class="who">%s</td>' % E(who))
        for w in W:
            v = vals.get(w, 0)
            if not v:
                A('<td class="zero">·</td>')
            else:
                A('<td class="%s">%.0f</td>' % ("hot" if v == peak else "", v))
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

    P = []
    A = P.append
    A(f'<!doctype html><html lang="en"><head><meta charset="utf-8">')
    A(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    A(f'<meta name="robots" content="noindex,nofollow">')
    A(f'<title>Week {week} — Players FF Podcast Outline</title>')
    A('<link rel="stylesheet" href="style.css"></head><body>')
    nav = [("Agenda", "agenda")] if agenda else []
    for m in b:
        nav.append((f'{m["slot"].replace(" GAME","").title()} · {m["away"]} v {m["home"]}',
                    slug(m["away"] + "-" + m["home"])))
    if awards:      nav.append(("Weekly Awards", "awards"))
    if totw_roster: nav.append(("Team of the Week", "totw"))
    if hotseat:     nav.append(("Hot Seat", "hotseat"))

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
        if m["trend"]:
            A(f'<p class="trend"><b>Trend / stat</b>{E(m["trend"])}</p>')
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

    A('</main><footer>Players FF Podcast · outline</footer></body></html>')
    return "\n".join(P)

if __name__ == "__main__":
    src, week, season, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    deep = load_deep(sys.argv[5]) if len(sys.argv) > 5 else []
    V = load(src)
    pathlib.Path(out).write_text(page(V, week, season, deep))
    print("wrote", out)
