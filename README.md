# Alliance Stats

Streamlit web app that presents alliance members across several views: by VS
score, by total power, by a configurable composite of the two, and by the
balance between their VS and power percentiles. Source data is a `.xlsx` with
two raw-dump sheets — one containing columns `player_name` + `VS`, the other
`player_name` + `Power`.

## Local

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app uses `data.xlsx` next to the script if it's present; otherwise upload
via the sidebar.

## Deploy anonymously to Streamlit Community Cloud

1. **Make a throwaway GitHub account.** Any email, any name; the alliance only
   ever sees the deployed URL.
2. **New repo on that account** (public is fine — Streamlit Community Cloud
   doesn't deploy from private repos on the free tier without extra setup).
3. **Push these three files** to it: `streamlit_app.py`, `requirements.txt`,
   `data.xlsx` (your snapshot — rename `Book1.xlsx` to `data.xlsx`).
4. Go to <https://share.streamlit.io>, sign in with that GitHub.
5. **New app** → pick the repo → branch `main` → main file
   `streamlit_app.py` → **Deploy**.
6. Share the resulting `https://<your-app>.streamlit.app` URL.

## Updating data

Two options:

- **Commit a new `data.xlsx`** to the repo. The app redeploys automatically on
  push and everyone sees the new numbers.
- **Use the sidebar upload** for a one-off view (other viewers won't see it —
  Streamlit Cloud's free tier doesn't persist uploads across sessions).

## Composite math

```
vs_pct    = percentile of VS score within the alliance
power_pct = percentile of total power within the alliance
composite = (power_pct ** wp) × (vs_pct ** wv) × 10000   where wp + wv = 1
```

The sidebar slider controls `wp` (power weight). Default 67% gives power 2×
the weight of VS. Composite is a single number that compresses both
dimensions; the other tabs (`By VS`, `By Power`, `Balance`) let viewers slice
the same data without that weighting.

## Caveats

- **Duplicate detection is exact-match only.** The capture tool's OCR sometimes
  reads the same player as e.g. `♡ Elena ♡` and `ℭ Elena ℭ`; those show up in
  the "Unmatched" expander so you can fix the source workbook before
  re-deploying.
- **Newer players will tend to be lower in the power tab** simply because they
  haven't grown yet; tenure isn't in the data.
