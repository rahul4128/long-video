"""Offline Canva image provider tests: no credits or external HTTP calls."""
import io
import ast
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.canva_image_provider import CanvaImageError, generate_canva_image
import scripts.canva_image_provider as provider


class Response:
    def __init__(self, status=200, payload=None, content=b""):
        self.status_code = status
        self.payload = payload or {}
        self.content = content
        self.headers = {}

    def json(self):
        return self.payload


class Session:
    def __init__(self, create, poll=None, image=None):
        self.create = create if isinstance(create, list) else [create]
        self.poll = poll if isinstance(poll, list) else [poll]
        self.image = image
        self.sent = []
        self.gets = []

    def post(self, url, **kwargs):
        self.sent.append(kwargs)
        return self.create[min(len(self.sent)-1, len(self.create)-1)]

    def get(self, url, **kwargs):
        self.gets.append(url)
        return self.poll[min(len(self.gets)-1, len(self.poll)-1)] if "/image-generations/" in url else self.image


def test_png():
    out = io.BytesIO()
    Image.new("RGB", (1600, 900), "purple").save(out, format="PNG")
    return out.getvalue()


class CanvaImageProviderTests(unittest.TestCase):
    def setUp(self):
        provider._LAST_CREATE_AT = 0.0

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

    def test_api_rate_limit_cools_down_then_reuses_idempotency_key(self):
        transient = Response(429, {"code": "too_many_requests", "message": "Throttled"})
        session = Session([
            transient,
            Response(payload={"job": {"id": "job-4", "status": "success",
                                      "result": {"image": {"url": "https://canva.example/scene"}}}}),
        ], image=Response(content=test_png()))
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.canva_image_provider.time.sleep") as sleep:
                generated = generate_canva_image(
                    "accurate Indian devotional scene", str(Path(tmp) / "scene.jpg"),
                    token="fake", session=session,
                )
        self.assertTrue(generated.endswith("scene.jpg"))
        self.assertEqual(len(session.sent), 2)
        self.assertEqual(
            session.sent[0]["json"]["idempotency_key"],
            session.sent[1]["json"]["idempotency_key"],
        )
        self.assertTrue(any(call.args[0] >= 5 for call in sleep.call_args_list))

    def test_poll_rate_limit_cools_down_and_keeps_the_existing_job(self):
        session = Session(
            Response(payload={"job": {"id": "j-poll", "status": "in_progress"}}),
            poll=[
                Response(429, {"code": "too_many_requests", "message": "Slow polling"}),
                Response(payload={"job": {"id": "j-poll", "status": "success",
                                          "result": {"image": {"url": "https://canva.example/img"}}}}),
            ],
            image=Response(content=test_png()),
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.canva_image_provider.time.sleep") as sleep:
                path = str(Path(tmp) / "poll.jpg")
                generate_canva_image("Indian temple", path, token="fake", session=session)
                self.assertTrue(Path(path).exists())
        self.assertEqual(len(session.sent), 1, "Polling must not create another paid job")
        self.assertEqual(len(session.gets), 3)
        self.assertTrue(any(call.args[0] >= 4 for call in sleep.call_args_list))

    def test_credit_quota_cooldown_waits_only_for_short_provider_reset(self):
        now = 1900000000
        quota = Response(429, {"code": "credit_quota_cooldown", "message": "Cool down",
                               "quota_usage": {"cooldown_ends_at": now+21}})
        done = Response(payload={"job": {"id": "j-5", "status": "success",
                                         "result": {"image": {"url": "https://canva.example/scene"}}}})
        session = Session([quota, done], image=Response(content=test_png()))
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.canva_image_provider.time.time", return_value=now), patch(
                "scripts.canva_image_provider.time.sleep"
            ) as sleep:
                generate_canva_image("puja diya", str(Path(tmp) / "scene.jpg"),
                                     token="fake", session=session)
        self.assertEqual(len(session.sent), 2)
        self.assertTrue(any(call.args[0] >= 21 for call in sleep.call_args_list))

    def test_far_away_credit_cooldown_does_not_block_render_for_hours(self):
        now = 1900000000
        quota = Response(429, {"code": "credit_quota_cooldown", "message": "Cool down",
                               "quota_usage": {"cooldown_ends_at": now+7200}})
        session = Session(quota)
        with patch("scripts.canva_image_provider.time.time", return_value=now), patch(
            "scripts.canva_image_provider.time.sleep"
        ) as sleep, self.assertRaises(CanvaImageError) as raised:
            generate_canva_image("puja diya", "unused.jpg", token="fake", session=session)
        self.assertEqual(raised.exception.code, "credit_quota_cooldown")
        self.assertEqual(len(session.sent), 1)
        sleep.assert_not_called()

    def test_multiple_credit_jobs_are_possible_with_larger_configured_ceiling(self):
        code = (Path(__file__).resolve().parents[1] / "generate_assets.py").read_text()
        tree = ast.parse(code)
        fn = next(n for n in tree.body
                  if isinstance(n, ast.FunctionDef) and n.name == "_canva_image_budget")
        budget_namespace = {"os": os}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), "generate_assets.py", "exec"),
             budget_namespace)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(budget_namespace["_canva_image_budget"](), 80)
        with patch.dict(os.environ, {"CANVA_IMAGE_MAX_PER_RUN": "100"}):
            self.assertEqual(budget_namespace["_canva_image_budget"](), 100)
        with patch.dict(os.environ, {"CANVA_IMAGE_MAX_PER_RUN": "900"}):
            self.assertEqual(budget_namespace["_canva_image_budget"](), 200)
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/render.yml").read_text()
        self.assertIn("CANVA_IMAGE_MIN_GAP_SECONDS:", workflow)
        self.assertIn("default: '80'", workflow)
        self.assertIn("github.event_name == 'repository_dispatch'", workflow)

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
