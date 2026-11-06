#!/usr/bin/env python3
"""Index authorized local subtitle/transcript files without copying dialogue."""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
INBOX=ROOT/"transcripts"/"inbox"
OUTPUT=ROOT/"data"/"episode_research.json"
SUPPORTED={".srt",".vtt",".txt"}
STAMP=re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(?:(\d{1,2}):)?(\d{2}):(\d{2})[,.](\d{3})")
TAG=re.compile(r"<[^>]+>")
SPEAKER=re.compile(r"^([A-Z][A-Z0-9 ._'’-]{1,35}):\s*(.*)$")
WORD=re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
STOP=set("""a an and are as at be been but by can did do does for from had has have he her here him his how i if in into is it its just me my of on or our she so that the their them then there these they this to was we were what when where which who will with you your yeah yes no not uh um okay ok well""".split())
TOPICS={
"rehearsal_and_simulation":["rehearse","rehearsal","simulation","simulate","actor","acting","replica","set"],
"truth_and_deception":["lie","lying","truth","honest","honesty","secret","confess","deception"],
"relationships_and_family":["wife","husband","girlfriend","boyfriend","mother","father","son","daughter","family","marriage"],
"identity_and_performance":["identity","pretend","character","role","perform","performance"],
"fear_and_uncertainty":["fear","afraid","nervous","anxiety","uncertain","risk","mistake"],
"aviation_and_safety":["pilot","plane","airplane","flight","captain","cockpit","aviation","safety"]}
def secs(h,m,s): return int(h or 0)*3600+int(m)*60+int(s)
def parse_file(path):
 raw=path.read_text(encoding="utf-8-sig",errors="replace")
 cues=[]
 for block in re.split(r"\r?\n\s*\r?\n",raw.strip()):
  lines=[x.strip() for x in block.splitlines() if x.strip()]
  ix=next((i for i,x in enumerate(lines) if "-->" in x),None)
  if ix is None: continue
  m=STAMP.search(lines[ix])
  if not m: continue
  sh,sm,ss,sms,eh,em,es,ems=m.groups()
  start=secs(sh,sm,ss)+int(sms)/1000
  end=secs(eh,em,es)+int(ems)/1000
  text=TAG.sub(""," ".join(lines[ix+1:]))
  text=re.sub(r"\{\\an\d+\}","",text)
  text=re.sub(r"\s+"," ",text).strip()
  if text: cues.append({"start":start,"end":end,"text":text})
 return cues
def get_episode_id(name):
 m=re.search(r"\bS(\d{1,2})[ ._-]*E(\d{1,2})\b",name,re.I) or re.search(r"\b(\d{1,2})x(\d{1,2})\b",name,re.I)
 return f"S{int(m.group(1)):02d}E{int(m.group(2)):02d}" if m else None
def analyze(path):
 cues=parse_file(path)
 if not cues: return None
 words,speakers,topics=Counter(),Counter(),Counter()
 moments=defaultdict(list)
 for cue in cues:
  txt=cue["text"]
  sm=SPEAKER.match(txt)
  if sm: speakers[sm.group(1).strip()]+=1
  tokens=[w.lower().strip("'") for w in WORD.findall(txt)]
  words.update(w for w in tokens if w not in STOP)
  for topic,terms in TOPICS.items():
   hits=[term for term in terms if term in tokens]
   if hits:
    topics[topic]+=len(hits)
    if len(moments[topic])<12:
     n=int(cue["start"])
     moments[topic].append({"timestamp_seconds":n,"timestamp":f"{n//3600:02d}:{(n%3600)//60:02d}:{n%60:02d}"})
 ends=[c["end"] for c in cues]
 gaps=[max(0, round(cues[i]["start"]-cues[i-1]["end"], 3)) for i in range(1,len(cues))]
 first=round(min(c["start"] for c in cues),3)
 last=round(max(ends),3)
 largest_gap=max(gaps,default=0)
 return {"episode_id":get_episode_id(path.name),"source_file":path.name,"source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"cue_count":len(cues),"first_timestamp_seconds":first,"last_timestamp_seconds":last,"duration_seconds":round(last),"largest_gap_seconds":largest_gap,"gaps_over_60_seconds":sum(g>60 for g in gaps),"speaker_labels":[{"label":k,"cue_count":v} for k,v in speakers.most_common(30)],"frequent_terms":[{"term":k,"count":v} for k,v in words.most_common(40)],"topic_counts":dict(topics.most_common()),"topic_timestamps":dict(moments),"raw_transcript_stored":False}
def main():
 p=argparse.ArgumentParser(description="Index SRT/VTT/timestamped TXT files you are authorized to analyze.")
 p.add_argument("--input",type=Path,default=INBOX)
 p.add_argument("--output",type=Path,default=OUTPUT)
 a=p.parse_args()
 if not a.input.exists(): raise SystemExit(f"Input folder does not exist: {a.input}")
 rows=[]
 for f in sorted(a.input.rglob("*")):
  if f.is_file() and f.suffix.lower() in SUPPORTED:
   result=analyze(f)
   if result: rows.append(result); print(f"Indexed {f.name}: {result['cue_count']} cues")
   else: print(f"Skipped {f.name}: no recognizable timestamped cues")
 payload={"schema_version":1,"generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"transcript_text_included":False,"episodes":rows,"note":"Aggregate analysis and timestamp pointers only; original files remain local."}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(f"Wrote {len(rows)} episode records to {a.output}")
if __name__=="__main__": main()
