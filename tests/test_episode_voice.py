"""Offline, zero-credit tests for episode-wide voice selection."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from scripts.episode_voice import cache_key, synthesize_episode


class EpisodeVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cache = self.base / "cache"
        self.report = self.base / "out" / "voice_episode_report.json"
        self.tasks = [
            {"text": f"कथा {i}", "beat": "wonder",
             "path": str(self.base / f"chunk_{i}.mp3")}
            for i in range(3)
        ]
        self.calls = []
        self.env = {
            "GEMINI_API_KEY": "fake-no-network",
            "GEMINI_TTS_MAX_REQUESTS": "12",
            "GEMINI_TTS_MAX_API_ATTEMPTS": "18",
            "GEMINI_TTS_VOICE": "Kore",
        }

    def duration(self, path):
        return 3.0 if Path(path).is_file() and Path(path).stat().st_size > 1000 else 0.0

    async def render(self, text, output, beat, *, engine, strict_engine):
        self.assertTrue(strict_engine)
        self.calls.append((text, engine))
        Path(output).write_bytes((engine + ":" + text).encode("utf-8") * 100)
        return [{"word": text, "start": 0.0, "end": 2.0}]

    async def run_episode(self, callback=None, requested="gemini", env=None):
        return await synthesize_episode(
            self.tasks, callback or self.render, self.duration,
            lambda x: x, requested=requested, cache_dir=self.cache,
            report_path=self.report, env=env or self.env,
        )

    async def test_late_gemini_quota_failure_regenerates_all_chunks_with_kokoro(self):
        async def fail_late(text, output, beat, *, engine, strict_engine):
            if engine == "gemini" and text == "कथा 2":
                raise RuntimeError("quota_daily_exhausted")
            return await self.render(text, output, beat, engine=engine, strict_engine=strict_engine)
        words, report = await self.run_episode(fail_late)
        self.assertEqual(len(words), 3)
        self.assertEqual(report["engine"], "kokoro")
        self.assertFalse(report["mixed_engines"])
        self.assertEqual([x[1] for x in self.calls],
                         ["gemini", "gemini", "kokoro", "kokoro", "kokoro"])
        for task in self.tasks:
            self.assertTrue(Path(task["path"]).read_bytes().startswith(b"kokoro:"))
        self.assertEqual(json.loads(self.report.read_text())["engine"], "kokoro")

    async def test_budget_preflight_skips_gemini_without_using_it(self):
        env = {**self.env, "GEMINI_TTS_MAX_REQUESTS": "2"}
        _, report = await self.run_episode(env=env)
        self.assertEqual(report["engine"], "kokoro")
        self.assertTrue(all(engine == "kokoro" for _, engine in self.calls))
        self.assertEqual(report["fallback_events"][0]["reason"],
                         "episode_exceeds_configured_request_cap")

    async def test_known_daily_remaining_is_respected(self):
        env = {**self.env, "GEMINI_TTS_DAILY_REMAINING": "1"}
        _, report = await self.run_episode(env=env)
        self.assertEqual(report["engine"], "kokoro")
        self.assertEqual(report["fallback_events"][0]["reason"],
                         "episode_exceeds_known_daily_quota")

    async def test_replay_uses_voice_and_text_hash_cache(self):
        _, first = await self.run_episode()
        self.assertEqual(first["new_chunks"], 3)
        self.calls.clear()
        _, second = await self.run_episode()
        self.assertEqual(self.calls, [])
        self.assertEqual(second["engine"], "gemini")
        self.assertEqual(second["cache_hits"], 3)

    async def test_voice_setting_invalidates_old_cache(self):
        await self.run_episode()
        self.calls.clear()
        _, report = await self.run_episode(env={**self.env, "GEMINI_TTS_VOICE": "Aoede"})
        self.assertEqual(report["cache_hits"], 0)
        self.assertEqual(len(self.calls), 3)
        self.assertNotEqual(cache_key("कथा 1", "wonder", "gemini", self.env),
                            cache_key("कथा 1", "wonder", "gemini",
                                      {**self.env, "GEMINI_TTS_VOICE": "Aoede"}))

    async def test_kokoro_failure_falls_back_entire_episode_to_edge(self):
        async def fail_kokoro(text, output, beat, *, engine, strict_engine):
            if engine == "kokoro" and text == "कथा 1":
                raise RuntimeError("model unavailable")
            return await self.render(text, output, beat, engine=engine, strict_engine=strict_engine)
        _, report = await self.run_episode(fail_kokoro, requested="kokoro")
        self.assertEqual(report["engine"], "edge")
        self.assertTrue(all(Path(t["path"]).read_bytes().startswith(b"edge:")
                            for t in self.tasks))

    async def test_total_failure_fails_closed_without_partial_audio(self):
        async def always_fail(*args, **kwargs):
            raise RuntimeError("no voice available")
        with self.assertRaisesRegex(RuntimeError, "refusing mixed voices"):
            await self.run_episode(always_fail)
        self.assertTrue(all(not Path(t["path"]).exists() for t in self.tasks))
        self.assertEqual(json.loads(self.report.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
