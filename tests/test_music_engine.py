"""Offline regression checks; no remote requests, paid APIs or third-party music."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import music_engine


class MusicEngineTests(unittest.TestCase):
    def test_story_mood_is_dynamic(self):
        self.assertEqual(music_engine.scene_mood({"director": {"mood": "suspense"}}), "mystery")
        self.assertEqual(music_engine.scene_mood({"entertainmentBeat": "reveal"}), "revelation")
        self.assertEqual(music_engine.scene_mood({"visualBeats": [{"mood": "celebration"}]}), "uplifting")
        self.assertEqual(music_engine.scene_mood({"director": {"mood": "gentle compassion"}}), "emotional")
        self.assertEqual(music_engine.scene_mood({}), "devotional")

    def test_no_internal_url_or_plain_http(self):
        for url in ("http://example.com/foo.mp3", "https://localhost/a.mp3",
                    "https://127.0.0.1/a.mp3", "https://192.168.1.2/a.mp3",
                    "https://site.local/file", "https://example.com:8443/track"):
            self.assertFalse(music_engine._source_url_ok(url), url)
        self.assertTrue(music_engine._source_url_ok("https://upload.wikimedia.org/example.ogg"))

    def test_openverse_refuses_cc_by_and_pdm(self):
        fake = {"results": [
            {"license": "by", "url": "https://example.com/by.mp3",
             "foreign_landing_url": "https://example.com/by"},
            {"license": "pdm", "url": "https://example.com/pdm.mp3",
             "foreign_landing_url": "https://example.com/pdm"},
            {"license": "cc0", "url": "https://example.com/cc0.mp3",
             "foreign_landing_url": "https://example.com/cc0", "title": "Free flute"},
        ]}
        with patch.object(music_engine, "_get_json", return_value=fake):
            tracks = list(music_engine._openverse_candidates("devotional"))
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["license"], "CC0-1.0")
        self.assertTrue(tracks[0]["requires_review"])

    def test_commons_rejects_broad_public_domain(self):
        def page(name, license_name, license_url):
            return {"title": name, "imageinfo": [{
                "url": "https://upload.wikimedia.org/test.ogg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.ogg",
                "extmetadata": {
                    "LicenseShortName": {"value": license_name},
                    "LicenseUrl": {"value": license_url},
                },
            }]}
        fake = {"query": {"pages": [
            page("PD label", "Public Domain", ""),
            page("CC-BY", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
            page("CC0", "CC0 1.0", music_engine.LICENSE_CC0),
        ]}}
        with patch.object(music_engine, "_get_json", return_value=fake):
            tracks = list(music_engine._wikimedia_candidates("devotional"))
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["source"], "Wikimedia Commons")

    def test_manual_manifest_requires_hash_and_cross_platform_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "flute.mp3"
            p.write_bytes(b"made up binary for hash validation")
            entry = {
                "title": "Approved recording",
                "file": "flute.mp3",
                "license": "Mixkit Stock Music Free License",
                "license_url": music_engine.LICENSE_MIXKIT,
                "source_url": "https://mixkit.co/free-stock-music/",
                "moods": ["devotional"],
                "platforms": ["youtube", "instagram"],
                "approved": True,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps([entry]), encoding="utf-8")
            self.assertEqual(len(list(music_engine._approved_candidates("devotional", tmp))), 1)
            entry["sha256"] = "0" * 64
            manifest.write_text(json.dumps([entry]), encoding="utf-8")
            self.assertEqual(len(list(music_engine._approved_candidates("devotional", tmp))), 0)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "FFmpeg is required for soundtrack tests")
    def test_original_music_fallback_and_scene_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            long = [{"scene_number": 1, "director": {"mood": "mystery"}},
                    {"scene_number": 2, "director": {"mood": "devotional"}}]
            shorts = [{"scene_number": 1, "entertainmentBeat": "reveal"},
                      {"scene_number": 2, "director": {"mood": "mystery"}}]
            report = music_engine.attach_music(
                long, shorts,
                music_dir=str(Path(tmp) / "music"),
                report_path=str(Path(tmp) / "report.json"),
                approved_dir=str(Path(tmp) / "empty"),
                remote_enabled=False,
            )
            self.assertEqual(len(report["tracks"]), 3)
            self.assertEqual(report["status"], "ready")
            self.assertEqual(long[0]["musicFile"], shorts[1]["musicFile"])
            for track in report["tracks"]:
                path = Path(tmp) / track["file"].replace("music/", "music/", 1)
                self.assertTrue(path.is_file())
                self.assertGreater(music_engine._audio_seconds(path), 34)


if __name__ == "__main__":
    unittest.main()
