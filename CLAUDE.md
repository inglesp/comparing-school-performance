# CLAUDE.md

## Project overview

Dashboard for exploring primary school performance and demographic data in England (2024-25). Deployed at https://inglesp.github.io/comparing-school-performance/.

## Tech stack

- **Python + uv** for the build script
- **Vanilla JS** (no frameworks) for the frontend
- **Canvas API** for the scatterplot (~14,500 data points)
- **just** for task running (`just build`, `just serve`)
- Static site deployed via GitHub Pages (Actions workflow in `.github/workflows/deploy.yml`)

## Key files

- `scripts/build.py` — reads DfE CSVs from `data/2024-25/`, merges school info + census + KS2 data, generates `_site/` (HTML, JSON, JS, CSS)
- `static/dashboard.js` — all frontend logic: scatterplot rendering, filters, search, table, URL state sync
- `static/style.css` — all styling
- `justfile` — `just build` and `just serve`

## Build and deploy

- `just build` or `uv run python scripts/build.py` generates `_site/`
- `_site/` is gitignored; built in CI
- Pushing to `main` triggers GitHub Actions deploy to Pages

## Data

- Source CSVs from DfE's compare school performance service (must be downloaded manually — direct fetch returns 403)
- CSVs in `data/2024-25/`: `england_school_information.csv`, `england_ks2revised.csv`, `england_census.csv`
- Suppressed values in CSVs: `SUPP`, `NE`, `NA`, `NP`, `NEW`, `LOW`, `DNS` — treated as null
- Percentages stored as strings like `"39%"` — parsed by `parse_pct()`
- Progress scores are entirely empty for 2024-25
- "% expected" includes "% higher" (at or above expected standard)
- SEN support + SEN EHCP are non-overlapping; their sum = total SEN

## Architecture notes

- `build.py` embeds `FIELD_LABELS`, `DEMOGRAPHIC_FIELDS`, and `FILTER_OPTIONS` as JS variables in the generated HTML
- All dashboard state is stored in URL query params for shareability (`x`, `y`, `f`, `schools`, `cols`, `sort`)
- Filters are dynamic: users add/remove filter rows, each with a category dropdown + value control
- Percentile filters use rank-based calculation (same formula in `schoolPercentile()` and `formatRank()`) to ensure display matches filtering
- Table shows all filtered schools (capped at 500), sorted by configurable column, with highlighted schools always included
- Canvas click and table row click both toggle school selection via `toggleSchool()`

## Conventions

- Commit messages: short summary line, optional blank line + detail paragraph
- Always rebuild with `uv run python scripts/build.py` after changing `build.py`, `dashboard.js`, or `style.css`
- Don't use `python3 -c` with multiline strings containing `#` (triggers permission warnings)
