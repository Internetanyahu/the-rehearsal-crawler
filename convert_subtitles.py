#!/usr/bin/env python3
"""Convert authorized local SRT/VTT subtitle files into readable TXT files.

Input:  transcripts/inbox/
Output: transcripts/plain_text/
The output folder is ignored by Git to prevent accidental redistribution.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "transcripts" / "inbox"
DEFAULT_OUTPUT = ROOT / "transcripts" / "plain_text"
TIMESTAMP = re.compile(
    r"(?:(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?:(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{3})"
)
TAG = re.compile(r"<[^>]+>")
ASS_TAG = re.compile(r"\{\\an\d+\}")
HTML_ENTITY = re.compile(r"&(?:amp|lt|gt|quot|apos|nbsp);")

def clean_caption(text: str) -> str:
    text = TAG.sub("", text)
    text = ASS_TAG.sub("", text)
    text = text.replace("\\N", " ").replace("\\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def convert(path: Path) -> tuple[str, dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output = []
    cue_count = 0
    for line in lines:
        line = line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        if line.upper().startswith(("WEBVTT", "NOTE ", "STYLE", "REGION")):
            continue
        if TIMESTAMP.search(line):
            continue
        caption = clean_caption(line)
        if caption and caption not in output[-1:]:
            output.append(caption)
            cue_count += 1
    text = "\n".join(output).strip() + ("\n" if output else "")
    return text, {"source": path.name, "text_lines": len(output), "nonempty": bool(output)}

def main() -> None:
    parser = argparse.ArgumentParser(description="Convert local SRT/VTT subtitles to plain TXT.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.input.exists():
        raise SystemExit(f"Input folder not found: {args.input}")
    files = sorted(p for p in args.input.rglob("*") if p.is_file() and p.suffix.lower() in {".srt", ".vtt"})
    if not files:
        raise SystemExit(f"No SRT/VTT files found in {args.input}. Add your files first.")
    args.output.mkdir(parents=True, exist_ok=True)
    converted = 0
    for source in files:
        text, info = convert(source)
        if not info["nonempty"]:
            print(f"SKIP {source.name}: no caption text recognized")
            continue
        target = args.output / f"{source.stem}.txt"
        target.write_text(text, encoding="utf-8")
        converted += 1
        print(f"Converted {source.name} -> {target.relative_to(ROOT)} ({info['text_lines']} text lines)")
    print(f"Finished: {converted}/{len(files)} files converted.")

if __name__ == "__main__":
    main()
