# Local transcript research input

Place subtitle or transcript files here only when you have lawfully obtained them and are authorized to analyze them.

Supported formats: SRT, VTT, and TXT with standard subtitle timestamps such as 00:01:23.000 --> 00:01:25.000.

Name files with an episode identifier:
- S01E01.srt
- S02E06.en.vtt

From the repository root, run:

    python research.py

The script reads files recursively and writes data/episode_research.json. It records cue counts, duration, speaker labels when present, frequent terms, topic counts, and timestamps where topic terms occur. It does not copy dialogue into the output.

Keep original files local. The transcripts/inbox folder is excluded from Git so files are not accidentally committed to this public repository.
