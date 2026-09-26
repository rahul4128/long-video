"""Optional OpenCLIP re-ranking of stock-video candidates (free, open source).

Tag/slug keyword matching can't tell whether a clip actually *looks* like the
scene. When CLIP_RERANK_ENABLED=true, each candidate's preview image (Pexels
`image`, Pixabay `thumbnail`) is scored against the scene's English visual
prompt with OpenCLIP ViT-B-32, on CPU, before anything is downloaded.

Returns None whenever it is disabled or anything fails, so the caller simply
keeps the existing keyword ranking.
"""
import io
import os
import threading

import requests

_state = {"model": None, "preprocess": None, "tokenizer": None, "failed": False}
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("CLIP_RERANK_ENABLED", "false").strip().lower() == "true" and not _state["failed"]


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
        _state["tokenizer"] = open_clip.get_tokenizer(os.getenv("CLIP_MODEL", "ViT-B-32"))


def similarities(prompt: str, image_urls: list):
    """Cosine similarity (≈0.1-0.35) of each preview image to the prompt.

    Entries whose preview can't be fetched get None. Returns None overall if
    re-ranking is disabled/unavailable.
    """
    if not enabled() or not prompt or not image_urls:
        return None
    try:
        import torch
        from PIL import Image

        with _lock:
            _load()
            model, preprocess, tokenizer = _state["model"], _state["preprocess"], _state["tokenizer"]
            images, index = [], []
            for i, url in enumerate(image_urls):
                if not url:
                    continue
                try:
                    r = requests.get(url, timeout=10)
                    r.raise_for_status()
                    images.append(preprocess(Image.open(io.BytesIO(r.content)).convert("RGB")))
                    index.append(i)
                except Exception:
                    continue
            if not images:
                return None
            with torch.no_grad():
                img = model.encode_image(torch.stack(images))
                txt = model.encode_text(tokenizer([prompt[:300]]))
                img = img / img.norm(dim=-1, keepdim=True)
                txt = txt / txt.norm(dim=-1, keepdim=True)
                sims = (img @ txt.T).squeeze(-1).tolist()
        out = [None] * len(image_urls)
        for i, s in zip(index, sims):
            out[i] = float(s)
        return out
    except Exception as exc:
        print(f"CLIP rerank notice: disabled for this run ({exc})", flush=True)
        _state["failed"] = True
        return None
