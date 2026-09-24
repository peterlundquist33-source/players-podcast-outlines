#!/usr/bin/env python3
"""Pull deep matchup data: lineup cards, game-window splits, season form."""
import json, sys, urllib.request, collections

SLOT_ORDER = ["QB", "RB", "WR", "TE", "FLEX", "D/ST", "K"]
WINDOWS = ["Thu", "Sun Noon", "Sun Aft", "SNF", "MNF"]

def nfl_windows(season, week):
    """{TEAM: window} using kickoff time."""
    url = (f"https://cdn.espn.com/core/nfl/schedule?xhr=1&year={season}"
           f"&week={week}&seasontype=2")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=25))
    out, games = {}, []
    for day, blk in sorted(d["content"]["schedule"].items()):
        for g in blk.get("games", []):
            comp = g["competitions"][0]
            iso = comp.get("date", "")            # e.g. 2026-09-28T00:20Z
            teams = [c["team"]["abbreviation"] for c in comp["competitors"]]
            dow = day[-2:]                         # day of month
            hh = int(iso[11:13]) if len(iso) > 13 else 18
            # UTC -> window
            if day == sorted(d["content"]["schedule"])[0]:
                w = "Thu"
            elif hh == 17:
                w = "Sun Noon"
            elif hh in (20, 21):
                w = "Sun Aft"
            elif hh == 0 and day == sorted(d["content"]["schedule"])[-1]:
                w = "MNF"
            elif hh == 0:
                w = "SNF"
            else:
                w = "Sun Aft"
            for t in teams:
                out[t] = w
            games.append((w, teams))
    return out, games

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
    tw, _ = nfl_windows(season, week)
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
            "lineup": lineup_card(a, h),
            "windows": {"away": ea, "home": eh, "away_unk": ua, "home_unk": uh},
            "form": {"away": form.get(a["owner"]), "home": form.get(h["owner"])},
        })
    return out

if __name__ == "__main__":
    lg, pw, season, week, dest = sys.argv[1:6]
    data = build(lg, pw, int(season), int(week))
    json.dump(data, open(dest, "w"), indent=1)
    print(f"wrote {dest}: {len(data)} matchups")
    m = data[0]
    print(" sample:", m["away"], "vs", m["home"], "| lineup rows:", len(m["lineup"]))
    print(" windows away:", m["windows"]["away"], "unknown:", m["windows"]["away_unk"])
    print(" form away:", m["form"]["away"])
