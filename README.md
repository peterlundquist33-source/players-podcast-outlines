# Players FF Podcast — weekly outlines

Static host-prep pages. Not linked from the league site.

## Rebuild a week

```bash
# 1. export the sheet tab
gog sheets get <WORKBOOK_ID> "'Podcast Week N 2026'!A1:U48" \
    -a peterlundquist33@gmail.com --json > wkN.json

# 2. (only if that week has trades) rewrite the snapshot post-trade
python3 apply_trades.py \
    ~/repos/players-league/tools/data/2026-week-0N-preview.json \
    N post-trade-week-0N.json

# 3. pull deep matchup data from the players-league repo
python3 enrich.py \
    post-trade-week-0N.json \
    ~/repos/players-league/tools/data/2026-power-week-0M-.json \
    2026 N deep.json

# 4. render
python3 build.py wkN.json N 2026 week-0N.html deep.json
```

## Rebuild a week without the workbook

If the Google OAuth token is expired or the sheet is otherwise unreachable,
`compose_sheet.py` writes the same `{"values": ...}` payload from the
players-league data files plus the week's content, held in that file:

```bash
python3 apply_trades.py \
    ~/repos/players-league/tools/data/2026-week-05-preview.json \
    5 post-trade-week-05.json
python3 enrich.py \
    post-trade-week-05.json \
    ~/repos/players-league/tools/data/2026-power-week-04.json \
    2026 5 deep.json
python3 compose_sheet.py deep.json 5 wk5.json
python3 build.py wk5.json 5 2026 week-05.html deep.json
```

Week 5 was built this way. Anything the league data can't supply (guest,
recording date, intro song, Team of the Week pick, Peter's picks) is written
as a bracketed placeholder rather than guessed.

## Trades

The cached preview snapshot is always *pre-trade*. `apply_trades.py` holds the
verified transaction ledger and rewrites the snapshot itself, so lineup cards,
roster commentary, featured players and matchup totals all regenerate from
post-trade rosters — nothing is hand-edited into `week-0N.html`.

It refuses to write unless it can first reproduce the untouched snapshot's
`optimal_proj` and starter set for all twelve teams, using the league's own
optimal-lineup algorithm (`players-league/tools/league.py`). Starter slots
emptied by an outgoing player are refilled with the best startable bench player;
slots that were already empty stay empty. ESPN's `win_prob` cannot be
recomputed, so for any matchup a trade touched it is dropped and the renderer
shows the derived projected edge instead.

`TRADES` in `build.py` holds the editorial read — per-deal and full-day grades,
spotlight and caveats — and inserts its own agenda row.

`PICKS` in `build.py` holds the weekly predictions, keyed by week number.
`OWNERS` maps team name -> owner, so team renames don't break picks.
`RENAMES` corrects team names the sheet still has under an old label.
`RECAP` holds last week's results table; the sheet has no cells for it.
`BEACH_DRINKS` holds the beach-drink segment (one entry per owner, in power-board
order); like `RECAP` it lives in `build.py` so it survives a sheet rebuild.
