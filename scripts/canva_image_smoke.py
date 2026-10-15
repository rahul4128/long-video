#!/usr/bin/env python3
"""One-image Canva API smoke test for GitHub Actions.

Explicit manual workflow only. Uses precisely one Canva image POST and never
publishes to YouTube or dispatches Make. This may consume one Canva AI credit.
"""
from pathlib import Path

from scripts.canva_image_provider import generate_canva_image
from scripts.image_framing import framing_issue

PROMPT = (
    "Cinematic photorealistic Indian Navratri puja scene, close-up of a "
    "traditional brass thali with a small bowl of honey offered beside "
    "a lit diya and marigold flowers, morning sunlight, respectful accurate "
    "ritual objects, no unrelated characters or visible deity faces, "
    "natural textures, single coherent moment, no lettering, no watermark, "
    "no border, 16:9 composition, all objects safely framed"
)


def main():
    dest = Path("out/canva_smoke_scene.jpg")
    result = generate_canva_image(PROMPT, str(dest), aspect_ratio="16:9")
    issue = framing_issue(result, "16:9")
    if issue:
        raise RuntimeError(f"Canva smoke image framing failed: {issue}")
    print(f"Canva image smoke SUCCESS: {dest}, bytes={dest.stat().st_size}")


if __name__ == "__main__":
    main()
