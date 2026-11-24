#!/usr/bin/env python3
"""Re-derive every factual claim in wk12_compose.py from the league data.

A Week 8 build once shipped three superlatives ("highest projection on the
slate" among them) that were all wrong on audit, so nothing in the Week 12
outline is asserted without being recomputed here. Run this before pushing
the tab; it exits non-zero on the first mismatch.

    python3 verify_wk12.py
"""
import json, collections, sys, pathlib

LG = pathlib.Path.home() / "repos/players-league"
DATA = LG / "tools/data"
fails, checks = [], 0


def ck(label, got, want, tol=0.05):
    """Assert a derived value matches what the outline claims."""
    global checks
    checks += 1
    ok = (abs(got - want) <= tol) if isinstance(want, (int, float)) and \
         isinstance(got, (int, float)) else (got == want)
    if not ok:
        fails.append(f"{label}: derived {got!r}, outline says {want!r}")
    print(f"  {'ok ' if ok else 'FAIL'} {label}: {got!r}")


def load(name):
    return json.load(open(DATA / name))


# ------------------------------------------------------------ week 12 preview
prev = load("2026-week-12-preview.json")["data"]
deep = json.load(open("deep-12.json"))

proj, opt, wp = {}, {}, {}
for m in prev["matchups"]:
    for s in ("away", "home"):
        t = m[s]
        proj[t["owner"]] = t["projected"]
        opt[t["owner"]] = t["optimal_proj"]
        wp[t["owner"]] = t["win_prob"]

print("Week 12 board")
hi_set = max(proj.items(), key=lambda kv: kv[1])
ck("highest as-set projection is Isaac", hi_set[0], "Isaac")
ck("Isaac as-set projection", hi_set[1], 137.1)
hi_opt = max(opt.items(), key=lambda kv: kv[1])
ck("highest optimal is Adam", hi_opt[0], "Adam")
ck("Adam optimal", hi_opt[1], 138.2)
lo_set = min(proj.items(), key=lambda kv: kv[1])
ck("lowest as-set projection is Kaleb", lo_set[0], "Kaleb")
ck("Kaleb as-set projection", lo_set[1], 93.1)
gaps = {o: round(opt[o] - proj[o], 1) for o in proj}
big_gap = max(gaps.items(), key=lambda kv: kv[1])
ck("largest optimal-minus-set gap is Adam", big_gap[0], "Adam")
ck("Adam bench gap", big_gap[1], 33.9)
ck("Kaleb bench gap", gaps["Kaleb"], 17.0)
best_edge = max(wp.items(), key=lambda kv: kv[1])
ck("biggest win-prob edge is Peter", best_edge[0], "Peter")
ck("Peter win prob", best_edge[1], 0.61, tol=0.005)

# window shares
win = {}
for m in deep:
    for s in ("away", "home"):
        win[m[s + "_owner"]] = m["windows"][s]
thu = {o: w.get("Thu", 0) for o, w in win.items()}
share = {o: thu[o] / sum(win[o].values()) * 100 for o in win}
ck("biggest Thursday points is Mitchell", max(thu, key=thu.get), "Mitchell")
ck("Mitchell Thursday points", thu["Mitchell"], 69.9)
ck("Mitchell Thursday share %", round(share["Mitchell"], 1), 57.7)
ck("smallest Thursday points is CJ", min(thu, key=thu.get), "CJ")
ck("CJ Thursday points", thu["CJ"], 10.9)
ck("Leif Sunday-afternoon points", win["Leif"].get("Sun Aft", 0), 46.8)
ck("Leif Sun-Aft share %", round(win["Leif"]["Sun Aft"] /
   sum(win["Leif"].values()) * 100), 40)
ck("Adam Monday points", win["Adam"].get("MNF", 0), 35.2)

# per-matchup combined windows
for m in deep:
    comb = collections.Counter()
    for s in ("away", "home"):
        comb.update(m["windows"][s])
    tot = sum(comb.values())
    pair = (m["away_owner"], m["home_owner"])
    if pair == ("Isaac", "Christian"):
        ck("Isaac/Christian Sun-Noon points", round(comb["Sun Noon"]), 151)
        ck("Isaac/Christian Sun-Noon share %",
           round(comb["Sun Noon"] / tot * 100), 57)
    if pair == ("Kaleb", "Peter"):
        ck("Kaleb/Peter SNF points", round(comb["SNF"]), 57)
        ck("Kaleb/Peter SNF share %", round(comb["SNF"] / tot * 100), 28)
    if pair == ("John", "Logan"):
        ck("John/Logan Friday points", round(comb["Fri"], 1), 30.8)
        ck("John/Logan have Wednesday exposure", comb["Wed"] > 0, True)

fri = {}
wed = {}
for m in deep:
    c = collections.Counter()
    for s in ("away", "home"):
        c.update(m["windows"][s])
    fri[(m["away_owner"], m["home_owner"])] = c["Fri"]
    wed[(m["away_owner"], m["home_owner"])] = c["Wed"]
ck("largest Friday total is John/Logan",
   max(fri, key=fri.get), ("John", "Logan"))
# Grant also has a Wednesday starter (Christian Watson), so the outline claims
# only that John's Kyren Williams is in the Wednesday game, not exclusivity.
ck("John/Logan has six distinct game windows",
   len([w for w in win["John"] if win["John"][w] or win["Logan"][w]]), 6)
ck("largest single Wednesday exposure is John's",
   max(win, key=lambda o: win[o].get("Wed", 0)), "John")
ck("John Wednesday points", win["John"].get("Wed", 0), 16.8)

# no byes this week
starters = [p for m in deep for r in m["lineup"] for p in (r["a"], r["h"]) if p]
ck("starters on bye", sum(1 for p in starters if p["bye"]), 0)
ck("starters with a kickoff time", sum(1 for p in starters if p["kick"]),
   len(starters))

# same-game pairings the trend lines claim
by_name = {p["name"]: p for p in starters}
ck("Coleman is at PIT", by_name["Jonah Coleman"]["opp"], "@PIT")
ck("Warren hosts DEN", by_name["Jaylen Warren"]["opp"], "vs DEN")
ck("Coleman and Warren kick off together",
   by_name["Jonah Coleman"]["kick"], by_name["Jaylen Warren"]["kick"])
ck("McCaffrey is a 49er", by_name["Christian McCaffrey"]["pro"], "SF")
ck("Evans is a 49er", by_name["Mike Evans"]["pro"], "SF")
ck("Robinson is at MIN", by_name["Bijan Robinson"]["opp"], "@MIN")
ck("Cousins hosts ATL", by_name["Kirk Cousins"]["opp"], "vs ATL")
ck("Irving hosts CAR", by_name["Bucky Irving"]["opp"], "vs CAR")
ck("Young is at TB", by_name["Bryce Young"]["opp"], "@TB")

# ------------------------------------------------------------- power board 11
print("\nPower board after Week 11")
rows = {r["owner"]: r for r in load("2026-power-week-11.json")["board"]["rows"]}
ck("Noah is power #12", rows["Noah"]["rank"], 12)
ck("Peter is power #11", rows["Peter"]["rank"], 11)
ck("Kaleb is power #10", rows["Kaleb"]["rank"], 10)
ck("Noah all-play %", rows["Noah"]["allplay_pct"], 31.4)
ck("Noah all-play is lowest",
   min(rows, key=lambda o: rows[o]["allplay_pct"]), "Noah")
ck("Noah PF/G", rows["Noah"]["pf_pg"], 104.6)
ck("Noah PF/G rank", rows["Noah"]["ranks"]["pf_pg"], "11th of 12")
ck("lowest PF/G is Kaleb", min(rows, key=lambda o: rows[o]["pf_pg"]), "Kaleb")
ck("Kaleb PF/G", rows["Kaleb"]["pf_pg"], 103.7)
ck("Kaleb luck is highest", max(rows, key=lambda o: rows[o]["luck"]), "Kaleb")
ck("Kaleb luck", rows["Kaleb"]["luck"], 2.9)
ck("Christian luck is lowest",
   min(rows, key=lambda o: rows[o]["luck"]), "Christian")
ck("Christian luck", rows["Christian"]["luck"], -2.2)
ck("Leif luck", rows["Leif"]["luck"], 2.6)
ck("Leif record", rows["Leif"]["record"], "8-3")
ck("Leif is power #8", rows["Leif"]["rank"], 8)
ck("John PF/G", rows["John"]["pf_pg"], 130.5)
ck("John is power #3", rows["John"]["rank"], 3)
ck("Mitchell is power #4", rows["Mitchell"]["rank"], 4)
ck("Mitchell moved +3", rows["Mitchell"]["move"], 3)
ck("Mitchell streak", rows["Mitchell"]["streak"], "W3")
ck("Peter streak", rows["Peter"]["streak"], "L4")
ck("CJ is power #9", rows["CJ"]["rank"], 9)
ck("CJ all-play %", rows["CJ"]["allplay_pct"], 43.0)
ck("Isaac is power #7", rows["Isaac"]["rank"], 7)
ck("Isaac all-play %", rows["Isaac"]["allplay_pct"], 45.5)
ck("Christian is power #2", rows["Christian"]["rank"], 2)
ck("Adam is power #1", rows["Adam"]["rank"], 1)
ck("Grant is power #5", rows["Grant"]["rank"], 5)
ck("Logan is power #6", rows["Logan"]["rank"], 6)
ck("Leif all-play %", rows["Leif"]["allplay_pct"], 48.8)
ck("Kaleb all-play %", rows["Kaleb"]["allplay_pct"], 37.2)
ck("Peter all-play %", rows["Peter"]["allplay_pct"], 37.2)

# --------------------------------------------------------------- week 11 recap
print("\nWeek 11 results")
w11 = load("2026-week-11.json")["data"]
act, pr, margin = {}, {}, {}
for m in w11["matchups"]:
    a, h = m["away"], m["home"]
    for t in (a, h):
        act[t["owner"]] = t["actual"]
        pr[t["owner"]] = t["projected"]
    margin[(a["owner"], h["owner"])] = round(abs(a["actual"] - h["actual"]), 2)

ck("Week 11 low score is Peter", min(act, key=act.get), "Peter")
ck("Peter Week 11 score", act["Peter"], 66.30)
ck("Peter Week 11 projection", pr["Peter"], 88.0)
ck("Peter Week 11 miss", round(act["Peter"] - pr["Peter"], 1), -21.7)
ck("Peter had the lowest projection too", min(pr, key=pr.get), "Peter")
ck("Week 11 high score is Mitchell", max(act, key=act.get), "Mitchell")
ck("Mitchell Week 11 score", act["Mitchell"], 162.90)
ck("Mitchell beat projection by", round(act["Mitchell"] - pr["Mitchell"], 1), 45.2)
ck("Mitchell had the biggest beat",
   max(act, key=lambda o: act[o] - pr[o]), "Mitchell")
ck("largest Week 11 margin", max(margin.values()), 41.54)
ck("largest margin is Grant/Mitchell",
   max(margin, key=margin.get), ("Grant", "Mitchell"))
ck("narrowest Week 11 margin", min(margin.values()), 0.60)
ck("narrowest is John/Christian",
   min(margin, key=margin.get), ("John", "Christian"))
ck("highest Week 11 projection is Isaac", max(pr, key=pr.get), "Isaac")
ck("Isaac Week 11 projection", pr["Isaac"], 135.2)
ck("Isaac Week 11 score", act["Isaac"], 113.76)
ck("Isaac lost to Leif by", margin[("Isaac", "Leif")], 6.00)
ck("largest Week 11 miss is Logan",
   min(act, key=lambda o: act[o] - pr[o]), "Logan")
ck("Logan Week 11 miss", round(act["Logan"] - pr["Logan"], 1), -33.0)
ck("Logan beat Noah by", margin[("Noah", "Logan")], 2.94)
ck("John Week 11 score", act["John"], 134.34)
ck("Grant Week 11 score", act["Grant"], 121.36)

# starter-level claims
sl = [(p, t["owner"]) for m in w11["matchups"] for s in ("away", "home")
      for t in [m[s]] for p in t["starters"]]
diffs = sorted(sl, key=lambda x: x[0]["actual"] - x[0]["proj"])
worst, worst_o = diffs[0]
best, best_o = diffs[-1]
ck("worst Week 11 starter bust", worst["name"], "Ja'Marr Chase")
ck("Chase bust size", round(worst["actual"] - worst["proj"], 1), -17.3)
ck("Chase belongs to Isaac", worst_o, "Isaac")
ck("biggest Week 11 overperformance", best["name"], "Jonah Coleman")
ck("Coleman overperformance", round(best["actual"] - best["proj"], 1), 15.5)
ck("Coleman belongs to John", best_o, "John")
ck("Coleman score", best["actual"], 34.90)

pete = [p for p, o in sl if o == "Peter"]
ck("Peter starters under 7.5", sum(1 for p in pete if p["actual"] < 7.5), 7)
ck("Peter starters over 12", sum(1 for p in pete if p["actual"] > 12), 1)
ck("Peter's only starter over 12",
   [p["name"] for p in pete if p["actual"] > 12][0], "George Pickens")

allsc = sorted((t["actual"], w, t["owner"])
               for w in range(1, 12)
               for m in load(f"2026-week-{w:02d}.json")["data"]["matchups"]
               for s in ("away", "home") for t in [m[s]])
ck("Peter's 66.30 is 3rd-lowest in 2026",
   [o for _, _, o in allsc[:3]].count("Peter") == 1 and allsc[2][0] == 66.30, True)
ck("Peter's season low", min(a for a, _, o in allsc if o == "Peter"), 66.30)
ck("Mitchell's 2026 high", max(a for a, _, o in allsc if o == "Mitchell"), 162.90)

# ------------------------------------------------------------ all-time H2H
print("\nAll-time head-to-head (through 2025 + the Week 6 2026 meeting)")
import re, html as H
src = open(LG / "js/teams-data.js").read()
TD, _ = json.JSONDecoder().raw_decode(src[src.index("{"):])
FULL = {"Noah": "Noah Thesing", "Adam": "Adam Stockwell",
        "John": "John Lundquist", "Logan": "Logan Rezac",
        "Isaac": "Isaac Douglas", "Christian": "Christian Massett",
        "Grant": "Grant Sawyer", "Leif": "Leif Engen", "CJ": "CJ Woda",
        "Mitchell": "Mitchell Max", "Kaleb": "Kaleb Feahn",
        "Peter": "Peter Lundquist"}


def h2h(owner):
    t = re.sub(r"<[^>]+>", "|", TD[FULL[owner]]["h2h_html"])
    t = H.unescape(re.sub(r"\|+", "|", t)).strip("|").split("|")
    return {t[i]: t[i + 1] for i in range(0, len(t) - 1, 2)}


w6 = load("2026-week-06.json")["data"]
w6win = {}
for m in w6["matchups"]:
    a, h = m["away"], m["home"]
    w6win[frozenset((a["owner"], h["owner"]))] = (
        a["owner"] if a["actual"] > h["actual"] else h["owner"])

# (leader, trailer, record the outline prints)
CLAIMS = [("CJ", "Mitchell", "5-3"), ("John", "Logan", "6-4"),
          ("Christian", "Isaac", "7-4"), ("Leif", "Grant", "6-3"),
          ("Peter", "Kaleb", "7-2"), ("Adam", "Noah", "7-1")]
for lead, trail, want in CLAIMS:
    w, l = (int(x) for x in h2h(lead)[FULL[trail]].split("-"))
    winner = w6win[frozenset((lead, trail))]
    w += winner == lead
    l += winner == trail
    ck(f"{lead} leads {trail}", f"{w}-{l}", want)

ck("Week 12 repeats the Week 6 pairings",
   {frozenset((m["away_owner"], m["home_owner"])) for m in deep},
   set(w6win))
# rivalries the outline calls out
ck("Mitchell's listed rival is CJ", TD["Mitchell Max"]["rival"], "CJ Woda")
ck("Isaac's listed rival is Christian",
   TD["Isaac Douglas"]["rival"], "Christian Massett")
ck("Christian's listed rival is Isaac",
   TD["Christian Massett"]["rival"], "Isaac Douglas")
peter_h = {k: tuple(int(x) for x in v.split("-")) for k, v in h2h("Peter").items()}
ck("Kaleb is Peter's best H2H margin",
   max(peter_h, key=lambda k: peter_h[k][0] - peter_h[k][1]), "Kaleb Feahn")

# ------------------------------------------------- team of the week (Mitchell)
print("\nTeam of the Week: Finding Nico")
recs = json.JSONDecoder().raw_decode(
    (s := open(LG / "js/records.js").read())[s.index("{"):])[0]
ck("Mitchell all-time best week", recs["weekly"]["Mitchell Max"]["highest"]["score"], 175.92)
ck("Mitchell best-week year", recs["weekly"]["Mitchell Max"]["highest"]["year"], 2022)
ck("Mitchell best-week number", recs["weekly"]["Mitchell Max"]["highest"]["week"], 2)
ck("Mitchell playoff berths",
   sum(1 for a in recs["achievements"]["Mitchell Max"]
       if a["label"] == "Playoff Berth"), 2)
ck("Mitchell was 2025 runner-up",
   any(a["label"] == "Runner-Up" and a["year"] == 2025
       for a in recs["achievements"]["Mitchell Max"]), True)
seasons = re.findall(r"<span>(\d{4})</span><span[^>]*>([\d-]+)</span>",
                     TD["Mitchell Max"]["seasons_html"])
ck("Mitchell season records", dict(seasons),
   {"2022": "7-7", "2023": "7-7", "2024": "5-9", "2025": "7-7"})

# draft rounds + 2026 positional ranks for the roster the outline prints
pts = collections.defaultdict(float)
for w in range(1, 12):
    for m in load(f"2026-week-{w:02d}.json")["data"]["matchups"]:
        for s in ("away", "home"):
            for p in m[s]["players"]:
                pts[(p["name"], p["pos"])] += p["actual"]
bypos = collections.defaultdict(list)
for (n, pos), v in pts.items():
    bypos[pos].append((v, n))
posrank = {}
for pos, lst in bypos.items():
    for i, (v, n) in enumerate(sorted(lst, reverse=True), 1):
        posrank[(n, pos)] = i
drafted = {}
for t in load("2026-rankings.json")["grades"]["teams"]:
    for p in t["picks"]:
        drafted[p["name"]] = (p["round"], t["owner"])

ROSTER = [("Dak Prescott", "QB", "FA", 2), ("Jahmyr Gibbs", "RB", "1", 1),
          ("Jordan Mason", "RB", "FA", 48), ("Nico Collins", "WR", "2", 19),
          ("DJ Moore", "WR", "5", 28), ("Travis Kelce", "TE", "10", 5),
          ("Tyler Warren", "TE", "4", 12), ("Broncos D/ST", "D/ST", "12", 5),
          ("Dominic Zvada", "K", "FA", 13)]
for name, pos, rd, rank in ROSTER:
    ck(f"{name} 2026 {pos} rank", posrank[(name, pos)], rank)
    d = drafted.get(name)
    want_rd = "FA" if (d is None or d[1] != "Mitchell") else str(d[0])
    ck(f"{name} draft round column", want_rd, rd)
ck("Coleman was undrafted", "Jonah Coleman" in drafted, False)

print(f"\n{checks} checks run")
if fails:
    print(f"\n{len(fails)} FAILED:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("all claims verified against the league data")
