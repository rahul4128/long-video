"""Atomic episode-wide narrator selection with reusable content-addressed MP3 cache.

A single engine/voice is used for EVERY Long and Shorts chunk. On any failure,
discard staged chunks and retry the whole episode with the next engine.
This module contains no paid-service calls; the caller supplies a synthesizer.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def engine_candidates(requested):
    requested = (requested or "kokoro").strip().lower()
    chains = {
        "gemini": ("gemini", "kokoro", "edge"),
        "kokoro": ("kokoro", "edge"),
        "auto": ("kokoro", "edge"),
        "indicf5": ("indicf5", "edge"),
        "edge": ("edge",),
    }
    if requested not in chains:
        raise ValueError("Unsupported narration engine: " + requested)
    return chains[requested]


def _voice_identity(engine, env):
    settings = {
        "gemini": ("GEMINI_TTS_MODEL", "GEMINI_TTS_VOICE", "GEMINI_TTS_STYLE"),
        "kokoro": ("KOKORO_VOICE", "KOKORO_SPEED"),
        "edge": ("EDGE_TTS_VOICE", "EDGE_TTS_RATE", "EDGE_TTS_PITCH"),
        "indicf5": ("INDICF5_MODEL", "INDICF5_VOICE"),
    }
    identity = {key: env.get(key, "") for key in settings[engine]}
    if engine == "indicf5":
        # A changed voice reference must never reuse the previous clone's audio.
        for filename in ("voice/ref.wav", "voice/ref.txt"):
            path = Path(filename)
            if path.is_file():
                identity[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    return identity


def cache_key(text, beat, engine, env=None):
    env = env if env is not None else os.environ
    params = {
        "cache_version": "episode-narration-v1",
        "transcript": text,
        "beat": beat,
        "engine": engine,
        "voice": _voice_identity(engine, env),
    }
    raw = json.dumps(params, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_paths(cache_dir, engine, key):
    parent = Path(cache_dir) / engine
    return parent / (key + ".mp3"), parent / (key + ".json")


def _read_cache(audio_file, timings_file, duration):
    try:
        if not audio_file.is_file() or audio_file.stat().st_size < 1000:
            return None
        if duration(str(audio_file)) <= 0.8:
            return None
        metadata = json.loads(timings_file.read_text(encoding="utf-8"))
        if not isinstance(metadata, list):
            return None
        return metadata
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _save_cache(src, timings, audio_file, timings_file):
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    partial_audio = audio_file.with_suffix(".partial.mp3")
    partial_json = timings_file.with_suffix(".partial.json")
    try:
        shutil.copyfile(src, partial_audio)
        partial_json.write_text(json.dumps(timings, ensure_ascii=False), encoding="utf-8")
        os.replace(partial_audio, audio_file)
        os.replace(partial_json, timings_file)
    finally:
        partial_audio.unlink(missing_ok=True)
        partial_json.unlink(missing_ok=True)


def _gemini_budget(uncached, chars, env):
    if uncached == 0:
        return None
    if not env.get("GEMINI_API_KEY", "").strip():
        return "missing_key"
    try:
        max_calls = min(40, max(1, int(env.get("GEMINI_TTS_MAX_REQUESTS", "12"))))
        max_attempts = max(1, int(env.get("GEMINI_TTS_MAX_API_ATTEMPTS", "18")))
        available = env.get("GEMINI_TTS_DAILY_REMAINING", "").strip()
        daily = int(available) if available else None
    except (TypeError, ValueError):
        return "invalid_budget_configuration"
    if uncached > max_calls or uncached > max_attempts:
        return "episode_exceeds_configured_request_cap"
    if daily is not None and uncached > daily:
        return "episode_exceeds_known_daily_quota"
    if chars <= 0:
        return "empty_episode"
    # Google does not expose remaining free-tier quota reliably through this
    # interface. These are preflight *configured* budgets, not live promises.
    return None


async def synthesize_episode(tasks, synthesize, duration, normalize, *,
                             requested="gemini", cache_dir=".tts_cache",
                             report_path="out/voice_episode_report.json", env=None):
    """Render all chunks with one voice or fail closed.

    tasks: list of {text, beat, path}; synthesize(text, stage_path, beat,
    engine=<name>, strict_engine=True) is an async callable.
    """
    env = env if env is not None else os.environ
    if not tasks or any(not task.get("path") for task in tasks):
        raise ValueError("Expected nonempty narration tasks with output paths")
    transcripts = [normalize(task.get("text", "")) for task in tasks]
    if any(not text.strip() or len(text) > 12500 for text in transcripts):
        raise ValueError("Invalid/oversized narration chunk")
    if len({task["path"] for task in tasks}) != len(tasks):
        raise ValueError("Duplicate narration output path")

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    total_chars = sum(map(len, transcripts))
    failures = []
    for engine in engine_candidates(requested):
        entries = []
        misses = 0
        missing_chars = 0
        for task, transcript in zip(tasks, transcripts):
            key = cache_key(transcript, task.get("beat", ""), engine, env)
            audio_file, timings_file = _cache_paths(cache_dir, engine, key)
            cached = _read_cache(audio_file, timings_file, duration)
            entries.append((key, audio_file, timings_file, cached))
            if cached is None:
                misses += 1
                missing_chars += len(transcript)
        reason = _gemini_budget(misses, missing_chars, env) if engine == "gemini" else None
        if reason:
            failures.append({"engine": engine, "reason": reason})
            continue

        try:
            with tempfile.TemporaryDirectory(prefix="episode_voice_", dir=str(report_path.parent)) as tmp:
                timings = []
                staged = []
                hits = 0
                for i, (task, transcript, entry) in enumerate(zip(tasks, transcripts, entries)):
                    key, audio_file, timings_file, cached = entry
                    stage = Path(tmp) / f"voice_{i}.mp3"
                    if cached is not None:
                        shutil.copyfile(audio_file, stage)
                        word_timings = cached
                        hits += 1
                    else:
                        word_timings = await synthesize(
                            task["text"], str(stage), task.get("beat", ""),
                            engine=engine, strict_engine=True,
                        )
                        if not isinstance(word_timings, list) or not stage.is_file():
                            raise RuntimeError("narration synthesis produced no valid MP3")
                        if stage.stat().st_size < 1000 or duration(str(stage)) <= 0.8:
                            raise RuntimeError("narration MP3 failed quality checks")
                        _save_cache(stage, word_timings, audio_file, timings_file)
                    staged.append(stage)
                    timings.append(word_timings)
                # COMMIT only after every narration chunk passes, never mix engines.
                for task, stage in zip(tasks, staged):
                    dest = Path(task["path"])
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(stage, dest)
                report = {
                    "status": "passed", "requested_engine": requested,
                    "engine": engine, "voice": _voice_identity(engine, env),
                    "chunk_count": len(tasks), "characters": total_chars,
                    "cache_hits": hits, "new_chunks": len(tasks) - hits,
                    "fallback_events": failures,
                    "mixed_engines": False,
                }
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
                return timings, report
        except Exception as exc:
            # Never log API response bodies/transcripts or copy partial
            # audio into the final public/audio directory.
            failures.append({"engine": engine, "reason": type(exc).__name__})
    report_path.write_text(json.dumps({
        "status": "failed", "requested_engine": requested,
        "chunk_count": len(tasks), "characters": total_chars,
        "fallback_events": failures, "mixed_engines": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    raise RuntimeError("All episode-wide narration engines failed; refusing mixed voices")
