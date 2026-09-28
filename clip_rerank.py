"""Optional OpenCLIP re-ranking and visual-continuity scoring.

When CLIP_RERANK_ENABLED=true, stock preview images are encoded once with
OpenCLIP ViT-B-32 and reused for both:
- narration/prompt semantic scoring;
- adjacent-shot visual continuity / near-duplicate detection.

Everything remains optional: failures return None and the asset pipeline falls
back to metadata-based scoring.
"""
import io
import os
import threading

import requests

_state = {
    "model": None,
    "preprocess": None,
    "tokenizer": None,
    "failed": False,
    "image_features": {},
}
_lock = threading.Lock()


def enabled() -> bool:
    return (
        os.getenv("CLIP_RERANK_ENABLED", "false").strip().lower() == "true"
        and not _state["failed"]
    )


def min_similarity() -> float:
    try:
        return float(os.getenv("CLIP_MIN_SIMILARITY", "0.20"))
    except ValueError:
        return 0.20


def _load():
    if _state["model"] is None:
        import open_clip

        model, _, preprocess = open_clip.create_model_and_transforms(
            os.getenv("CLIP_MODEL", "ViT-B-32"),
            pretrained=os.getenv("CLIP_PRETRAINED", "laion2b_s34b_b79k"),
        )
        model.eval()
        _state["model"] = model
        _state["preprocess"] = preprocess
        _state["tokenizer"] = open_clip.get_tokenizer(
            os.getenv("CLIP_MODEL", "ViT-B-32")
        )


def _image_feature(url: str):
    """Return one cached normalized CLIP image feature tensor."""
    if not url:
        return None

    cache = _state["image_features"]
    if url in cache:
        return cache[url]

    import torch
    from PIL import Image

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        tensor = _state["preprocess"](
            Image.open(io.BytesIO(response.content)).convert("RGB")
        )
        with torch.no_grad():
            feature = _state["model"].encode_image(tensor.unsqueeze(0))
            feature = feature / feature.norm(dim=-1, keepdim=True)
        # Keep the cache bounded. One run only needs the recent candidate
        # previews; this prevents a pathological payload from growing it forever.
        if len(cache) >= 180:
            first_key = next(iter(cache))
            cache.pop(first_key, None)
        cache[url] = feature
        return feature
    except Exception:
        cache[url] = None
        return None


def similarities(prompt: str, image_urls: list):
    """Cosine similarity of each preview image to a text prompt."""
    if not enabled() or not prompt or not image_urls:
        return None
    try:
        import torch

        with _lock:
            _load()
            model, tokenizer = _state["model"], _state["tokenizer"]

            with torch.no_grad():
                text_feature = model.encode_text(tokenizer([prompt[:300]]))
                text_feature = text_feature / text_feature.norm(
                    dim=-1, keepdim=True
                )

            out = []
            any_feature = False
            for url in image_urls:
                feature = _image_feature(url)
                if feature is None:
                    out.append(None)
                    continue
                any_feature = True
                with torch.no_grad():
                    score = (feature @ text_feature.T).squeeze().item()
                out.append(float(score))

        return out if any_feature else None
    except Exception as exc:
        print(
            f"CLIP rerank notice: disabled for this run ({exc})",
            flush=True,
        )
        _state["failed"] = True
        return None


def image_similarities(reference_url: str, image_urls: list):
    """Cosine similarity of candidate previews to one reference preview."""
    if not enabled() or not reference_url or not image_urls:
        return None
    try:
        import torch

        with _lock:
            _load()
            reference = _image_feature(reference_url)
            if reference is None:
                return None

            out = []
            any_feature = False
            for url in image_urls:
                feature = _image_feature(url)
                if feature is None:
                    out.append(None)
                    continue
                any_feature = True
                with torch.no_grad():
                    score = (feature @ reference.T).squeeze().item()
                out.append(float(score))

        return out if any_feature else None
    except Exception as exc:
        print(
            f"CLIP continuity notice: image similarity unavailable ({exc})",
            flush=True,
        )
        return None
