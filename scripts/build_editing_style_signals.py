#!/usr/bin/env python3
"""Aggregate *real, individually labeled* creator analytics for editing selection.

Input is a JSON array exported/matched by owner, not Gemini inference:
{video_id, platform, editing_style, published_on, views,
 average_view_duration_seconds, video_duration_seconds, shares, evidence_url}.
No real data => no signal. Unknown style/implausible data => skip.
Source-reported signals remain subject to owner verification.
"""
import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse

from editing_style_engine import STYLES


def summarize(rows, now=None):
    now=now or date.today()
    groups=defaultdict(list)
    unique=set()
    for record in rows if isinstance(rows,list) else []:
        if not isinstance(record,dict):continue
        style=record.get("editing_style")
        platform=record.get("platform")
        video_id=str(record.get("video_id") or "").strip()
        if style not in STYLES or platform not in ("youtube","instagram") or not video_id or len(video_id)>150:
            continue
        try:
            published=date.fromisoformat(str(record.get("published_on")))
            days=(now-published).days
            views=int(record["views"])
            duration=float(record["video_duration_seconds"])
            viewed=float(record["average_view_duration_seconds"])
            shares=int(record.get("shares",0))
        except (ValueError,KeyError,TypeError,OverflowError):continue
        evidence=str(record.get("evidence_url") or "")
        parsed=urlparse(evidence)
        if parsed.scheme!="https" or not parsed.hostname or len(evidence)>400:
            continue
        if not 0<=days<=45 or views<100 or views>1000000000 or duration<=0 or duration>36000:
            continue
        if not 0<viewed<=duration*3 or shares<0 or shares>views:
            continue
        key=(platform,video_id)
        if key in unique:continue
        unique.add(key)
        groups[(platform,style)].append({
            "published_on":published,"views":views,
            "watch":min(100,viewed/duration*100),
            "shares_per_1000":shares/max(1,views)*1000,
            "source":evidence,
        })
    output=[]
    for (platform,style),items in sorted(groups.items()):
        if len(items)<3:continue
        # Use per-video averages, not view-weighted dominance by one viral hit.
        watch=sum(it["watch"] for it in items)/len(items)
        shares=sum(it["shares_per_1000"] for it in items)/len(items)
        latest=max(it["published_on"] for it in items).isoformat()
        output.append({
            "platform":platform,"style":style,"published_on":latest,
            "videos":len(items),
            "average_view_percentage":round(watch,3),
            "shares_per_1000":round(shares,3),
            # A human-reviewable evidence link (not a claim that data is independently verified).
            "source":items[-1]["source"],
            "source_type":"owner_reported_analytics",
        })
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True)
    parser.add_argument("--output",default="data/editing_style_signals.json")
    args=parser.parse_args()
    path=Path(args.input)
    records=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records,list):raise SystemExit("Analytics file must be an array of video metrics")
    output=summarize(records)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"🎬 {len(output)} style-performance aggregates from {len(records)} input records")


if __name__=="__main__":
    main()
