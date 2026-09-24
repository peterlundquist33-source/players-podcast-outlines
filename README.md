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

`PICKS` in `build.py` holds the weekly predictions, keyed by week number.
`OWNERS` maps team name -> owner, so team renames don't break picks.
`RENAMES` corrects team names the sheet still has under an old label.
