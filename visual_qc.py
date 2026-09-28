"""Pre-render visual quality control for the visual-director pipeline.

This module is intentionally pure/cheap: it audits the already-selected
shot sequence after TTS timing is known and returns targeted repair requests.
The expensive repair actions remain in generate_assets.py, where stock/AI
providers are already available.

Phase 8 checks:
- beat/media coverage and missing files;
- weak stock-selection scores;
- hard/abrupt continuity flags;
- exact clip reuse inside one scene;
- excessive AI fallback usage;
- real narration-synchronised shot duration;
- timeline gaps/coverage.
"""
import os


_HARD_CONTINUITY_FLAGS = {
    "realism_conflict",
    "entity_conflict",
    "period_conflict",
    "near_duplicate",
    "near_duplicate_composition",
}
_SOFT_CONTINUITY_FLAGS = {
    "lighting_jump",
    "adjacent_realism_jump",
    "adjacent_period_jump",
    "large_visual_change",
    "very_similar_composition",
}


def _env_float(name, default, minimum, maximum):
    try:
        value = float(os.getenv(name, str(default)) or default)
    except ValueError:
        value = float(default)
    return max(minimum, min(maximum, value))


def thresholds(format_name="long"):
    is_shorts = format_name == "shorts"
    return {
        "minStockScore": _env_float(
            "VISUAL_QC_MIN_STOCK_SCORE",
            0.54 if not is_shorts else 0.50,
            0.30,
            0.85,
        ),
        "minShotSeconds": _env_float(
            "VISUAL_QC_MIN_SHOT_SECONDS",
            2.6 if not is_shorts else 1.8,
            0.8,
            5.0,
        ),
        "maxShotSeconds": _env_float(
            "VISUAL_QC_MAX_SHOT_SECONDS",
            8.5 if not is_shorts else 6.0,
            4.0,
            15.0,
        ),
        "maxAiRatio": _env_float(
            "VISUAL_QC_MAX_AI_RATIO",
            0.55 if not is_shorts else 0.70,
            0.20,
            1.0,
        ),
        "timelineTolerance": _env_float(
            "VISUAL_QC_TIMELINE_TOLERANCE",
            0.20,
            0.05,
            0.75,
        ),
    }


def _shot_duration(shot):
    try:
        duration = float(shot.get("syncedDurationSeconds"))
        if duration > 0:
            return duration
    except Exception:
        pass
    try:
        return max(
            0.0,
            float(shot.get("endSeconds") or 0.0)
            - float(shot.get("startSeconds") or 0.0),
        )
    except Exception:
        return 0.0


def _shot_key(shot):
    source = str(shot.get("source") or "")
    candidate = shot.get("candidateId")
    if not source or candidate in (None, "", "local_library"):
        return ""
    return f"{source}:{candidate}"


def assess_scene(scene, format_name="long", media_root="public/images"):
    limits = thresholds(format_name)
    shots = [dict(s or {}) for s in (scene.get("shots") or [])]
    beats = [dict(b or {}) for b in (scene.get("visualBeats") or [])]
    scene_number = scene.get("scene_number")
    strict_scene = bool(scene.get("visualStrict"))

    issues = []
    warnings = []
    repair_targets = []

    expected_beats = {
        int(b.get("beatIndex") or i + 1)
        for i, b in enumerate(beats)
    }
    covered_beats = {
        int(s.get("beatIndex") or i + 1)
        for i, s in enumerate(shots)
    }

    for beat_index in sorted(expected_beats - covered_beats):
        issue = {
            "code": "missing_beat_visual",
            "beatIndex": beat_index,
            "blocking": True,
        }
        issues.append(issue)
        repair_targets.append({
            "beatIndex": beat_index,
            "shotIndex": None,
            "reason": "missing_beat_visual",
            "action": "replace_or_generate",
            "priority": 100,
        })

    seen_keys = {}
    ai_indices = []

    for index, shot in enumerate(shots):
        beat_index = int(shot.get("beatIndex") or index + 1)
        source = str(shot.get("source") or "unknown")
        path = str(shot.get("file") or "").strip()
        duration = _shot_duration(shot)

        if not path or not os.path.exists(os.path.join(media_root, path)):
            issues.append({
                "code": "missing_media_file",
                "beatIndex": beat_index,
                "shotIndex": index,
                "file": path,
                "blocking": True,
            })
            repair_targets.append({
                "beatIndex": beat_index,
                "shotIndex": index,
                "reason": "missing_media_file",
                "action": "replace_or_generate",
                "priority": 100,
            })

        if source == "ai_image":
            ai_indices.append(index)
        elif source in {"local_continuity_fallback", "local_atmosphere_fallback"}:
            warnings.append({
                "code": "network_independent_visual_fallback",
                "beatIndex": beat_index,
                "shotIndex": index,
                "source": source,
            })

        selection_score = shot.get("selectionScore")
        if source not in {"ai_image", "local_library", "unknown"} and selection_score is not None:
            try:
                score = float(selection_score)
            except Exception:
                score = 1.0
            if score < limits["minStockScore"]:
                issues.append({
                    "code": "weak_stock_relevance",
                    "beatIndex": beat_index,
                    "shotIndex": index,
                    "score": round(score, 4),
                    "minimum": limits["minStockScore"],
                    "blocking": False,
                })
                repair_targets.append({
                    "beatIndex": beat_index,
                    "shotIndex": index,
                    "reason": "weak_stock_relevance",
                    "action": "replace_or_generate",
                    "priority": 85,
                })

        flags = set(shot.get("continuityFlags") or [])
        hard_flags = sorted(flags & _HARD_CONTINUITY_FLAGS)
        soft_flags = sorted(flags & _SOFT_CONTINUITY_FLAGS)
        if hard_flags:
            issues.append({
                "code": "hard_continuity_conflict",
                "beatIndex": beat_index,
                "shotIndex": index,
                "flags": hard_flags,
                "blocking": False,
            })
            repair_targets.append({
                "beatIndex": beat_index,
                "shotIndex": index,
                "reason": "hard_continuity_conflict",
                "action": "replace_or_generate",
                "priority": 95,
            })
        elif soft_flags:
            warnings.append({
                "code": "continuity_warning",
                "beatIndex": beat_index,
                "shotIndex": index,
                "flags": soft_flags,
            })

        key = _shot_key(shot)
        if key:
            if key in seen_keys:
                issues.append({
                    "code": "duplicate_clip_in_scene",
                    "beatIndex": beat_index,
                    "shotIndex": index,
                    "duplicateOfShotIndex": seen_keys[key],
                    "candidate": key,
                    "blocking": False,
                })
                repair_targets.append({
                    "beatIndex": beat_index,
                    "shotIndex": index,
                    "reason": "duplicate_clip_in_scene",
                    "action": "replace_or_generate",
                    "priority": 90,
                })
            else:
                seen_keys[key] = index

        if duration > limits["maxShotSeconds"]:
            issues.append({
                "code": "shot_too_long",
                "beatIndex": beat_index,
                "shotIndex": index,
                "duration": round(duration, 3),
                "maximum": limits["maxShotSeconds"],
                "blocking": False,
            })
            repair_targets.append({
                "beatIndex": beat_index,
                "shotIndex": index,
                "reason": "shot_too_long",
                "action": "split_visual",
                "priority": 60,
            })
        elif 0 < duration < limits["minShotSeconds"]:
            # Very short narration beats should remain narration-synchronised.
            # Repair uses a softer transition instead of moving the spoken cut.
            warnings.append({
                "code": "shot_too_short",
                "beatIndex": beat_index,
                "shotIndex": index,
                "duration": round(duration, 3),
                "minimum": limits["minShotSeconds"],
            })
            if shot.get("qcAction") != "soften_short_beat":
                repair_targets.append({
                    "beatIndex": beat_index,
                    "shotIndex": index,
                    "reason": "shot_too_short",
                    "action": "soften_short_beat",
                    "priority": 45,
                })

    if shots:
        ai_ratio = len(ai_indices) / len(shots)
    else:
        ai_ratio = 1.0

    if (
        shots
        and ai_ratio > limits["maxAiRatio"]
        and not strict_scene
    ):
        warnings.append({
            "code": "excessive_ai_fallback",
            "ratio": round(ai_ratio, 3),
            "maximum": limits["maxAiRatio"],
        })
        desired_ai_count = int(len(shots) * limits["maxAiRatio"])
        attempts_needed = max(1, len(ai_indices) - desired_ai_count)
        # Prefer replacing longer AI holds first; they have the largest
        # perceptual impact if we can find valid stock.
        candidates = sorted(
            ai_indices,
            key=lambda i: _shot_duration(shots[i]),
            reverse=True,
        )
        for index in candidates[:attempts_needed]:
            repair_targets.append({
                "beatIndex": int(shots[index].get("beatIndex") or index + 1),
                "shotIndex": index,
                "reason": "excessive_ai_fallback",
                "action": "try_stock_only",
                "priority": 35,
            })

    # Timeline coverage/gap checks operate on real TTS-synchronised windows.
    timed = [
        (i, s)
        for i, s in enumerate(shots)
        if isinstance(s.get("startSeconds"), (int, float))
        and isinstance(s.get("endSeconds"), (int, float))
    ]
    timed.sort(key=lambda item: float(item[1].get("startSeconds") or 0.0))
    tolerance = limits["timelineTolerance"]
    if timed:
        first_start = float(timed[0][1].get("startSeconds") or 0.0)
        if first_start > tolerance:
            issues.append({
                "code": "timeline_missing_start",
                "gapSeconds": round(first_start, 3),
                "blocking": True,
            })
        for (prev_index, prev), (curr_index, curr) in zip(timed, timed[1:]):
            gap = float(curr.get("startSeconds") or 0.0) - float(prev.get("endSeconds") or 0.0)
            if gap > tolerance:
                issues.append({
                    "code": "timeline_gap",
                    "shotIndex": curr_index,
                    "gapSeconds": round(gap, 3),
                    "blocking": True,
                })
        try:
            scene_duration = float(scene.get("durationInSeconds") or 0.0)
            final_end = float(timed[-1][1].get("endSeconds") or 0.0)
            if scene_duration > 0 and scene_duration - final_end > tolerance:
                issues.append({
                    "code": "timeline_missing_end",
                    "gapSeconds": round(scene_duration - final_end, 3),
                    "blocking": True,
                })
        except Exception:
            pass

    # Dedupe repair requests: a beat with a hard conflict does not also need
    # a second low-score retry.
    repair_targets.sort(key=lambda item: item["priority"], reverse=True)
    deduped = []
    seen_target = set()
    for target in repair_targets:
        key = (target.get("beatIndex"), target.get("action"))
        if target.get("action") in {"replace_or_generate", "try_stock_only"}:
            key = (target.get("beatIndex"), "replace")
        if key in seen_target:
            continue
        seen_target.add(key)
        deduped.append(target)

    return {
        "sceneNumber": scene_number,
        "format": format_name,
        "ok": not any(i.get("blocking") for i in issues),
        "issues": issues,
        "warnings": warnings,
        "repairTargets": deduped,
        "shotCount": len(shots),
        "beatCount": len(beats),
        "aiRatio": round(ai_ratio, 3),
        "thresholds": limits,
    }


def assess_sequence(scenes, format_name="long", media_root="public/images"):
    reports = [
        assess_scene(scene, format_name=format_name, media_root=media_root)
        for scene in (scenes or [])
    ]
    return {
        "format": format_name,
        "ok": all(report["ok"] for report in reports),
        "sceneCount": len(reports),
        "repairTargetCount": sum(len(r["repairTargets"]) for r in reports),
        "blockingIssueCount": sum(
            1
            for report in reports
            for issue in report["issues"]
            if issue.get("blocking")
        ),
        "warningCount": sum(len(r["warnings"]) for r in reports),
        "scenes": reports,
    }
