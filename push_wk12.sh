#!/usr/bin/env bash
# Push the composed Week 12 2026 outline into the podcast workbook.
#
# Blocked as of 2026-11-24: every gog call on peterlundquist33@gmail.com
# returns invalid_grant ("Token has been expired or revoked"), for Sheets and
# Drive alike, so the tab could not be created. Peter has to reauthorize that
# account himself — Nicole's kohrmanlundquist@gmail.com is not a substitute
# and must not be used here. Once `gog sheets metadata "$BOOK" -a "$ACCT"`
# succeeds, run this script; it creates the tab, copies Week 6's format onto
# it, writes the values, and reads three cells back to prove the write landed.
#
#   bash push_wk12.sh
set -euo pipefail

BOOK=1XcKHk9bZDvd_wVtsb0XMIL0EaIpBxSVXmP7jf2pBGlA
ACCT=peterlundquist33@gmail.com
TAB='Podcast Week 12 2026'
SRC='Podcast Week 6 2026'          # most complete finished tab in the workbook
PAYLOAD="$(dirname "$0")/wk12.json"

export GOG_KEYRING_PASSWORD="$(cat ~/.config/gog/keyring-password)"

echo "== checking access =="
gog sheets metadata "$BOOK" -a "$ACCT" --plain >/dev/null

echo "== creating '$TAB' (skipped if it already exists) =="
gog sheets add-tab "$BOOK" "$TAB" -a "$ACCT" || \
  echo "   tab already present, continuing"

# FORMAT, not NORMAL: the layout and cell styling come from Week 6, but none
# of its content does, so there is nothing to clear out afterwards.
echo "== copying Week 6 formatting onto the new tab =="
gog sheets copy-paste "$BOOK" "'$SRC'!A1:U48" "'$TAB'!A1:U48" \
  --type=FORMAT -a "$ACCT"

echo "== writing the Week 12 values =="
python3 - "$PAYLOAD" <<'PY' > /tmp/wk12-batch.json
import json, sys
p = json.load(open(sys.argv[1]))
json.dump([{"range": p["range"], "values": p["values"]}], sys.stdout)
PY
gog sheets batch-update "$BOOK" --data-json="$(cat /tmp/wk12-batch.json)" -a "$ACCT"

echo "== reading back =="
gog sheets get "$BOOK" "'$TAB'!C5" -a "$ACCT" --plain
gog sheets get "$BOOK" "'$TAB'!B15" -a "$ACCT" --plain
gog sheets get "$BOOK" "'$TAB'!I4:I5" -a "$ACCT" --plain
echo "done"
