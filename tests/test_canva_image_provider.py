"""Offline Canva image provider tests: no credits or external HTTP calls."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.canva_image_provider import CanvaImageError, generate_canva_image


class Response:
    def __init__(self, status=200, payload=None, content=b""):
        self.status_code = status
        self.payload = payload or {}
        self.content = content

    def json(self):
        return self.payload


class Session:
    def __init__(self, create, poll=None, image=None):
        self.create = create
        self.poll = poll
        self.image = image
        self.sent = []
        self.gets = []

    def post(self, url, **kwargs):
        self.sent.append(kwargs)
        return self.create

    def get(self, url, **kwargs):
        self.gets.append(url)
        return self.poll if "/image-generations/" in url else self.image


def test_png():
    out = io.BytesIO()
    Image.new("RGB", (1600, 900), "purple").save(out, format="PNG")
    return out.getvalue()


class CanvaImageProviderTests(unittest.TestCase):
    def test_generated_png_converted_to_valid_jpeg(self):
        session = Session(
            Response(payload={"job": {"id": "j-1", "status": "in_progress"}}),
            Response(payload={"job": {"id": "j-1", "status": "success", "result": {"image": {"url": "https://canva.example/img"}}}}),
            Response(content=test_png()),
        )
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.canva_image_provider.time.sleep"):
            dest = str(Path(tmp) / "scene.jpg")
            self.assertEqual(generate_canva_image("accurate Hindu ritual", dest, token="test", session=session), dest)
            with Image.open(dest) as im:
                self.assertEqual(im.format, "JPEG")
                self.assertEqual(im.size, (1600, 900))
            body = session.sent[0]["json"]
            self.assertEqual(body["aspect_ratio"], "landscape")
            self.assertEqual(body["asset_upload"]["type"], "none")
            self.assertEqual(len(body["idempotency_key"]), 36)

    def test_portrait_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Session(
                Response(payload={"job": {"id": "j-2", "status": "success", "result": {"image": {"url": "https://canva.example/img"}}}}),
                image=Response(content=test_png())
            )
            generate_canva_image("portrait frame", str(Path(tmp) / "scene.jpg"), "9:16", token="test", session=session)
            self.assertEqual(session.sent[0]["json"]["aspect_ratio"], "portrait")

    def test_quota_failure_does_not_generate_image(self):
        session = Session(Response(429, {"code": "credit_quota_exceeded", "message": "Quota exhausted"}))
        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp) / "scene.jpg")
            with self.assertRaises(CanvaImageError) as err:
                generate_canva_image("temple", dest, token="test", session=session)
            self.assertEqual(err.exception.code, "credit_quota_exceeded")
            self.assertFalse(Path(dest).exists())

    def test_disabled_token_no_api_call(self):
        session = Session(Response())
        with self.assertRaises(CanvaImageError) as err:
            generate_canva_image("temple", "unused.jpg", token="", session=session)
        self.assertEqual(err.exception.code, "missing_token")
        self.assertEqual(session.sent, [])

    def test_failed_generation_reports_code(self):
        session = Session(Response(payload={
            "job": {"id": "j-3", "status": "failed", "error": {"code": "unsafe_input", "message": "Rejected"}}
        }))
        with self.assertRaises(CanvaImageError) as err:
            generate_canva_image("temple", "unused.jpg", token="test", session=session)
        self.assertEqual(err.exception.code, "unsafe_input")


if __name__ == "__main__":
    unittest.main()
