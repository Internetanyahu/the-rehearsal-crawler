#!/usr/bin/env python3
"""Discover and index publicly accessible The Rehearsal-related source pages.

This is a metadata indexer, not a full-text mirror. It honors robots.txt,
uses conservative request delays, and stores only a short identifying excerpt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "sources.json"
CATALOG_PATH = ROOT / "data" / "catalog.json"
USER_AGENT = os.getenv(
    "CRAWL_USER_AGENT",
    "RehearsalArchiveBot/1.0 (+https://github.com/Internetanyahu/the-rehearsal-crawler; research indexer)"
)
MAX_PAGES = max(1, min(int(os.getenv("CRAWL_MAX_PAGES", "40")), 150))
DELAY = max(1.0, float(os.getenv("CRAWL_DELAY_SECONDS", "3")))
TIMEOUT = 20
MAX_RESPONSE_BYTES = 2_000_000
EXCERPT_LIMIT = 500
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}
LAST_REQUEST: dict[str, float] = {}

KEYWORDS = {
    "transcript": ("transcript", "transcription", "full dialogue", "dialogue transcript"),
    "screenplay": ("screenplay", "shooting script", "teleplay", "script pdf", "production script"),
    "interview": ("interview", " Q&A", "questions and answers"),
    "episode_guide": ("episode guide", "episode recap", "episode summary", "recap"),
    "scene_breakdown": ("scene breakdown", "shot breakdown", "behind the scenes"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    # Remove fragments and common tracking parameters.
    query = [(k, v) for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    flat = "&".join(f"{quote_plus(k)}={quote_plus(vv)}" for k, values in query for vv in values)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", "", flat, ""))


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in ROBOTS_CACHE:
        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = SESSION.get(robots_url, timeout=TIMEOUT, allow_redirects=True)
            if response.status_code >= 400:
                # A missing robots.txt is treated as no published exclusion.
                parser.parse([])
            else:
                parser.parse(response.text.splitlines())
            ROBOTS_CACHE[origin] = parser
        except requests.RequestException:
            # Fail closed if the site's robots policy cannot be checked.
            ROBOTS_CACHE[origin] = None
    parser = ROBOTS_CACHE[origin]
    return bool(parser and parser.can_fetch(USER_AGENT, url))


def polite_get(url: str) -> requests.Response | None:
    host = urlparse(url).netloc.lower()
    wait = DELAY - (time.time() - LAST_REQUEST.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    if not allowed_by_robots(url):
        print(f"ROBOTS BLOCKED: {url}")
        return None
    try:
        response = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        LAST_REQUEST[host] = time.time()
        if response.status_code != 200:
            response.close()
            return None
        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            response.close()
            return None
        chunks, size = [], 0
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                response.close()
                return None
            chunks.append(chunk)
        response._content = b"".join(chunks)
        response.close()
        return response
    except requests.RequestException as exc:
        print(f"FETCH ERROR: {url}: {exc}")
        return None


def search_web(query: str, limit: int) -> list[str]:
    search_url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    response = polite_get(search_url)
    if not response:
        return []
    soup = BeautifulSoup(response.content, "html.parser")
    found = []
    for link in soup.select("a.result__a, a[data-testid='result-title-a']"):
        href = link.get("href", "")
        if "uddg=" in href:
            href = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        normalized = normalize_url(urljoin(search_url, href))
        host = urlparse(normalized).netloc.lower()
        if normalized and host and "duckduckgo.com" not in host:
            found.append(normalized)
        if len(found) >= limit:
            break
    return found


def clean_text(soup: BeautifulSoup) -> str:
    for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form"]):
        node.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()


def classify(title: str, text: str) -> tuple[str, float]:
    haystack = f"{title} {text[:12000]}".lower()
    scores = {kind: sum(1 for term in terms if term in haystack)
              for kind, terms in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    score = scores[best]
    if score == 0 or "the rehearsal" not in haystack and "nathan fielder" not in haystack:
        return "unclassified", 0.0
    confidence = min(0.98, 0.45 + score * 0.12)
    if best == "transcript" and ("transcript" in title.lower() or "transcript" in haystack[:1500]):
        confidence += 0.08
    return best, round(min(confidence, 0.99), 2)


def episode_hint(text: str) -> str | None:
    patterns = [
        r"\bseason\s*(\d+)\s*(?:episode|ep\.?|x)\s*(\d+)\b",
        r"\bS(\d{1,2})E(\d{1,2})\b",
        r"\bepisode\s*(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            if len(match.groups()) == 2:
                return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"
            return f"E{int(match.group(1)):02d}"
    return None


def extract_page(url: str) -> dict | None:
    response = polite_get(url)
    if not response:
        return None
    final_url = normalize_url(response.url)
    soup = BeautifulSoup(response.content, "html.parser")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()
    text = clean_text(soup)
    if not text:
        return None
    kind, confidence = classify(title, text)
    if kind == "unclassified":
        return None
    canonical = soup.find("link", rel="canonical")
    canonical_url = normalize_url(urljoin(final_url, canonical.get("href", ""))) if canonical else final_url
    excerpt = text[:EXCERPT_LIMIT].strip()
    digest = hashlib.sha256((title + "\n" + text[:20000]).encode("utf-8", "ignore")).hexdigest()
    return {
        "url": final_url,
        "canonical_url": canonical_url or final_url,
        "title": title[:300],
        "material_type": kind,
        "confidence": confidence,
        "episode_hint": episode_hint(title + " " + text[:12000]),
        "excerpt": excerpt,
        "content_sha256": digest,
        "first_seen": None,
        "last_seen": now_iso(),
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.exists() else {
        "schema_version": 1, "project": "The Rehearsal Archive", "updated_at": None, "items": []
    }
    existing = {item.get("canonical_url", item["url"]): item for item in catalog.get("items", [])}
    candidates: list[str] = []
    for seed in config.get("seed_urls", []):
        normalized = normalize_url(seed)
        if normalized:
            candidates.append(normalized)
    for query in config.get("search_queries", []):
        candidates.extend(search_web(query, int(config.get("max_search_results_per_query", 8))))
    # Stable de-duplication and bounded work per run.
    candidates = list(dict.fromkeys(candidates))[:MAX_PAGES]
    print(f"Reviewing {len(candidates)} candidate pages.")
    for url in candidates:
        item = extract_page(url)
        if not item:
            continue
        key = item["canonical_url"]
        old = existing.get(key)
        if old:
            item["first_seen"] = old.get("first_seen") or now_iso()
            if old.get("content_sha256") == item["content_sha256"]:
                item["first_seen"] = old.get("first_seen")
        else:
            item["first_seen"] = now_iso()
        existing[key] = item
        print(f"INDEXED [{item['material_type']}] {item['title']} — {item['url']}")
    catalog["items"] = sorted(existing.values(), key=lambda x: (x.get("material_type", ""), x.get("title", "").lower()))
    catalog["updated_at"] = now_iso()
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Catalog contains {len(catalog['items'])} indexed pages.")


if __name__ == "__main__":
    main()
