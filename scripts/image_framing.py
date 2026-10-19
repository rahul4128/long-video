"""Pre-render framing checks for AI stills (no paid services or Python imaging dependencies)."""
import json
import os
import subprocess
import tempfile

CANVAS = {"9:16": (720, 1280), "16:9": (1280, 720)}


def image_dimensions(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=12, check=True,
        )
        stream = (json.loads(result.stdout).get("streams") or [{}])[0]
        return int(stream.get("width") or 0), int(stream.get("height") or 0)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        return 0, 0


def framing_issue(path, aspect_ratio):
    """Return None for a correctly shaped image; otherwise the rejection reason.

    The texture check rejects obvious horizontal 'video inside image' strips.
    It deliberately requires BOTH margins to be nearly featureless so dark
    devotional artwork with a single dark edge is not incorrectly rejected.
    """
    if aspect_ratio not in CANVAS:
        raise ValueError("Unsupported aspect ratio: " + str(aspect_ratio))
    width, height = image_dimensions(path)
    if width < 256 or height < 256:
        return "image missing, unreadable, or too small"
    target_width, target_height = CANVAS[aspect_ratio]
    expected = target_width / target_height
    actual = width / height
    if abs(actual / expected - 1.0) > 0.09:
        return f"wrong aspect ratio ({width}x{height}; expected {aspect_ratio})"

    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
             "scale=64:128,format=gray", "-frames:v", "1",
             "-f", "rawvideo", "pipe:1"],
            capture_output=True, timeout=15, check=True,
        )
        pixels = result.stdout
        if len(pixels) != 64 * 128:
            return None  # shape already checked; do not block on optional probe
        def texture(a, b):
            total = 0
            for y in range(a, b):
                start = y * 64
                for x in range(63):
                    total += abs(pixels[start + x + 1] - pixels[start + x])
            return total / max(1, (b - a) * 63)
        top = texture(0, 27)
        middle = texture(43, 85)
        bottom = texture(101, 128)
        if middle > 7.5 and max(top, bottom) < 0.9 and middle > 10 * max(0.1, top, bottom):
            return "embedded horizontal letterbox / empty top and bottom bands"
    except (OSError, subprocess.SubprocessError):
        pass  # no false rejection on optional content analysis
    return None


def preserve_full_subject(path, aspect_ratio):
    """Last-resort aspect correction without cropping/stretching the foreground.

    If the preferred native-ratio providers are unavailable, an incompatible
    still is placed over its own softly extended backdrop. This is deliberately
    less ideal than native 9:16 art, but prevents severed crowns, hands and feet.
    """
    if aspect_ratio not in CANVAS or not os.path.exists(path):
        return False
    width, height = CANVAS[aspect_ratio]
    folder = os.path.dirname(os.path.abspath(path)) or "."
    fd, temp = tempfile.mkstemp(prefix="framed_", suffix=".jpg", dir=folder)
    os.close(fd)
    try:
        graph = (
            "[0:v]split=2[backsrc][frontsrc];"
            f"[backsrc]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},boxblur=24:2[back];"
            f"[frontsrc]scale={width}:{height}:force_original_aspect_ratio=decrease[front];"
            "[back][front]overlay=(W-w)/2:(H-h)/2:shortest=1,"
            "format=yuv420p[out]"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-filter_complex",
             graph, "-map", "[out]", "-frames:v", "1", "-q:v", "3", temp],
            capture_output=True, timeout=50, check=True,
        )
        if image_dimensions(temp) != (width, height):
            return False
        os.replace(temp, path)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        if os.path.exists(temp):
            os.remove(temp)



def video_framing_issue(path, aspect_ratio):
    """Reject incompatible or pre-letterboxed source video before Shorts render.

    A 9:16 MP4 can itself contain a 16:9 frame surrounded by black. ffprobe
    dimensions alone will miss this; inspect a sampled source frame as well.
    This is a technical framing check, not a semantic/anatomy quality check.
    """
    if aspect_ratio not in CANVAS:
        raise ValueError("Unsupported aspect ratio: " + str(aspect_ratio))
    if not os.path.isfile(path):
        return "video missing"
    try:
        metadata = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=15, check=True,
        )
        stream = (json.loads(metadata.stdout).get("streams") or [{}])[0]
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if width < 240 or height < 240:
            return "invalid or undersized video dimensions"
        target_w, target_h = CANVAS[aspect_ratio]
        if abs((width / height) / (target_w / target_h) - 1.0) > 0.15:
            return f"wrong video aspect ratio ({width}x{height}; expected {aspect_ratio})"
        fd, snapshot = tempfile.mkstemp(suffix=".jpg", prefix="video_frame_")
        os.close(fd)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", "0.4", "-i", str(path),
                 "-frames:v", "1", "-q:v", "3", snapshot],
                capture_output=True, timeout=20, check=True,
            )
            return framing_issue(snapshot, aspect_ratio)
        finally:
            if os.path.isfile(snapshot):
                os.remove(snapshot)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        return "unreadable video framing"
