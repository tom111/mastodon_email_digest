# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Mastodon Email Digest fetches recent posts from your Mastodon home timeline, scores them by popularity, filters to the top percentile, renders them as HTML via Jinja2, and emails the result. It runs on a schedule via GitHub Actions.

## Running Locally

Copy `.env.example` to `.env` and fill in your Mastodon credentials.

**Direct Python:**
```bash
pip install -r requirements.txt
mkdir -p render
python run.py -n 24 -s SimpleWeighted -t lax
```

**Docker (via Makefile):**
```bash
make build
make run FLAGS="-n 24 -s SimpleWeighted -t lax"
```

**CLI options:**
- `-n` — Hours to look back (1–24, default 12)
- `-s` — Scorer: `Simple`, `SimpleWeighted`, `ExtendedSimple`, `ExtendedSimpleWeighted`
- `-t` — Threshold: `lax` (90th pct), `normal` (95th pct), `strict` (98th pct)
- `-o` — Output directory (default `./render/`)

Output is written to `render/index.html`.

## Architecture

The pipeline in `run.py` has three stages:

1. **Fetch** (`api.py`) — Paginates the Mastodon home timeline up to 1000 posts within the time window. Skips posts the user has already reblogged, favourited, bookmarked, or authored. Separates results into `posts` (original) and `boosts` lists.

2. **Score & filter** (`scorers.py`, `thresholds.py`) — Each `Scorer` subclass computes a numeric score per post using a geometric mean of engagement metrics. `Weighted` variants divide by sqrt(follower count) to de-emphasize large accounts. `Extended` variants add reply counts to the mean. `Threshold` (an Enum at 90/95/98th percentile) filters to only posts above the cutoff using `scipy.stats.percentileofscore`.

3. **Render** (`formatters.py`, `templates/`) — `format_posts` converts `ScoredPost` objects to plain dicts for the Jinja2 template. `digest.html.jinja` renders both streams (Posts + Boosts) using the shared `posts.html.jinja` partial.

**Key classes/modules:**
- `models.ScoredPost` — thin wrapper around the raw Mastodon API dict; provides `url`, `get_home_url()`, and `get_score(scorer)`
- `scorers.Scorer` / `Weight` — abstract base classes; concrete scorers use Python MRO to compose scoring + weighting; `get_scorers()` auto-discovers all `Scorer` subclasses via `inspect`
- `thresholds.Threshold` — Enum; `get_thresholds()` returns the name→value dict used for CLI choices

## Deployment

The workflow in `.github/workflows/update.yml` runs daily (configure cron there), installs dependencies, runs `python run.py`, then emails `render/index.html` using `dawidd6/action-send-mail`. Required GitHub secrets: `MASTODON_TOKEN`, `MASTODON_BASE_URL`, `MASTODON_USERNAME`, `MAIL_SERVER`, `MAIL_SERVER_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DESTINATION`.

## Adding a New Scorer

Subclass `Scorer` (and optionally a `Weight` class) in `scorers.py`. The `get_scorers()` function auto-discovers all `Scorer` subclasses, so no registration is needed. The class name minus `"Scorer"` becomes the CLI name.
