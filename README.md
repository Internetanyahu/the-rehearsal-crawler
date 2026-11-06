# The Rehearsal Research Crawler

A GitHub-hosted discovery index and local research toolkit for HBO's *The Rehearsal*. It covers both seasons (12 episodes) and helps organize transcript/subtitle sources, episode metadata, interviews, recaps, and timestamped research notes.

## What it does

- Searches the public web for transcript, subtitle, screenplay, interview, episode-guide, and scene-breakdown references.
- Checks each destination's robots.txt, uses request delays, and avoids login/paywall/CAPTCHA/access-control bypass.
- Maintains a source catalog in data/catalog.json and the episode registry in data/episodes.json.
- Provides a local subtitle research indexer (research.py) for SRT, VTT, and timestamped TXT files you are authorized to analyze.
- Produces episode-level cue counts, durations, speaker labels, frequent terms, topic counts, and timestamp pointers in data/episode_research.json.

## Transcript handling and copyright

This is not a public mirror of copyrighted episode transcripts or screenplay text. The crawler discovers and links to sources; it does not download or republish full scripts/subtitles. The local research tool reads files you lawfully obtained and are authorized to analyze, but deliberately does not copy dialogue into its output. Keep source files in transcripts/inbox/, which is excluded from Git by default. Public visibility does not automatically grant permission to reproduce a work.

## Repository layout

- crawler.py — web discovery, robots checks, page classification, and metadata catalog.
- research.py — local SRT/VTT/TXT parser and timestamp/topic indexer.
- config/sources.json — seed pages and search phrases.
- data/catalog.json — generated source metadata.
- data/episodes.json — episode registry for both seasons.
- data/episode_research.json — generated research index, without transcript dialogue.
- transcripts/inbox/ — local input folder; original files are ignored by Git.
- .github/workflows/crawl.yml — scheduled/manual source discovery workflow.

## Use it in GitHub Codespaces

1. Open the repository and select Code → Codespaces → Create codespace on main.
2. Create transcripts/inbox/ in the file explorer.
3. Upload authorized SRT, VTT, or timestamped TXT files. Use names such as S01E01.srt or S02E06.en.vtt.
4. Open the terminal and run: python research.py
5. Open data/episode_research.json to review episode-level research pointers. Original transcript files stay in the Codespace and are not included in Git commits.

This works in a browser and does not require Linux on your Chromebook.

## Run the source crawler

    python -m pip install -r requirements.txt
    python crawler.py

The GitHub Actions workflow runs weekly and can also be started manually from Actions → Crawl The Rehearsal Archive → Run workflow.

Optional variables: CRAWL_MAX_PAGES (default 40), CRAWL_DELAY_SECONDS (default 3), and CRAWL_USER_AGENT.

## Add sources

Edit config/sources.json. Add a relevant index page to seed_urls and search phrases to search_queries. The crawler still applies robots.txt and access restrictions to every destination.

All fetched pages and local input files are untrusted data. The scripts never execute content or follow instructions embedded in it.
