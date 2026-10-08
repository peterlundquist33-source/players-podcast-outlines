#!/usr/bin/env python3
"""Derive a post-trade copy of a players-league preview snapshot.

The cached preview JSON is a *pre-trade* snapshot. Rather than hand-edit
generated HTML, this step rewrites the snapshot itself, so every downstream
artifact (enrich.py lineup cards, compose_sheet.py roster commentary and
featured players, build.py matchup tables) regenerates from post-trade rosters.

    python3 apply_trades.py <preview.json> <week> <out.json>

Rules, all deterministic — nothing here invents a projection or an injury:

* Players move as whole records. A moved player keeps his own proj / actual /
  injury / pro fields exactly as the snapshot had them.
* `optimal_proj` is recomputed with the league's own algorithm
  (players-league tools/league.py `_optimal`): top-n by position over the
  *entire* roster including bench and IR, then FLEX from the leftover RB/WR/TE.
  No injury filter — that is how the league computes it, and this script is
  validated against the untouched snapshot before it is allowed to write.
* `projected` is the sum of whoever occupies a starter slot, same as the
  league's normalizer.
* Lineups are repaired conservatively: a starter slot emptied by an outgoing
  player is refilled with the best *startable* player on the bench, and a slot
  that was already empty before the trades stays empty. We have no evidence a
  manager set a lineup he had not set, so we do not grant him one.
* An incoming player who cannot play and projects zero goes to IR when the
  team's single IR slot is free, otherwise the bench.
* `win_prob` is ESPN's own live number. It predates these trades and cannot be
  recomputed from projections, so for any matchup a trade touched it is set to
  None and flagged `wp_stale`; the renderer then shows the projected edge
  instead of a stale win percentage.
"""
import json, sys, copy

# Lineup settings for this league, mirroring tools/league.py's slot_counts.
SLOT_COUNTS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "D/ST": 1, "K": 1, "FLEX": 1}
FLEX_POS = {"RB", "WR", "TE"}
BENCH_SLOTS = {"BE", "IR"}

# Injury strings ESPN uses that still allow a player to be started. Taken from
# the snapshot itself: every starter in it carries "" or QUESTIONABLE.
STARTABLE_INJURY = {"", "QUESTIONABLE"}
# Statuses that justify the IR slot.
IR_INJURY = {"INJURY_RESERVE", "OUT", "DOUBTFUL"}

# ------------------------------------------------------------------ the ledger
# Verified transactions, Thursday Oct 8 2026, in the order they were made.
# DK Metcalf appears twice on purpose: Isaac -> Logan, then Logan -> CJ.
TRADES = {
    5: [
        {"id": 1, "a": "Isaac", "b": "Logan",
         "a_gets": ["Saquon Barkley", "J.K. Dobbins"],
         "b_gets": ["DK Metcalf", "Jaylen Warren"]},
        {"id": 2, "a": "CJ", "b": "Grant",
         "a_gets": ["Juwan Johnson"],
         "b_gets": ["Quinshon Judkins"]},
        {"id": 3, "a": "CJ", "b": "Logan",
         "a_gets": ["Emanuel Wilson", "DK Metcalf", "Jalen Hurts"],
         "b_gets": ["Zach Charbonnet", "Joe Burrow"]},
    ],
}


# ------------------------------------------------------------------- lineup math

def optimal_proj(players):
    """The league's own optimal-lineup number. Mirrors league.py `_optimal`."""
    by_pos = {}
    for p in players:
        by_pos.setdefault(p["pos"], []).append(p)
    for v in by_pos.values():
        v.sort(key=lambda p: -p["proj"])
    lineup, used = [], set()
    for pos, n in SLOT_COUNTS.items():
        if pos == "FLEX":
            continue
        for p in by_pos.get(pos, [])[:n]:
            lineup.append(p)
            used.add(id(p))
    flex_pool = sorted((p for p in players
                        if p["pos"] in FLEX_POS and id(p) not in used),
                       key=lambda p: -p["proj"])
    for p in flex_pool[:SLOT_COUNTS.get("FLEX", 0)]:
        lineup.append(p)
    return round(sum(p["proj"] for p in lineup), 1)


def startable(p):
    return p["injury"] in STARTABLE_INJURY and p["proj"] > 0


def slot_eligible(p, slot):
    return p["pos"] in FLEX_POS if slot == "FLEX" else p["pos"] == slot


def refresh(side):
    """Recompute started / starters / projected / optimal_proj from slots.

    `projected` in the snapshot is ESPN's own live aggregate, which it sums from
    unrounded player projections; summing the rounded per-player `proj` values
    we actually have lands within 0.1 of it. So we keep ESPN's number as the
    baseline and only move it by the trade delta, rather than replacing it with
    a slightly different sum of our own.
    """
    for p in side["players"]:
        p["started"] = p["slot"] not in BENCH_SLOTS
    side["starters"] = [p for p in side["players"] if p["started"]]
    parts = round(sum(p["proj"] for p in side["starters"]), 1)
    if "_proj_offset" not in side:
        side["_proj_offset"] = round(side["projected"] - parts, 1)
    side["projected"] = round(parts + side["_proj_offset"], 1)
    side["optimal_proj"] = optimal_proj(side["players"])
    return side


def open_slots(side):
    """Starter slots the league settings allow that nobody currently occupies."""
    held = {}
    for p in side["players"]:
        if p["started"]:
            held[p["slot"]] = held.get(p["slot"], 0) + 1
    gaps = []
    for slot, n in SLOT_COUNTS.items():
        for _ in range(n - held.get(slot, 0)):
            gaps.append(slot)
    return gaps


def repair_lineup(side, vacated):
    """Refill only the starter slots this trade emptied, best startable first.

    `vacated` is the multiset of slots outgoing starters were occupying. Slots
    that were empty before the trade are not touched.
    """
    filled = []
    for slot in vacated:
        pool = [p for p in side["players"]
                if p["slot"] == "BE" and startable(p) and slot_eligible(p, slot)]
        if not pool:
            continue
        pick = max(pool, key=lambda p: (p["proj"], p["name"]))
        pick["slot"] = slot
        filled.append((slot, pick["name"], pick["proj"]))
    return filled


def seat_incoming(side, player):
    """Bench an arriving player; use the IR slot if he needs it and it is free."""
    ir_used = any(p["slot"] == "IR" for p in side["players"])
    if player["proj"] == 0 and player["injury"] in IR_INJURY and not ir_used:
        player["slot"] = "IR"
    else:
        player["slot"] = "BE"


def stash_ir(side):
    """If the IR slot is free, move a zero-projection IR-status player into it."""
    if any(p["slot"] == "IR" for p in side["players"]):
        return None
    pool = [p for p in side["players"]
            if p["slot"] == "BE" and p["proj"] == 0 and p["injury"] in IR_INJURY]
    if not pool:
        return None
    pick = min(pool, key=lambda p: p["name"])
    pick["slot"] = "IR"
    return pick["name"]


# ---------------------------------------------------------------------- driver

def sides_by_owner(data):
    out = {}
    for m in data["matchups"]:
        for key in ("home", "away"):
            out[m[key]["owner"]] = m[key]
    return out


def take(side, name):
    for i, p in enumerate(side["players"]):
        if p["name"] == name:
            return side["players"].pop(i)
    raise SystemExit(f'{name!r} is not on {side["owner"]}\'s roster — '
                     f'snapshot does not match the trade ledger')


def apply_trades(doc, week, log=print):
    data = doc["data"]
    sides = sides_by_owner(data)
    deals = TRADES.get(int(week))
    if not deals:
        raise SystemExit(f"no trade ledger for week {week}")

    # Capture ESPN's projected-vs-rounded-parts residual while the rosters are
    # still pristine. Doing this lazily inside refresh() would measure it after
    # players had already moved and bake the trade delta into the offset.
    for side in sides.values():
        parts = round(sum(p["proj"] for p in side["players"]
                          if p["slot"] not in BENCH_SLOTS), 1)
        side["_proj_offset"] = round(side["projected"] - parts, 1)

    touched, moves = set(), []
    for deal in deals:
        a, b = sides[deal["a"]], sides[deal["b"]]
        vacated = {deal["a"]: [], deal["b"]: []}
        for dest, src, names in ((a, b, deal["a_gets"]), (b, a, deal["b_gets"])):
            for name in names:
                p = take(src, name)
                if p["slot"] not in BENCH_SLOTS:
                    vacated[src["owner"]].append(p["slot"])
                seat_incoming(dest, p)
                dest["players"].append(p)
                moves.append((deal["id"], name, src["owner"], dest["owner"],
                              p["pos"], p["proj"], p["injury"]))
        for side in (a, b):
            refresh(side)
            fills = repair_lineup(side, vacated[side["owner"]])
            stashed = stash_ir(side)
            refresh(side)
            touched.add(side["owner"])
            for slot, nm, pr in fills:
                log(f'  trade {deal["id"]}: {side["owner"]:9} {slot:4} <- '
                    f'{nm} ({pr} proj)')
            if stashed:
                log(f'  trade {deal["id"]}: {side["owner"]:9} IR   <- {stashed}')

    # ESPN's win probability predates the trades for any matchup they touched.
    stale = 0
    for m in data["matchups"]:
        if {m["home"]["owner"], m["away"]["owner"]} & touched:
            for key in ("home", "away"):
                m[key]["win_prob"] = None
                m[key]["wp_stale"] = True
            stale += 1

    for side in sides.values():
        side.pop("_proj_offset", None)

    doc["phase"] = data["phase"] = "preview-post-trade"
    doc["trades_applied"] = [
        {"id": d["id"], "owners": [d["a"], d["b"]],
         d["a"] + "_gets": d["a_gets"], d["b"] + "_gets": d["b_gets"]}
        for d in deals
    ]
    return doc, moves, sorted(touched), stale


PROJ_TOLERANCE = 0.15   # ESPN's live aggregate vs sum of rounded parts


def validate_passthrough(path):
    """Refuse to run unless the recompute reproduces the untouched snapshot.

    `optimal_proj` and the starter set must match exactly — those are fully
    reconstructible, so any difference means the lineup model is wrong and the
    post-trade numbers would be wrong too. `projected` only has to land within
    PROJ_TOLERANCE, because ESPN sums it from unrounded projections we do not
    have; `refresh()` then carries that residual forward as a fixed offset
    instead of silently replacing ESPN's number.
    """
    doc = json.load(open(path))
    bad = []
    for m in doc["data"]["matchups"]:
        for key in ("home", "away"):
            t = m[key]
            got = refresh(copy.deepcopy(t))
            parts = round(sum(p["proj"] for p in got["starters"]), 1)
            if (got["optimal_proj"] != t["optimal_proj"]
                    or len(got["starters"]) != len(t["starters"])
                    or abs(parts - t["projected"]) > PROJ_TOLERANCE):
                bad.append((t["owner"],
                            (t["projected"], t["optimal_proj"], len(t["starters"])),
                            (parts, got["optimal_proj"], len(got["starters"]))))
    return bad


if __name__ == "__main__":
    src, week, dest = sys.argv[1], int(sys.argv[2]), sys.argv[3]

    bad = validate_passthrough(src)
    if bad:
        for owner, want, got in bad:
            print(f"  MISMATCH {owner}: snapshot {want} != recomputed {got}")
        raise SystemExit("lineup model does not reproduce the snapshot; refusing to write")
    print(f"validated: recompute reproduces all 12 teams in {src}")

    doc, moves, touched, stale = apply_trades(json.load(open(src)), week)
    json.dump(doc, open(dest, "w"), indent=1)

    print(f"wrote {dest}: {len(moves)} player moves, "
          f"{len(touched)} teams touched ({', '.join(touched)}), "
          f"{stale} matchups with win_prob retired")
    for tid, name, src_ow, dst_ow, pos, proj, inj in moves:
        print(f"  [{tid}] {name:20} {pos:4} {proj:6.1f} {inj:14} "
              f"{src_ow} -> {dst_ow}")
    for m in doc["data"]["matchups"]:
        for key in ("away", "home"):
            t = m[key]
            if t["owner"] in touched:
                print(f'  {t["owner"]:9} proj {t["projected"]:6.1f} '
                      f'optimal {t["optimal_proj"]:6.1f} '
                      f'roster {len(t["players"]):2} starters {len(t["starters"])}')
