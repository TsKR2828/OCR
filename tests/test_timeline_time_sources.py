import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, patch

from src import chat_runner, pipeline


def _message(timestamp_ms: str) -> dict:
    return {
        "author": "viewer",
        "text": "hello",
        "timestamp_ms": timestamp_ms,
        "type": "normal",
        "amount": None,
    }


def _source_file(output_dir: Path) -> Path:
    source = output_dir / "source.mp4"
    source.write_bytes(b"video")
    return source


def _write_chat_sidecar(
    output_dir: Path,
    source: Path,
    config: dict,
    video_id: str = "video-id",
) -> None:
    chat_cfg = config.get("chat", {})
    settings = {
        "video_id": video_id,
        "aggregate_window_sec": chat_cfg.get("aggregate_window_sec", 10.0),
        "spike_threshold": chat_cfg.get("spike_threshold", 2.5),
        "max_messages_per_segment": chat_cfg.get("max_messages_per_segment", 5),
        "min_spike_messages": chat_cfg.get("min_spike_messages", 3),
        "include_superchat": chat_cfg.get("include_superchat", True),
        "reaction_keywords": config.get("keywords", {}).get("reaction", []),
    }
    chat_runner._atomic_write_json(
        output_dir / "chat_cache.meta.json",
        chat_runner._build_cache_meta(source, "chat", settings),
    )


class ChatStreamStartTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "chat": {"enabled": True, "aggregate_window_sec": 10.0},
            "keywords": {"reaction": []},
        }

    def test_api_start_is_used_and_written_to_new_cache(self):
        api_start_ms = 1_700_000_000_000.0
        messages = [_message("2024-01-01T00:00:30Z")]

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"}), \
                patch.object(chat_runner, "_build_youtube_service", return_value=object()), \
                patch.object(chat_runner, "_get_live_chat_id", return_value="chat-id"), \
                patch.object(chat_runner, "_get_stream_start_time", return_value=api_start_ms), \
                patch.object(chat_runner, "_fetch_all_messages", return_value=messages), \
                patch.object(chat_runner, "aggregate_chat", return_value=[]) as aggregate:
            output_dir = Path(tmp)
            source = _source_file(output_dir)
            chat_runner.run_chat(
                "video-id", self.config, output_dir, 120.0, source_path=source,
            )

            self.assertEqual(
                aggregate.call_args.kwargs["stream_start_ms"], api_start_ms,
            )
            payload = json.loads(
                (output_dir / "chat_cache.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["metadata"]["stream_start_ms"], api_start_ms)
            self.assertEqual(payload["messages"], messages)
            self.assertTrue((output_dir / "chat_cache.meta.json").exists())

    def test_new_cache_metadata_precedes_first_message(self):
        metadata_start_ms = 1_650_000_000_000.0
        payload = {
            "metadata": {"stream_start_ms": metadata_start_ms},
            "messages": [_message("2024-01-01T00:00:30Z")],
        }

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"}), \
                patch.object(chat_runner, "_build_youtube_service") as build_service, \
                patch.object(chat_runner, "aggregate_chat", return_value=[]) as aggregate:
            output_dir = Path(tmp)
            source = _source_file(output_dir)
            (output_dir / "chat_cache.json").write_text(
                json.dumps(payload), encoding="utf-8",
            )
            _write_chat_sidecar(output_dir, source, self.config)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                chat_runner.run_chat(
                    "video-id", self.config, output_dir, 120.0, source_path=source,
                )

            build_service.assert_not_called()
            self.assertEqual(
                aggregate.call_args.kwargs["stream_start_ms"], metadata_start_ms,
            )
            self.assertNotIn("可能不準", stdout.getvalue())

    def test_legacy_array_cache_falls_back_to_first_message_and_warns(self):
        first_timestamp = "2024-01-01T00:00:30Z"
        expected_start_ms = (
            datetime.fromisoformat(first_timestamp.replace("Z", "+00:00")).timestamp()
            * 1000
        )

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"}), \
                patch.object(chat_runner, "aggregate_chat", return_value=[]) as aggregate:
            output_dir = Path(tmp)
            source = _source_file(output_dir)
            (output_dir / "chat_cache.json").write_text(
                json.dumps([_message(first_timestamp)]), encoding="utf-8",
            )
            _write_chat_sidecar(output_dir, source, self.config)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                chat_runner.run_chat(
                    "video-id", self.config, output_dir, 120.0, source_path=source,
                )

            self.assertEqual(
                aggregate.call_args.kwargs["stream_start_ms"], expected_start_ms,
            )
            self.assertIn("警告", stdout.getvalue())
            self.assertIn("可能不準", stdout.getvalue())


class MediaDurationTests(unittest.TestCase):
    def test_media_duration_uses_ffprobe_even_when_asr_is_empty(self):
        completed = subprocess.CompletedProcess(
            args=["ffprobe"], returncode=0, stdout="321.75\n", stderr="",
        )
        with patch.object(pipeline.subprocess, "run", return_value=completed) as run:
            duration = pipeline._get_media_duration(Path("video.mp4"), [])

        self.assertEqual(duration, 321.75)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "ffprobe")
        self.assertIn("-v", cmd)
        self.assertIn("error", cmd)
        self.assertIn("-show_entries", cmd)
        self.assertIn("format=duration", cmd)
        self.assertIn("video.mp4", cmd)
        self.assertTrue(run.call_args.kwargs["check"])

    def test_media_duration_falls_back_to_asr_and_warns(self):
        segments = [SimpleNamespace(time_end=12.5), SimpleNamespace(time_end=48.0)]
        stdout = io.StringIO()
        with patch.object(
            pipeline.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(1, ["ffprobe"]),
        ), redirect_stdout(stdout):
            duration = pipeline._get_media_duration(Path("video.mp4"), segments)

        self.assertEqual(duration, 48.0)
        self.assertIn("警告", stdout.getvalue())
        self.assertIn("ffprobe", stdout.getvalue())
        self.assertIn("改用 ASR", stdout.getvalue())

    def test_pipeline_passes_media_duration_to_chat(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(pipeline, "load_config", return_value={}), \
                patch.object(pipeline, "make_output_dir", return_value=Path(tmp)), \
                patch.object(pipeline, "run_asr", return_value=[]), \
                patch.object(pipeline, "_get_media_duration", return_value=555.5), \
                patch.object(pipeline, "run_chat", return_value=[]) as run_chat, \
                patch.object(pipeline, "align_mvp", return_value=[]), \
                patch.object(pipeline, "classify_all"), \
                patch.object(pipeline, "save_timeline"), \
                patch.object(pipeline, "render_index"), \
                patch.object(pipeline, "render_excel"), \
                patch.object(pipeline, "render_stats"):
            with redirect_stdout(io.StringIO()):
                pipeline.run_pipeline(
                    Path("video.mp4"), Path("config.yaml"), Path(tmp),
                )

        run_chat.assert_called_once_with(
            None, {}, Path(tmp), 555.5,
            chat_url=None,
            source_path=Path("video.mp4"),
            stage_report=ANY,
        )


if __name__ == "__main__":
    unittest.main()
