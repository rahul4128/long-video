"""Canva Connect API preview image-generation client.

Requires a user OAuth access token with asset:write. Use only as an opted-in
fallback; every POST can consume the user's Canva AI allowance.
See https://www.canva.dev/docs/apps/rest-apis/reference/generations/
"""
from io import BytesIO
import os
from pathlib import Path
import time
import threading
import uuid
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError

API_BASE = "https://api.canva.com/rest/v1/image-generations"
# Canva documents a 20-create-per-minute limit. One global lock avoids
# simultaneous scene workers overflowing the *same user's* request limit.
_CREATE_LOCK = threading.Lock()
_LAST_CREATE_AT = 0.0


def _env_int(name, default, low, high):
    try:
        return max(low, min(high, int(os.getenv(name, str(default)) or default)))
    except (TypeError, ValueError):
        return default


def _retry_after(response):
    try:
        return max(0.0, min(180.0, float((getattr(response, "headers", {}) or {}).get("Retry-After", ""))))
    except (TypeError, ValueError):
        return None


def _post_image_generation(client, headers, body):
    """Cooldown and retry Canva create, never duplicating a billed image job.

    Keep exactly the same idempotency key on every transient retry. A real
    exhausted monthly AI credit allowance returns immediately. A short Canva
    credit cooldown may be observed once when Canva supplies cooldown_ends_at.
    """
    global _LAST_CREATE_AT
    min_gap = _env_int("CANVA_IMAGE_MIN_GAP_SECONDS", 5, 3, 30)
    retries = _env_int("CANVA_IMAGE_MAX_RETRIES", 2, 0, 4)
    max_wait = _env_int("CANVA_IMAGE_MAX_COOLDOWN_SECONDS", 120, 10, 180)
    cooled_credit_once = False
    with _CREATE_LOCK:
        for attempt in range(retries + 2):
            remaining = min_gap - (time.monotonic() - _LAST_CREATE_AT) if _LAST_CREATE_AT else 0
            if remaining > 0:
                time.sleep(remaining)
            _LAST_CREATE_AT = time.monotonic()
            response = client.post(
                API_BASE, headers=headers, timeout=35, json=body,
            )
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            try:
                error = response.json()
                code = str(error.get("code") or "")
            except (ValueError, TypeError, AttributeError):
                error, code = {}, ""
            if code == "credit_quota_exceeded":
                return response  # Never retry genuine exhausted AI allowance.
            if code == "credit_quota_cooldown":
                try:
                    end_at = float((error.get("quota_usage") or {}).get("cooldown_ends_at") or 0)
                except (ValueError, TypeError):
                    end_at = 0
                wait = end_at - time.time() + 1 if end_at else max_wait + 1
                if (not cooled_credit_once and 0 < wait <= max_wait
                        and attempt <= retries):
                    cooled_credit_once = True
                    print(f"Canva AI credit cooldown: sleeping {wait:.0f}s before retry", flush=True)
                    time.sleep(wait)
                    continue
                return response  # Do not wait hours or retry indefinitely.
            if attempt >= retries:
                return response
            wait = min(max_wait, max(5 * (2 ** attempt), _retry_after(response) or 0))
            print(f"Canva image API HTTP {response.status_code}: cooling down {wait:.0f}s "
                  f"(retry {attempt + 1}/{retries})", flush=True)
            time.sleep(wait)
    return response



class CanvaImageError(RuntimeError):
    def __init__(self, message, code="unknown"):
        self.code = str(code or "unknown")
        super().__init__(str(message)[:380])


def _api_json(response):
    try:
        data = response.json()
    except (ValueError, AttributeError):
        raise CanvaImageError(f"Canva returned invalid JSON (HTTP {response.status_code})", "invalid_response")
    if response.status_code >= 400:
        code = str(data.get("code") or f"http_{response.status_code}")
        # No credentials or request headers in errors/logging.
        detail = str(data.get("message") or "Request rejected")[:170]
        raise CanvaImageError(f"HTTP {response.status_code} {code}: {detail}", code)
    return data


def generate_canva_image(prompt, destination, aspect_ratio="16:9", *, token=None,
                         timeout_seconds=150, session=None):
    """Generate one real 16:9/9:16 image, returning the image output path.

    Canva's job download URLs expire after 24h. Download immediately and
    convert the output to the requested destination format. The idempotency
    key is deterministic per GitHub run/shot, preventing duplicate charges
    for network retries inside one run.
    """
    token = (token if token is not None else os.environ.get("CANVA_ACCESS_TOKEN", "")).strip()
    if not token:
        raise CanvaImageError("CANVA_ACCESS_TOKEN is not available", "missing_token")
    if aspect_ratio not in ("16:9", "9:16"):
        raise CanvaImageError("Only 16:9 and 9:16 Canva images are supported", "invalid_aspect")
    clean_prompt = " ".join(str(prompt).split())[:1900]
    if not clean_prompt:
        raise CanvaImageError("Empty Canva image prompt", "invalid_prompt")
    api_ratio = "landscape" if aspect_ratio == "16:9" else "portrait"
    run = os.environ.get("GITHUB_RUN_ID", "local")
    key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"canva-scene-v1:{run}:{api_ratio}:{destination}:{clean_prompt}"))
    client = session if session is not None else requests
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        created = _post_image_generation(
            client, headers,
            {"prompt": clean_prompt, "idempotency_key": key,
             "aspect_ratio": api_ratio, "asset_upload": {"type": "none"}},
        )
        job = _api_json(created).get("job") or {}
        job_id = job.get("id")
        if not job_id:
            raise CanvaImageError("Canva did not return an image generation job ID", "invalid_response")
        deadline = time.monotonic() + max(10, timeout_seconds)
        while job.get("status") == "in_progress":
            if time.monotonic() >= deadline:
                raise CanvaImageError("Canva image generation timed out", "timeout")
            time.sleep(4)
            polled = client.get(f"{API_BASE}/{job_id}", headers=headers, timeout=35)
            job = _api_json(polled).get("job") or {}
        if job.get("status") != "success":
            failure = job.get("error") or {}
            raise CanvaImageError(
                f"Canva image job failed: {failure.get('message') or job.get('status')}",
                failure.get("code") or "generation_failed"
            )
        result = (job.get("result") or {}).get("image") or {}
        url = result.get("url", "")
        if urlparse(url).scheme != "https":
            raise CanvaImageError("Canva image download URL missing or insecure", "invalid_response")
        res = client.get(url, timeout=45)
        if res.status_code != 200:
            raise CanvaImageError(f"Canva image download failed (HTTP {res.status_code})", "download_failed")
        if len(res.content) > 18_000_000:
            raise CanvaImageError("Canva image exceeds safe download limit", "invalid_image")
        try:
            with Image.open(BytesIO(res.content)) as image:
                image.load()
                if image.width < 400 or image.height < 400:
                    raise CanvaImageError("Canva returned an undersized image", "invalid_image")
                path = Path(destination)
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".canva.tmp")
                if path.suffix.lower() in (".jpg", ".jpeg"):
                    image.convert("RGB").save(temporary, format="JPEG", quality=94)
                else:
                    image.convert("RGB").save(temporary, format="PNG")
                temporary.replace(path)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise CanvaImageError(f"Canva returned an invalid image: {type(exc).__name__}", "invalid_image") from exc
        return str(destination)
    except requests.RequestException as exc:
        raise CanvaImageError(f"Canva network issue: {type(exc).__name__}", "network_failure") from exc
