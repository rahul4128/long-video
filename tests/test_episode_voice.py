"""Offline tests for restored segment-wise Gemini/Kokoro behavior.

Compile only relevant generator functions from AST, so importing
generate_assets.py cannot call third-party APIs or read a Make payload.
"""
import ast
import asyncio
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class FakeGeminiError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class SegmentNarratorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.calls = []
        text = (ROOT / "generate_assets.py").read_text(encoding="utf-8")
        program = ast.parse(text)
        expected = {
            "_record_narrator", "_gemini_tts_claim_request",
            "_gemini_tts_block_on_error", "generate_clean_audio"
        }
        funcs = [node for node in program.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name in expected]
        self.assertEqual({node.name for node in funcs}, expected)
        ctx = {
            "asyncio": asyncio,
            "threading": threading,
            "os": os,
            "shutil": shutil,
            "GeminiTTSError": FakeGeminiError,
            "tts_semaphore": asyncio.Semaphore(2),
            "_GEMINI_TTS_STATE_LOCK": threading.Lock(),
            "_GEMINI_TTS_REQUESTS": 0,
            "_GEMINI_TTS_BLOCKED": False,
            "_TTS_NARRATOR_LOCK": threading.Lock(),
            "_TTS_NARRATOR_BY_PATH": {},
            "has_latin": lambda text: False,
            "_naturalize_text": lambda text: text,
            "to_spoken_hindi": lambda text: text,
            "build_prosody_map": lambda text, beat: {},
            "prepare_storyteller_text": lambda text: text,
            "_fallback_word_timings": lambda text, path: [{"word": text, "start": 0, "end": 1}],
            "get_audio_duration": lambda path: 3.0 if Path(path).exists() else 0,
            "KOKORO_AVAILABLE": True,
        }
        def gemini(text, dest):
            self.calls.append((text, "gemini"))
            if text == "bad-audio":
                raise FakeGeminiError("invalid_audio")
            if text == "daily-quota":
                raise FakeGeminiError("quota_daily_exhausted")
            Path(dest).write_bytes(b"gemini:" + text.encode() * 500)
        def kokoro(text, dest):
            self.calls.append((text, "kokoro"))
            Path(dest).write_bytes(b"kokoro:" + text.encode() * 500)
            return True
        ctx["generate_gemini_audio"] = gemini
        ctx["generate_kokoro_audio"] = kokoro
        namespace = ast.Module(body=funcs, type_ignores=[])
        exec(compile(namespace, "generate_assets.py", "exec"), ctx)
        self.ctx = ctx

    async def render(self, label):
        path = str(Path(self.folder.name) / (label + ".mp3"))
        await self.ctx["generate_clean_audio"](label, path)
        return self.ctx["_TTS_NARRATOR_BY_PATH"][os.path.normpath(path)]

    async def test_transient_gemini_failure_replaces_only_bad_chunk(self):
        with patch.dict(os.environ, {
            "AUDIO_TTS_ENGINE": "gemini", "GEMINI_API_KEY": "offline",
            "GEMINI_TTS_MAX_REQUESTS": "12",
        }):
            engines = [await self.render(x) for x in ("scene-1", "bad-audio", "scene-3")]
        self.assertEqual(engines, ["gemini", "kokoro", "gemini"])
        self.assertFalse(self.ctx["_GEMINI_TTS_BLOCKED"])

    async def test_daily_quota_does_not_reattempt_paid_gemini(self):
        with patch.dict(os.environ, {
            "AUDIO_TTS_ENGINE": "gemini", "GEMINI_API_KEY": "offline",
            "GEMINI_TTS_MAX_REQUESTS": "12",
        }):
            engines = [await self.render(x) for x in ("scene-1", "daily-quota", "scene-3")]
        self.assertEqual(engines, ["gemini", "kokoro", "kokoro"])
        self.assertTrue(self.ctx["_GEMINI_TTS_BLOCKED"])
        self.assertEqual(self.calls[-1], ("scene-3", "kokoro"))

    def test_no_atomic_rewrite_remaining(self):
        src = (ROOT / "generate_assets.py").read_text(encoding="utf-8")
        self.assertNotIn("await synthesize_episode(", src)
        self.assertIn("await asyncio.gather(", src)
        self.assertIn('"mode": "per_segment_gemini_first"', src)


if __name__ == "__main__":
    unittest.main()
