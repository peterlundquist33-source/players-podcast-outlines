# Players FF Podcast — weekly outlines

Static host-prep pages. Not linked from the league site.

## Rebuild a week

```bash
# 1. export the sheet tab
gog sheets get <WORKBOOK_ID> "'Podcast Week N 2026'!A1:U48" \
    -a peterlundquist33@gmail.com --json > wkN.json

# 2. pull deep matchup data from the players-league repo
python3 enrich.py \
    ~/repos/players-league/tools/data/2026-week-0N-preview.json \
    ~/repos/players-league/tools/data/2026-power-week-0M-.json \
    2026 N deep.json

# 3. render
python3 build.py wkN.json N 2026 week-0N.html deep.json
```

## Rebuild a week without the workbook

If the Google OAuth token is expired or the sheet is otherwise unreachable,
`compose_sheet.py` writes the same `{"values": ...}` payload from the
players-league data files plus the week's content, held in that file:

```bash
python3 enrich.py \
    ~/repos/players-league/tools/data/2026-week-05-preview.json \
    ~/repos/players-league/tools/data/2026-power-week-04.json \
    2026 5 deep.json
python3 compose_sheet.py deep.json 5 wk5.json
python3 build.py wk5.json 5 2026 week-05.html deep.json
```

Week 5 was built this way. Anything the league data can't supply (guest,
recording date, intro song, Team of the Week pick, Peter's picks) is written
as a bracketed placeholder rather than guessed.

`PICKS` in `build.py` holds the weekly predictions, keyed by week number.
`OWNERS` maps team name -> owner, so team renames don't break picks.
`RENAMES` corrects team names the sheet still has under an old label.
`RECAP` holds last week's results table; the sheet has no cells for it.
