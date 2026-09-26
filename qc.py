"""Automated media QC for generated devotional videos."""
import json, os, subprocess, sys

def probe(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration:stream=codec_type,codec_name,width,height,sample_rate","-of","json",path],capture_output=True,text=True)
    if r.returncode: return {"ok":False,"error":r.stderr.strip()}
    try: return {"ok":True,**json.loads(r.stdout)}
    except Exception as e: return {"ok":False,"error":str(e)}

def check(path, kind):
    if not os.path.exists(path):
        return {"path": path, "ok": False, "error": "missing"}
    p = probe(path)
    p["path"] = path
    streams = p.get("streams", [])
    duration = float(p.get("format", {}).get("duration", 0) or 0)
    p["duration"] = duration

    # The current production target is a compact 3-minute long-form episode.
    # Keep a little tolerance around the 2:30–3:30 content target so a bad
    # timing/render regression cannot silently ship a padded 5–10 minute file.
    # Two levels:
    #   target  (LONG_VIDEO_MIN/MAX_SECONDS, default 120-240 s) -> warning only;
    #           a complete, tight story should never be blocked or padded.
    #   hard    (LONG_VIDEO_HARD_MIN/MAX_SECONDS, default 60-300 s) -> fail;
    #           catches real render/timing regressions (empty or runaway video).
    if kind == "video" and path.endswith("final_video.mp4"):
        t_min = float(os.getenv("LONG_VIDEO_MIN_SECONDS", "120"))
        t_max = float(os.getenv("LONG_VIDEO_MAX_SECONDS", "240"))
        h_min = float(os.getenv("LONG_VIDEO_HARD_MIN_SECONDS", "60"))
        h_max = float(os.getenv("LONG_VIDEO_HARD_MAX_SECONDS", "300"))
        p["durationTargetOk"] = h_min <= duration <= h_max
        if not p["durationTargetOk"]:
            p["durationTargetError"] = f"long video {duration:.0f}s outside hard limit {h_min:.0f}-{h_max:.0f}s"
        elif not (t_min <= duration <= t_max):
            p["durationWarning"] = f"long video {duration:.0f}s outside {t_min:.0f}-{t_max:.0f}s target (not blocking)"
            print(f"::warning::{p['durationWarning']}")

    has_kind = any(s.get("codec_type") == kind for s in streams)
    # Still images (thumbnails) legitimately have no media duration in
    # ffprobe. Validate that an image has dimensions instead of requiring
    # duration > 0; audio/video must have a positive duration.
    if kind == "image":
        has_dimensions = any(
            s.get("codec_type") == "video"
            and int(s.get("width", 0) or 0) > 0
            and int(s.get("height", 0) or 0) > 0
            for s in streams
        )
        p["ok"] = p["ok"] and has_dimensions
    else:
        p["ok"] = p["ok"] and duration > 0 and has_kind
        if kind == "video" and path.endswith("final_video.mp4"):
            p["ok"] = p["ok"] and p.get("durationTargetOk", True)

    return p

def main():
    targets=[("out/final_video.mp4","video"),("out/final_video_shorts.mp4","video"),("out/thumbnail.jpg","image"),("out/thumbnail_shorts_final.jpg","image")]
    # Always check every required output. The previous implementation passed
    # tuples to os.path.exists(), causing a TypeError before QC could run.
    # Keeping missing targets in the report also prevents a partial artifact
    # set from accidentally passing the publish gate.
    results=[check(path, kind) for path, kind in targets]
    audio_files=[]
    if os.path.isdir("public/audio"):
        for root, _, files in os.walk("public/audio"):
            audio_files.extend(
                os.path.join(root, name)
                for name in files
                if name.lower().endswith(".mp3")
            )
    results += [check(x, "audio") for x in audio_files[:500]]
    failed=[r for r in results if not r["ok"]]
    report={"ok":not failed,"checked":len(results),"failed":failed,"results":results}
    os.makedirs("out",exist_ok=True)
    with open("out/qc_report.json","w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if failed: sys.exit(1)
if __name__=="__main__": main()