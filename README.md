# PIRO Production Tracker

A static dashboard that monitors job orders flowing through PIRO
(sashaprimak.pirofusion.com) and republishes itself every 10 minutes via
GitHub Actions. No server, no dependencies beyond the Python standard library.

## How it works

```
PIRO API ──> main.py ──> site/data.json ──> GitHub Pages (static site/)
                └──> history.json (stage-change journal, kept on the `data` branch)
```

- **[main.py](main.py)** logs into PIRO (env vars `PIRO_USER` / `PIRO_PW`),
  pulls all orders in *Processing*, *New*, and *On hold*, updates the
  stage-change journal, and writes `site/data.json`. Read-only against PIRO.
  It fails loudly (non-zero exit) if PIRO auth breaks or every status pull
  fails, so a broken pipeline fails the workflow instead of silently
  publishing a stale page.
- **[tracker/piro.py](tracker/piro.py)** — API client.
- **[tracker/history.py](tracker/history.py)** — the journal. Records a
  `{stage, since}` entry each time an order changes stage, tracks
  `last_seen`, and prunes orders not seen for 60 days into
  `history_archive.json` so the journal doesn't grow forever.
- **[tracker/payload.py](tracker/payload.py)** — assembles `site/data.json`
  (parents only; suborders dropped).
- **[site/](site)** — the entire front-end, served as-is by GitHub Pages.
  `index.html` + `styles.css` + `app.js` are static and hand-maintained;
  the page fetches `config.json` and `data.json` and renders client-side.
  Data soft-refreshes every 2 minutes without reloading or losing the
  user's place, and a banner appears if the data is more than 45 minutes old.

## Business rules live in config, not code

[site/config.json](site/config.json) defines:

- `departments` — display order, which stages belong to each department, and
  `"groupBy": "metal"` for departments whose stages group orders by metal.
- `personGroupedStages` — stages that render grouped by assigned worker with
  employee/due-date filters. (The employee-specific report button is *not*
  controlled by this list — it appears automatically on any stage where at
  least one order has an assigned worker.)
- `stuckDays`, `staleDays`, `refreshSeconds`, `staleDataMinutes` — thresholds.
- `metalColors`, `metalOrder`, `metalFallback` — metal pill colors and sort order.

Adding a new stage to a department or recoloring a metal is a one-line config
edit; no Python changes needed.

## CI ([.github/workflows/update.yml](.github/workflows/update.yml))

Every 10 minutes (and on every push to main):

1. Restore `history.json` / `history_archive.json` / `log.txt` from the
   orphan **`data`** branch (first run falls back to the seed files on main).
2. Run the test suite (`python -m unittest discover -s tests`).
3. `python main.py` — pull PIRO, update the journal, build `site/data.json`.
4. Commit the journal state back to the `data` branch. **main is never
   committed to by CI**, so its history stays human.
5. Deploy `site/` to GitHub Pages via `actions/deploy-pages`.

## One-time migration steps

- In the repo settings, set **Pages → Build and deployment → Source** to
  **GitHub Actions** (the site is now deployed as a workflow artifact, not
  served from the branch).
- After the first successful run creates the `data` branch, the seed copies
  of `history.json` and `log.txt` on main can be removed:
  `git rm history.json log.txt && git commit -m "Remove journal seed (now on data branch)"`.

## Local development

```bash
python -m unittest discover -s tests -v
```

To preview the site, put any `data.json` in `site/` (run `main.py` with real
credentials, or fabricate one) and serve the directory:

```bash
python -m http.server 8123 --directory site
```
