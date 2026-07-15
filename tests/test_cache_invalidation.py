import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import quick_clip
from src import asr_runner, chat_runner, clipper


class StageCacheInvalidationTests(unittest.TestCase):
    def _config(self, model_size: str = "medium") -> dict:
        return {
            "asr": {"model_size": model_size, "device": "cpu"},
            "channel": {"default_language": "zh"},
        }

    def _seed_valid_asr_cache(
        self,
        root: Path,
        config: dict,
    ) -> tuple[Path, Path]:
        source = root / "video.mp4"
        source.write_bytes(b"video-data")
        output_dir = root / "output"
        output_dir.mkdir()

        audio_path = output_dir / "audio.wav"
        audio_path.write_bytes(b"cached-audio")
        audio_meta = chat_runner._build_cache_meta(
            source,
            "asr_audio",
            {"channels": 1, "sample_rate_hz": 16000},
        )
        chat_runner._atomic_write_json(
            chat_runner._cache_meta_path(audio_path), audio_meta,
        )

        asr_cfg = config["asr"]
        cache_meta = chat_runner._build_cache_meta(
            source,
            "asr",
            {
                "model_size": asr_cfg["model_size"],
                "device": asr_cfg["device"],
                "resolved_device": "cpu",
                "language": config["channel"]["default_language"],
            },
        )
        chat_runner._write_json_cache(
            output_dir / "asr_cache.json", [], cache_meta,
        )
        return source, output_dir

    def _run_asr(
        self,
        source: Path,
        config: dict,
        output_dir: Path,
    ):
        def fake_extract(_video_path: Path, wav_path: Path) -> None:
            wav_path.write_bytes(b"new-audio")

        stdout = io.StringIO()
        with patch.object(
            asr_runner, "extract_audio", side_effect=fake_extract,
        ) as extract, patch.object(
            asr_runner, "transcribe", return_value=[],
        ) as transcribe, patch.object(
            asr_runner, "detect_volume_peaks", return_value=[],
        ), redirect_stdout(stdout):
            result = asr_runner.run_asr(source, config, output_dir)
        return result, extract, transcribe, stdout.getvalue()

    def test_matching_fingerprint_reuses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config()
            source, output_dir = self._seed_valid_asr_cache(Path(tmp), config)

            result, extract, transcribe, output = self._run_asr(
                source, config, output_dir,
            )

        self.assertEqual(result, [])
        extract.assert_not_called()
        transcribe.assert_not_called()
        self.assertIn("沿用快取", output)

    def test_source_mtime_change_regenerates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config()
            source, output_dir = self._seed_valid_asr_cache(Path(tmp), config)
            stat = source.stat()
            os.utime(
                source,
                ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000),
            )

            _, extract, transcribe, output = self._run_asr(
                source, config, output_dir,
            )

        extract.assert_called_once()
        transcribe.assert_called_once()
        self.assertIn("快取失效原因：source.mtime_ns 變了", output)

    def test_model_change_regenerates_and_reports_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_config = self._config("medium")
            source, output_dir = self._seed_valid_asr_cache(Path(tmp), old_config)

            _, extract, transcribe, output = self._run_asr(
                source, self._config("large-v3"), output_dir,
            )

        extract.assert_not_called()
        transcribe.assert_called_once()
        self.assertIn("快取失效原因：settings.model_size 變了", output)

    def test_cache_without_meta_is_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config()
            source, output_dir = self._seed_valid_asr_cache(Path(tmp), config)
            (output_dir / "asr_cache.meta.json").unlink()

            _, _, transcribe, output = self._run_asr(
                source, config, output_dir,
            )

        transcribe.assert_called_once()
        self.assertIn("缺少 asr_cache.meta.json", output)
        self.assertIn("舊格式快取", output)

    def test_corrupt_json_cache_does_not_crash_and_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._config()
            source, output_dir = self._seed_valid_asr_cache(Path(tmp), config)
            (output_dir / "asr_cache.json").write_text("{", encoding="utf-8")

            _, _, transcribe, output = self._run_asr(
                source, config, output_dir,
            )
            regenerated = json.loads(
                (output_dir / "asr_cache.json").read_text(encoding="utf-8")
            )

        transcribe.assert_called_once()
        self.assertEqual(regenerated, [])
        self.assertIn("asr_cache.json JSON 損毀", output)

    def test_removed_setting_is_reported_as_metadata_difference(self):
        expected = {"settings": {"rois": {"dialogue": {}}}}
        actual = {
            "settings": {
                "rois": {"dialogue": {}, "name": {"x1_norm": 0.1}},
            }
        }

        differences = chat_runner._metadata_differences(expected, actual)

        self.assertIn("settings.rois.name 已移除", differences[0])

    def test_malformed_chat_metadata_is_invalidated_without_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            cache_path = root / "chat_cache.json"
            metadata = chat_runner._build_cache_meta(
                source, "chat", {"aggregate_window_sec": 10.0},
            )
            chat_runner._write_json_cache(
                cache_path,
                {"metadata": [], "messages": []},
                metadata,
            )
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                loaded = chat_runner._load_chat_cache(cache_path, metadata)

        self.assertIsNone(loaded)
        self.assertIn("metadata 格式不正確", stdout.getvalue())


class ClipManifestTests(unittest.TestCase):
    def test_quick_clip_counts_only_manifest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            clips_dir = output_dir / "clips"
            clips_dir.mkdir()
            (clips_dir / "current.mp4").write_bytes(b"current")
            (clips_dir / "stale.mp4").write_bytes(b"stale")
            (output_dir / "clips_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "clips": [
                            {
                                "filename": "current.mp4",
                                "time_start": 1.0,
                                "time_end": 2.0,
                                "segments": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            count = quick_clip._count_current_clips(output_dir)

        self.assertEqual(count, 1)

    def test_old_clips_are_archived_and_empty_manifest_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            clips_dir = output_dir / "clips"
            clips_dir.mkdir(parents=True)
            (clips_dir / "clip_001.mp4").write_bytes(b"old")

            with patch.object(clipper.shutil, "which", return_value=None), \
                    redirect_stdout(io.StringIO()):
                result = clipper.extract_clips(source, [], output_dir, {})

            manifest = json.loads(
                (output_dir / "clips_manifest.json").read_text(encoding="utf-8")
            )
            current_clip_exists = (clips_dir / "clip_001.mp4").exists()
            archived_clip_exists = (
                output_dir / "clips_old" / "clip_001.mp4"
            ).exists()

        self.assertEqual(result, [])
        self.assertEqual(manifest["clips"], [])
        self.assertFalse(current_clip_exists)
        self.assertTrue(archived_clip_exists)


if __name__ == "__main__":
    unittest.main()
