# Spencer Goidel Website

Static academic website with an interactive front page for 2026 swing Senate races.

## Included

- Professional academic profile pages (`about`, `publications`, `book`)
- Interactive US map of Cook Political Report swing Senate states
- Hover tooltips with state primary dates
- Click-through state pages with betting-market, polling, and storyline sections
- Data updater script and scheduled GitHub Action refresh

## Local preview

From the project directory:

```bash
python3 -m http.server 8080
```

Then open [http://localhost:8080](http://localhost:8080).

## Data refresh

Manual run:

```bash
python3 scripts/update_race_data.py
```

Scheduled refresh:

- `.github/workflows/update-race-data.yml` runs every 24 hours.
- This keeps the site within the requested 24-48 hour refresh window.

## Data sources

- Cook Political Report (Senate race ratings)
- NCSL (state primary election dates)
- Polymarket and Kalshi (market odds)
- RealClearPolitics + election-page poll aggregators
- Google News RSS (recent storylines)
