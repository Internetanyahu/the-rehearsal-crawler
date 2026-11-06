#!/usr/bin/env python3
"""Check public subtitle-source listing metadata without downloading subtitle files.

The checker fetches HTML listing pages only. It never follows archive/download
links or retrieves SRT/VTT payloads.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
INDEX_PATH = ROOT / "data" / "season2_subtitles.json"
USER_AGENT = os.getenv(
    "CRAWL_USER_AGENT",
    "RehearsalArchiveBot/1.0 (+https://github.com/Internetanyahu/the-rehearsal-crawler; metadata checker)"
)
TIMEOUT = 20
MAX_HTML_BYTES = 2_000_000
DELAY_SECONDS = max(1.0, float(os.getenv("CRAWL_DELAY_SECONDS", "3")))
ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}
LAST_REQUEST: dict[str, float] = {}
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in ROBOTS_CACHE:
        parser = RobotFileParser()
        try:
            response = SESSION.get(f"{origin}/robots.txt", timeout=TIMEOUT)
            if response.status_code >= 400:
                parser.parse([])
            else:
                parser.parse(response.text.splitlines())
            ROBOTS_CACHE[origin] = parser
        except requests.RequestException:
            ROBOTS_CACHE[origin] = None
    parser = ROBOTS_CACHE[origin]
    return bool(parser and parser.can_fetch(USER_AGENT, url))


def fetch_listing(url: str) -> tuple[str, dict]:
    host = urlparse(url).netloc.lower()
    wait = DELAY_SECONDS - (time.time() - LAST_REQUEST.get(host, 0))
    if wait > 0:
        time.sleep(wait)

    if not robots_allows(url):
        return "", {
            "status": "robots_blocked",
            "http_status": None,
            "checked_at": now_iso(),
            "final_url": url,
            "detail": "robots.txt disallows access or could not be checked",
        }

    try:
        response = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        LAST_REQUEST[host] = time.time()
        status_code = response.status_code
        content_type = response.headers.get("Content-Type", "").lower()
        if status_code != 200:
            response.close()
            return "", {
                "status": "unavailable",
                "http_status": status_code,
                "checked_at": now_iso(),
                "final_url": response.url,
                "detail": "listing page did not return HTTP 200",
            }
        if "html" not in content_type and "xhtml" not in content_type:
            response.close()
            return "", {
                "status": "unexpected_content_type",
                "http_status": status_code,
                "checked_at": now_iso(),
                "final_url": response.url,
                "detail": "expected an HTML listing page",
            }

        chunks = []
        size = 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_HTML_BYTES:
                response.close()
                return "", {
                    "status": "response_too_large",
                    "http_status": status_code,
                    "checked_at": now_iso(),
                    "final_url": response.url,
                    "detail": "HTML listing exceeded the configured size limit",
                }
            chunks.append(chunk)
        final_url = response.url
        response.close()
        return b"".join(chunks).decode("utf-8", "replace"), {
            "status": "reachable",
            "http_status": status_code,
            "checked_at": now_iso(),
            "final_url": final_url,
            "content_type": content_type.split(";")[0],
        }
    except requests.RequestException as exc:
        return "", {
            "status": "request_error",
            "http_status": None,
            "checked_at": now_iso(),
            "final_url": url,
            "detail": str(exc)[:300],
        }


def normalized_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).casefold()


def main() -> int:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    expected_files = index.get("files", [])
    checked_sources = []

    for source in index.get("sources", [
        {
            "name": index.get("source_name", "Primary source"),
            "url": index.get("source_url"),
            "role": "primary",
        },
        {
            "name": "Alternate source",
            "url": index.get("alternate_source_url"),
            "role": "alternate",
        },
    ]):
        url = source.get("url")
        if not url:
            continue
        html, result = fetch_listing(url)
        text = normalized_text(html) if html else ""
        matched = []
        if source.get("role") == "primary" and text:
            for item in expected_files:
                filename = re.sub(r"\s+", " ", item.get("listed_filename", "")).strip().casefold()
                if filename and filename in text:
                    matched.append(item.get("episode_id"))

        result.update({
            "name": source.get("name"),
            "role": source.get("role", "reference"),
            "url": url,
        })
        if source.get("role") == "primary" and result["status"] == "reachable":
            result["listed_episode_ids_found"] = matched
            result["listed_episode_count_found"] = len(matched)
            result["expected_episode_count"] = len(expected_files)
            result["status"] = "listing_complete" if len(matched) == len(expected_files) else "listing_partial"
        checked_sources.append(result)
        print(f"{result['status']}: {source.get('name')} ({url})")

    primary = next((s for s in checked_sources if s.get("role") == "primary"), None)
    index["last_checked_at"] = now_iso()
    index["source_checks"] = checked_sources
    if primary and primary.get("status") == "listing_complete":
        index["status"] = "source_listing_reachable_all_episodes_listed_files_not_downloaded"
    elif primary and primary.get("status") == "listing_partial":
        index["status"] = "source_listing_reachable_partial_episode_listing_files_not_downloaded"
    elif primary:
        index["status"] = f"primary_source_{primary.get('status')}_files_not_downloaded"
    else:
        index["status"] = "no_primary_source_configured_files_not_downloaded"

    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {INDEX_PATH.relative_to(ROOT)}; subtitle payloads downloaded: 0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
