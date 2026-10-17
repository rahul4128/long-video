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


def sample_wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"\x00\x01" * 48000)
    return out.getvalue()


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.status_code = status
        self.payload = payload if payload is not None else {}

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


class GeminiNarrationTests(unittest.TestCase):
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

    def test_only_tts_models_are_allowed(self):
        session = FakeSession(self.response())
        with self.assertRaises(GeminiTTSError) as err:
            generate_gemini_audio("नमस्ते", "scene.mp3", api_key="key",
                                  model="gemini-3.8-flash", session=session)
        self.assertEqual(err.exception.code, "invalid_model")
        self.assertEqual(session.requests, [])


if __name__ == "__main__":
    unittest.main()
