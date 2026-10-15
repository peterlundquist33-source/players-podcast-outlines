#!/usr/bin/env python3
"""Pull deep matchup data: lineup cards, game-window splits, season form."""
import json, sys, urllib.request, collections
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "D/ST", "K"]
WINDOWS = ["Thu", "Sun AM", "Sun Noon", "Sun Aft", "SNF", "MNF"]

# The show is recorded and listened to on Central time, so every kickoff is
# stated in Chicago wall-clock time rather than UTC or the stadium's zone.
SHOW_TZ = ZoneInfo("America/Chicago")
TEAMS_URL = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
             "teams?limit=50")

def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=25))

def nfl_teams():
    """Every current NFL abbreviation, so a bye can be told from a typo."""
    try:
        d = _get(TEAMS_URL)
        teams = {t["team"]["abbreviation"]
                 for s in d["sports"] for l in s["leagues"] for t in l["teams"]}
    except Exception as e:
        teams = set()
        print(f"  NFL team list unavailable ({e})")
    if len(teams) != 32:
        # Without the roster of real abbreviations a bye can't be told from a
        # bad mapping, and build.py would rather block than label either wrong.
        raise SystemExit(f"expected 32 NFL abbreviations, got {len(teams)}; "
                         "refusing to guess byes")
    return teams

def kickoff_ct(iso):
    """'2026-10-18T17:00Z' -> 'Sun 12:00p' Central. '' when ESPN has no time.

    Returning the empty string is deliberate: an unscheduled or malformed
    date leaves the kickoff blank instead of inventing a plausible one.
    """
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(iso or "", fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        ct = dt.astimezone(SHOW_TZ)
        return "%s %d:%02d%s" % (ct.strftime("%a"), ct.hour % 12 or 12,
                                 ct.minute, "a" if ct.hour < 12 else "p")
    return ""

def nfl_windows(season, week):
    """{TEAM: window} using kickoff time, plus opponents and kickoff times."""
    url = (f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={season}"
           f"&week={week}&seasontype=2")
    d = _get(url)
    out, games, opp, kick = {}, [], {}, {}
    for day, blk in sorted(d["content"]["schedule"].items()):
        for g in blk.get("games", []):
            comp = g["competitions"][0]
            iso = comp.get("date", "")            # e.g. 2026-09-28T00:20Z
            teams = [c["team"]["abbreviation"] for c in comp["competitors"]]
            ha = {c.get("homeAway"): c["team"]["abbreviation"]
                  for c in comp["competitors"]}
            if ha.get("home") and ha.get("away"):
                opp[ha["away"]] = "@" + ha["home"]
                opp[ha["home"]] = "vs " + ha["away"]
            addr = (comp.get("venue") or {}).get("address") or {}
            # A neutral-site international game keeps its own label: the
            # Central kickoff alone would read like an ordinary early game.
            site = addr.get("city", "") if addr.get("country", "USA") != "USA" else ""
            at = kickoff_ct(iso)
            for t in teams:
                kick[t] = {"at": at, "site": site}
            dow = day[-2:]                         # day of month
            hh = int(iso[11:13]) if len(iso) > 13 else 18
            # UTC -> window
            if day == sorted(d["content"]["schedule"])[0]:
                w = "Thu"
            elif hh == 0 and day == sorted(d["content"]["schedule"])[-1]:
                w = "MNF"
            elif hh == 0:
                w = "SNF"
            elif hh < 17:
                w = "Sun AM"        # London/Europe morning kickoff
            elif hh == 17:
                w = "Sun Noon"
            else:
                w = "Sun Aft"
            for t in teams:
                out[t] = w
            games.append((w, teams))
    return out, games, opp, kick

def lineup_card(away, home):
    """Pair starters slot by slot, canonical order."""
    def by_slot(side):
        d = collections.defaultdict(list)
        for p in side["players"]:
            if p["started"]:
                d[p["slot"]].append(p)
        for k in d:
            d[k].sort(key=lambda x: -x["proj"])
        return d
    A, H = by_slot(away), by_slot(home)
    rows = []
    for slot in SLOT_ORDER:
        a, h = A.get(slot, []), H.get(slot, [])
        for i in range(max(len(a), len(h))):
            pa = a[i] if i < len(a) else None
            ph = h[i] if i < len(h) else None
            rows.append({
                "slot": slot,
                "a": pa, "h": ph,
                "edge": round((pa["proj"] if pa else 0) - (ph["proj"] if ph else 0), 1),
            })
    return rows

def with_opponents(rows, opp, kick, teams):
    """Stamp each starter with the NFL team it faces and its kickoff.

    `bye` is set only for a real NFL abbreviation with no game this week, so
    an abbreviation the schedule doesn't know (a mapping bug) stays visible
    as neither opponent nor bye instead of being mislabelled a bye.
    """
    for row in rows:
        for side in ("a", "h"):
            p = row.get(side)
            if not p:
                continue
            pro = p.get("pro") or ""
            k = kick.get(pro) or {}
            p["opp"] = opp.get(pro, "")
            p["kick"] = k.get("at", "")
            p["site"] = k.get("site", "")
            p["bye"] = bool(pro in teams and pro not in opp)
    return rows

def window_split(side, tw):
    out = collections.OrderedDict((w, 0.0) for w in WINDOWS)
    unknown = 0.0
    for p in side["players"]:
        if not p["started"]:
            continue
        w = tw.get(p["pro"])
        if w in out:
            out[w] += p["proj"]
        else:
            unknown += p["proj"]
    return {k: round(v, 1) for k, v in out.items()}, round(unknown, 1)

def form_rows(power_path):
    d = json.load(open(power_path))["board"]["rows"]
    out = {}
    for i, r in enumerate(d, 1):
        aw, al = r["allplay"][0], r["allplay"][1]
        out[r["owner"]] = {
            "rank": i, "score": r["score"], "record": r["record"],
            "streak": r["streak"], "ppg": r["pf_pg"], "pf": r["pf"], "pa": r["pa"],
            "allplay": f"{aw}-{al}", "luck": r["luck"],
        }
    return out

def build(league_path, power_path, season, week):
    d = json.load(open(league_path))["data"]
    tw, _, opp, kick = nfl_windows(season, week)
    teams = nfl_teams()
    form = form_rows(power_path)
    out = []
    for m in d["matchups"]:
        a, h = m["away"], m["home"]
        ea, ua = window_split(a, tw)
        eh, uh = window_split(h, tw)
        out.append({
            "away": a["team"], "home": h["team"],
            "away_owner": a["owner"], "home_owner": h["owner"],
            "away_rec": a["record"], "home_rec": h["record"],
            "away_proj": a["projected"], "home_proj": h["projected"],
            "away_opt": a["optimal_proj"], "home_opt": h["optimal_proj"],
            "win_prob": a.get("win_prob"),
            # set by apply_trades.py when ESPN's win chance predates a trade
            "wp_stale": bool(a.get("wp_stale") or h.get("wp_stale")),
            "lineup": with_opponents(lineup_card(a, h), opp, kick, teams),
            "windows": {"away": ea, "home": eh, "away_unk": ua, "home_unk": uh},
            "form": {"away": form.get(a["owner"]), "home": form.get(h["owner"])},
        })
    return out

def self_test():
    """Kickoff conversion, including the cases that are easy to get wrong."""
    cases = [
        # (ESPN UTC date, expected Central label)
        ("2026-10-16T00:15Z", "Thu 7:15p"),   # TNF, UTC date rolls over a day
        ("2026-10-18T13:30Z", "Sun 8:30a"),   # London morning kickoff
        ("2026-10-18T17:00Z", "Sun 12:00p"),  # the noon window, not 0:00p
        ("2026-10-18T20:25Z", "Sun 3:25p"),
        ("2026-10-19T00:20Z", "Sun 7:20p"),   # SNF, still Sunday in Chicago
        ("2026-10-20T00:15Z", "Mon 7:15p"),   # MNF
        ("2026-11-15T18:00Z", "Sun 12:00p"),  # after the CDT -> CST switch
        ("2026-10-18T17:00:00Z", "Sun 12:00p"),
        ("", ""),                              # no date: no guessed kickoff
        ("not a date", ""),
    ]
    for iso, want in cases:
        got = kickoff_ct(iso)
        assert got == want, f"{iso!r}: got {got!r}, want {want!r}"
    print(f"kickoff_ct: {len(cases)} cases pass")

if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        self_test()
        raise SystemExit(0)
    lg, pw, season, week, dest = sys.argv[1:6]
    data = build(lg, pw, int(season), int(week))
    json.dump(data, open(dest, "w"), indent=1)
    print(f"wrote {dest}: {len(data)} matchups")
    m = data[0]
    print(" sample:", m["away"], "vs", m["home"], "| lineup rows:", len(m["lineup"]))
    print(" windows away:", m["windows"]["away"], "unknown:", m["windows"]["away_unk"])
    print(" form away:", m["form"]["away"])
    starters = [p for mm in data for r in mm["lineup"]
                for p in (r["a"], r["h"]) if p]
    timed = sum(1 for p in starters if p["opp"] and p["kick"])
    byes = sum(1 for p in starters if p["bye"])
    notime = [p for p in starters if p["opp"] and not p["kick"]]
    unknown = [p for p in starters if not p["opp"] and not p["bye"]]
    print(f" starters {len(starters)}: {timed} with kickoff, {byes} on bye, "
          f"{len(notime)} no kickoff time, {len(unknown)} unmapped pro team")
    for p in notime + unknown:
        print("  check:", p["name"], p["pro"], repr(p["opp"]))
