# The Rehearsal Archive Crawler

A GitHub Actions-powered discovery and cataloging crawler for publicly accessible material about HBO's *The Rehearsal*: episode transcripts, screenplay/script references, production documents, interviews, and scene breakdowns.

## What it does

- Searches the public web for relevant pages using DuckDuckGo HTML search.
- Visits only HTTP(S) pages and checks each site's `robots.txt` before fetching.
- Identifies likely transcripts, scripts, screenplay references, interviews, and episode guides.
- Extracts title, source URL, page type, episode hints, a short identifying excerpt, and a content fingerprint.
- Deduplicates results and updates `data/catalog.json`.
- Runs on a schedule or manually through GitHub Actions.

## Copyright and access boundaries

This project is a **discovery index**, not a mirror of copyrighted television scripts or transcripts. It stores source metadata and a short excerpt (maximum 500 characters) for identification; it does not save full page text, full transcripts, or screenplay files. It does not bypass paywalls, logins, CAPTCHAs, access controls, or robots exclusions. It uses conservative request delays and a descriptive user agent.

The crawler may store full text only in a future workflow for material that is demonstrably public-domain, openly licensed, or explicitly authorized. A page being publicly viewable does not by itself grant permission to republish its contents.

## Repository layout

- `crawler.py` — discovery, robots checks, extraction, classification, and catalog updates.
- `config/sources.json` — seed sources and search phrases.
- `data/catalog.json` — generated metadata index.
- `.github/workflows/crawl.yml` — scheduled/manual GitHub Actions workflow.

## Run locally

```bash
python -m pip install -r requirements.txt
python crawler.py
```

Optional environment variables:
- `CRAWL_MAX_PAGES` (default: 40)
- `CRAWL_DELAY_SECONDS` (default: 3)
- `CRAWL_USER_AGENT` (override the default descriptive user agent)

## GitHub Actions

The workflow runs weekly and can also be started from the Actions tab using **Run workflow**. It commits catalog changes automatically. No API token or secret is required for the default search provider.

## Adding sources

Edit `config/sources.json`. Add a site's homepage or relevant index page to `seed_urls`, and add search phrases to `search_queries`. The crawler still applies robots.txt and access restrictions to every destination.

## Data format

Each catalog entry contains:
- `url`, `canonical_url`, `title`
- `material_type` and `confidence`
- `episode_hint` when identifiable
- `excerpt` (up to 500 characters)
- `content_sha256`, `first_seen`, and `last_seen`

Treat source pages as untrusted data. The crawler never executes scripts or follows instructions found in scraped pages.
