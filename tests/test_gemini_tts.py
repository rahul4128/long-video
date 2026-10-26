"""Offline Gemini 3.8 TTS contract tests; never call Google's API or consume credits."""
import base64
import io
import os
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch

from scripts.gemini_tts import (
    GeminiTTSError, generate_gemini_audio, _audio_from_response
)
import scripts.gemini_tts as tts


def sample_wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\x00\x01" * 48000)
    return out.getvalue()


class FakeResponse:
    def __init__(self, payload=None, status=200, headers=None):
        self.status_code = status
        self.payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.responses = response if isinstance(response, list) else [response]
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses[min(len(self.requests)-1, len(self.responses)-1)]


class GeminiNarrationTests(unittest.TestCase):
    def setUp(self):
        # No cooldowns or external requests in unit tests.
        tts._LAST_ATTEMPT_AT = 0.0
        tts._API_ATTEMPTS = 0
        tts._DAILY_QUOTA_EXHAUSTED = False
        tts._MODEL_DAILY_QUOTA_EXHAUSTED.clear()
        self.env = patch.dict(os.environ, {
            "GEMINI_TTS_MIN_GAP_SECONDS": "0",
            "GEMINI_TTS_MAX_RETRIES": "2",
            "GEMINI_TTS_MAX_API_ATTEMPTS": "18",
        })
        self.sleep = patch("scripts.gemini_tts.time.sleep")
        self.env.start()
        self.sleep.start()

    def tearDown(self):
        self.sleep.stop()
        self.env.stop()

    def response(self, raw=None):
        return FakeResponse({"steps": [
            {"type": "model_output", "content": [
                {"type": "audio", "data": base64.b64encode(raw or sample_wav()).decode("ascii")}
            ]}
        ]})

    def test_hindi_transcript_is_verbatim_and_audio_converts_to_mp3(self):
        session = FakeSession(self.response())
        text = "माँ दुर्गा की आराधना हमें साहस देती है।"
        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp) / "scene.mp3")
            def fake_ffmpeg(command, **kwargs):
                Path(command[-1]).write_bytes(b"ID3" + b"audio" * 900)
                return type("Result", (), {"returncode": 0})()
            with patch("scripts.gemini_tts.subprocess.run", side_effect=fake_ffmpeg):
                self.assertTrue(generate_gemini_audio(text, dest, api_key="sample-key",
                                                      session=session, voice="Kore"))
            self.assertTrue(Path(dest).exists())
            url, sent = session.requests[0]
            self.assertTrue(url.endswith("/v1beta/interactions"))
            self.assertEqual(sent["headers"]["x-goog-api-key"], "sample-key")
            body = sent["json"]
            self.assertEqual(body["model"], "gemini-3.8-flash-tts")
            self.assertEqual(body["input"][0]["content"][0]["text"], text)
            self.assertEqual(body["input"][0]["content"][0]["annotations"][0]["type"], "speech_metadata")
            self.assertEqual(body["generation_config"]["speech_config"][0]["voice"], "Kore")
            self.assertEqual(body["response_format"]["type"], "audio")

    def test_flash_lite_model_is_supported(self):
        session = FakeSession(self.response())
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.gemini_tts.subprocess.run") as f:
                def make_mp3(cmd, **kw):
                    Path(cmd[-1]).write_bytes(b"ID3"+b"x"*2000)
                    return type("Result", (), {"returncode": 0})()
                f.side_effect = make_mp3
                generate_gemini_audio("नमस्ते", str(Path(tmp)/"t.mp3"),
                                      api_key="key", model="gemini-3.8-flash-lite-tts", session=session)
        self.assertEqual(session.requests[0][1]["json"]["model"], "gemini-3.8-flash-lite-tts")

    def test_missing_key_never_calls_api(self):
        session = FakeSession(self.response())
        with self.assertRaises(GeminiTTSError) as err:
            generate_gemini_audio("नमस्ते", "scene.mp3", api_key="", session=session)
        self.assertEqual(err.exception.code, "missing_key")
        self.assertEqual(session.requests, [])

    def test_quota_error_is_sanitized_and_not_written(self):
        session = FakeSession(FakeResponse({"error": {"message": "contains-sensitive-details"}}, 429))
        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp)/"scene.mp3")
            with self.assertRaises(GeminiTTSError) as err:
                generate_gemini_audio("नमस्ते", dest, api_key="private-key", session=session)
            self.assertEqual(err.exception.code, "quota_exceeded")
            self.assertNotIn("private-key", str(err.exception))
            self.assertNotIn("contains-sensitive-details", str(err.exception))
            self.assertFalse(Path(dest).exists())

    def test_missing_audio_causes_safe_fallback(self):
        session = FakeSession(FakeResponse({"steps": [{"type": "model_output", "content": []}]}))
        with self.assertRaises(GeminiTTSError) as err:
            generate_gemini_audio("नमस्ते", "scene.mp3", api_key="key", session=session)
        self.assertEqual(err.exception.code, "empty_audio")

    def test_corrupt_wav_is_rejected_before_ffmpeg(self):
        session = FakeSession(self.response(raw=b"not a wave file"))
        with patch("scripts.gemini_tts.subprocess.run") as ff:
            with self.assertRaises(GeminiTTSError) as err:
                generate_gemini_audio("नमस्ते", "scene.mp3", api_key="key", session=session)
            self.assertEqual(err.exception.code, "invalid_audio")
            ff.assert_not_called()

    def test_429_retries_after_cooling_down_and_succeeds(self):
        session = FakeSession([
            FakeResponse({"error": {"message": "Rate limited"}}, 429, {"Retry-After": "28"}),
            self.response(),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.gemini_tts.subprocess.run") as ff:
                def make_mp3(cmd, **kw):
                    Path(cmd[-1]).write_bytes(b"ID3"+b"x"*2200)
                    return type("Result", (), {"returncode": 0})()
                ff.side_effect = make_mp3
                self.assertTrue(generate_gemini_audio(
                    "भक्ति की शक्ति", str(Path(tmp)/"demo.mp3"),
                    api_key="test", session=session,
                ))
        self.assertEqual(len(session.requests), 2)
        # Retry-After is honoured rather than retrying immediately.
        self.assertIn(28.0, [arg.args[0] for arg in tts.time.sleep.call_args_list])

    def test_daily_quota_never_retries(self):
        session = FakeSession(FakeResponse({
            "error": {
                "message": "Quota exceeded",
                "details": [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]
            }
        }, 429))
        with self.assertRaises(GeminiTTSError) as e:
            generate_gemini_audio("नमस्ते", "unused.mp3", api_key="key", session=session)
        self.assertEqual(e.exception.code, "quota_daily_exhausted")
        self.assertEqual(len(session.requests), 2)  # primary + backup model
        self.assertEqual(
            [request["json"]["model"] for _, request in session.requests],
            ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"],
        )
        self.assertTrue(tts._DAILY_QUOTA_EXHAUSTED)
        tts.time.sleep.assert_not_called()  # no retries after daily exhaustion
        with self.assertRaises(GeminiTTSError):
            generate_gemini_audio("नमस्ते", "unused.mp3", api_key="key", session=session)
        self.assertEqual(len(session.requests), 2)

    def test_failed_quota_retries_are_bounded(self):
        session = FakeSession(FakeResponse({"error": {"message": "Rate limit"}}, 429))
        with self.assertRaises(GeminiTTSError) as e:
            generate_gemini_audio("नमस्ते", "unused.mp3", api_key="key", session=session)
        self.assertEqual(e.exception.code, "quota_exceeded")
        self.assertEqual(len(session.requests), 6)
        self.assertEqual(len(tts.time.sleep.call_args_list), 4)

    def test_api_attempt_budget_includes_retries(self):
        session = FakeSession(FakeResponse({"error": {"message": "Too many requests"}}, 429))
        with patch.dict(os.environ, {"GEMINI_TTS_MAX_API_ATTEMPTS": "2"}):
            with self.assertRaises(GeminiTTSError) as e:
                generate_gemini_audio("नमस्ते", "unused.mp3", api_key="key", session=session)
        self.assertEqual(e.exception.code, "request_budget_exhausted")
        self.assertEqual(len(session.requests), 2)

    def test_primary_daily_quota_falls_back_to_lite_and_keeps_success(self):
        quota = FakeResponse({"error": {
            "message": "Quota exceeded",
            "details": [{"violations": [
                {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}
            ]}],
        }}, 429)
        session = FakeSession([quota, self.response(), self.response()])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.gemini_tts.subprocess.run") as ff:
                def convert(command, **kw):
                    Path(command[-1]).write_bytes(b"ID3" + b"x" * 2500)
                    return type("Result", (), {"returncode": 0})()
                ff.side_effect = convert
                self.assertTrue(generate_gemini_audio(
                    "राजा की कहानी", str(Path(tmp) / "one.mp3"),
                    api_key="test", session=session,
                ))
                # The next chunk must avoid the exhausted primary model.
                self.assertTrue(generate_gemini_audio(
                    "दूसरी कहानी", str(Path(tmp) / "two.mp3"),
                    api_key="test", session=session,
                ))
        models = [request["json"]["model"] for _, request in session.requests]
        self.assertEqual(models, [
            "gemini-3.8-flash-tts",
            "gemini-3.8-flash-lite-tts",
            "gemini-3.8-flash-lite-tts",
        ])
        self.assertEqual(tts._MODEL_DAILY_QUOTA_EXHAUSTED, {"gemini-3.8-flash-tts"})
        self.assertFalse(tts._DAILY_QUOTA_EXHAUSTED)

    def test_secondary_model_is_attempted_if_primary_has_transient_429_after_retries(self):
        quota = FakeResponse({"error": {"message": "Rate limited"}}, 429)
        session = FakeSession([quota, quota, quota, self.response()])
        with tempfile.TemporaryDirectory() as tmp:
            with patch("scripts.gemini_tts.subprocess.run") as ff:
                def convert(command, **kw):
                    Path(command[-1]).write_bytes(b"ID3" + b"x" * 2000)
                    return type("Result", (), {"returncode": 0})()
                ff.side_effect = convert
                self.assertTrue(generate_gemini_audio(
                    "बात", str(Path(tmp) / "transient.mp3"),
                    api_key="test", session=session,
                ))
        self.assertEqual(
            [request["json"]["model"] for _, request in session.requests],
            ["gemini-3.8-flash-tts"] * 3 + ["gemini-3.8-flash-lite-tts"],
        )
        self.assertFalse(tts._MODEL_DAILY_QUOTA_EXHAUSTED)

    def test_bad_request_does_not_burn_secondary_model_quota(self):
        session = FakeSession(FakeResponse(
            {"error": {"message": "Invalid input"}}, 400
        ))
        with self.assertRaises(GeminiTTSError) as err:
            generate_gemini_audio("राम", "unused.mp3", api_key="test", session=session)
        self.assertEqual(err.exception.code, "http_400")
        self.assertEqual(len(session.requests), 1)

    def test_only_tts_models_are_allowed(self):
        session = FakeSession(self.response())
        with self.assertRaises(GeminiTTSError) as err:
            generate_gemini_audio("नमस्ते", "scene.mp3", api_key="key",
                                  model="gemini-3.8-flash", session=session)
        self.assertEqual(err.exception.code, "invalid_model")
        self.assertEqual(session.requests, [])


if __name__ == "__main__":
    unittest.main()
