import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer

import quick_clip
from src import chat_runner, clipper, ocr_runner, pipeline
from src.schema import Score, Segment


class PipelineJobTests(unittest.TestCase):
    def _patch_pipeline_shell(
        self,
        stack: ExitStack,
        output_dir: Path,
        config: dict | None = None,
        timeline: list[Segment] | None = None,
    ) -> None:
        config = config or {}
        timeline = timeline or []
        stack.enter_context(patch.object(pipeline, "load_config", return_value=config))
        stack.enter_context(
            patch.object(pipeline, "make_output_dir", return_value=output_dir)
        )
        stack.enter_context(
            patch.object(pipeline, "_get_media_duration", return_value=120.0)
        )
        stack.enter_context(patch.object(pipeline, "align_mvp", return_value=timeline))
        stack.enter_context(patch.object(pipeline, "align_full", return_value=timeline))
        for name in (
            "classify_all",
            "save_timeline",
            "render_index",
            "render_excel",
            "render_stats",
            "render_conflict_report",
            "render_clips_index",
            "render_edl",
        ):
            stack.enter_context(patch.object(pipeline, name))

    @staticmethod
    def _successful_stage(result, artifact: Path, cache_hit: bool = False):
        def run(*_args, stage_report=None, **_kwargs):
            stage_report.update(
                status="success",
                cache_hit=cache_hit,
                artifacts=[str(artifact)],
            )
            return result

        return run

    def test_all_stages_success_write_job_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()
            artifacts = {
                name: output_dir / f"{name}.json"
                for name in ("asr", "chat", "ocr", "clipper")
            }
            for path in artifacts.values():
                path.write_text("{}", encoding="utf-8")

            self._patch_pipeline_shell(stack, output_dir)
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_asr",
                    side_effect=self._successful_stage([], artifacts["asr"], True),
                )
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_chat",
                    side_effect=self._successful_stage([], artifacts["chat"]),
                )
            )
            stack.enter_context(
                patch(
                    "src.ocr_runner.run_ocr",
                    side_effect=self._successful_stage([], artifacts["ocr"]),
                )
            )

            clip_result = [{"path": str(output_dir / "clips" / "clip.mp4")}]

            def run_clipper(*_args, stage_report=None, **_kwargs):
                stage_report.update(
                    status="success",
                    artifacts=[str(artifacts["clipper"])],
                    attempted_count=1,
                    success_count=1,
                    failed_count=0,
                    reel_created=False,
                )
                return clip_result

            stack.enter_context(
                patch.object(pipeline, "extract_clips", side_effect=run_clipper)
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = pipeline.run_pipeline(
                    source,
                    root / "config.yaml",
                    root,
                    enable_ocr=True,
                    enable_clips=True,
                )
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, output_dir)
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(job["status"], "success")
        self.assertEqual(
            {name: stage["status"] for name, stage in job["stages"].items()},
            {name: "success" for name in ("asr", "chat", "ocr", "clipper")},
        )
        for stage in job["stages"].values():
            self.assertTrue(stage["started_at"])
            self.assertTrue(stage["ended_at"])
            self.assertGreaterEqual(stage["duration_sec"], 0)
            self.assertIsInstance(stage["artifacts"], list)
            self.assertIsInstance(stage["cache_hit"], bool)
        self.assertTrue(job["stages"]["asr"]["cache_hit"])
        self.assertIn("Pipeline 成功", stdout.getvalue())
        self.assertNotIn("完成！", stdout.getvalue())

    def test_missing_ocr_config_is_skipped_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()

            self._patch_pipeline_shell(stack, output_dir)
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_asr",
                    side_effect=self._successful_stage([], output_dir / "asr.json"),
                )
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_chat",
                    side_effect=self._successful_stage([], output_dir / "chat.json"),
                )
            )

            with redirect_stdout(io.StringIO()):
                result = pipeline.run_pipeline(
                    source,
                    root / "config.yaml",
                    root,
                    enable_ocr=True,
                    ocr_config_path=root / "missing_roi.json",
                )
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result, output_dir)
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(job["stages"]["ocr"]["status"], "skipped")
        self.assertIn("ROI 設定檔", job["stages"]["ocr"]["reason"])

    def test_ocr_unopenable_media_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "broken.mp4"
            source.write_bytes(b"not a video")
            output_dir = root / "output"
            output_dir.mkdir()
            roi_path = root / "ocr_config.json"
            roi_path.write_text(
                json.dumps({"rois": {"dialogue": [0, 0, 1, 1]}}),
                encoding="utf-8",
            )

            self._patch_pipeline_shell(stack, output_dir)
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_asr",
                    side_effect=self._successful_stage([], output_dir / "asr.json"),
                )
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_chat",
                    side_effect=self._successful_stage([], output_dir / "chat.json"),
                )
            )
            capture = MagicMock()
            capture.isOpened.return_value = False
            stack.enter_context(
                patch("src.ocr_runner.cv2.VideoCapture", return_value=capture)
            )

            with redirect_stdout(io.StringIO()), self.assertRaises(
                pipeline.PipelineFailed
            ):
                pipeline.run_pipeline(
                    source,
                    root / "config.yaml",
                    root,
                    enable_ocr=True,
                    ocr_config_path=roi_path,
                )
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        self.assertEqual(job["stages"]["ocr"]["status"], "failed")
        self.assertIn("無法開啟影片供 OCR", job["stages"]["ocr"]["error"])
        self.assertEqual(job["exit_code"], 1)

    def test_ocr_opened_media_with_zero_frames_raises(self):
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.get.side_effect = [30.0, 1.0]
        capture.read.return_value = (False, None)

        with patch.object(ocr_runner.cv2, "VideoCapture", return_value=capture), \
                self.assertRaisesRegex(RuntimeError, "無法讀取任何影片畫面"):
            ocr_runner._process_video_headless(
                Path("zero-frame.mp4"), {"dialogue": [0, 0, 1, 1]}
            )

    def test_stage_exception_is_failed_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()

            self._patch_pipeline_shell(stack, output_dir)
            stack.enter_context(
                patch.object(
                    pipeline, "run_asr", side_effect=RuntimeError("ASR boom")
                )
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_chat",
                    side_effect=self._successful_stage([], output_dir / "chat.json"),
                )
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout), self.assertRaises(
                pipeline.PipelineFailed
            ) as raised:
                pipeline.run_pipeline(source, root / "config.yaml", root)
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(job["exit_code"], 1)
        self.assertEqual(job["stages"]["asr"]["status"], "failed")
        self.assertIn("ASR boom", job["stages"]["asr"]["error"])
        self.assertIn("FAILED", stdout.getvalue())
        self.assertIn("Pipeline 失敗", stdout.getvalue())

    def test_caught_chat_api_error_is_persisted_as_failed(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()

            self._patch_pipeline_shell(
                stack,
                output_dir,
                config={"chat": {"enabled": True}},
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_asr",
                    side_effect=self._successful_stage([], output_dir / "asr.json"),
                )
            )
            stack.enter_context(
                patch.dict(os.environ, {"YOUTUBE_API_KEY": "test"})
            )
            stack.enter_context(
                patch.object(
                    chat_runner,
                    "_build_youtube_service",
                    side_effect=RuntimeError("chat API boom"),
                )
            )

            with redirect_stdout(io.StringIO()), self.assertRaises(
                pipeline.PipelineFailed
            ):
                pipeline.run_pipeline(
                    source,
                    root / "config.yaml",
                    root,
                    video_id="video-id",
                )
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        self.assertEqual(job["stages"]["chat"]["status"], "failed")
        self.assertIn("chat API boom", job["stages"]["chat"]["error"])
        self.assertEqual(job["exit_code"], 1)

    def test_partial_clips_record_success_and_failure_counts(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()
            timeline = [
                Segment(time_start=10.0, time_end=12.0, score=Score(total=20)),
                Segment(time_start=100.0, time_end=102.0, score=Score(total=25)),
            ]
            config = {
                "highlight": {
                    "min_score": 15,
                    "clip_padding_sec": 0,
                    "clip_merge_gap_sec": 0,
                    "min_clip_sec": 1,
                    "max_clip_sec": 30,
                }
            }

            self._patch_pipeline_shell(stack, output_dir, config, timeline)
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_asr",
                    side_effect=self._successful_stage([], output_dir / "asr.json"),
                )
            )
            stack.enter_context(
                patch.object(
                    pipeline,
                    "run_chat",
                    side_effect=self._successful_stage([], output_dir / "chat.json"),
                )
            )
            stack.enter_context(patch.object(clipper.shutil, "which", return_value="ffmpeg"))
            stack.enter_context(patch.object(clipper, "_probe_duration", return_value=200.0))
            attempts = 0

            def run_ffmpeg(cmd, **_kwargs):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    Path(cmd[-1]).write_bytes(b"clip")
                    return subprocess.CompletedProcess(cmd, 0)
                raise subprocess.CalledProcessError(
                    1, ["ffmpeg"], stderr=b"mock clip failure"
                )

            stack.enter_context(
                patch.object(clipper.subprocess, "run", side_effect=run_ffmpeg)
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = pipeline.run_pipeline(
                    source,
                    root / "config.yaml",
                    root,
                    enable_clips=True,
                    clip_vertical=True,
                )
            job = json.loads(
                (output_dir / "job.json").read_text(encoding="utf-8")
            )

        clip_stage = job["stages"]["clipper"]
        self.assertEqual(result, output_dir)
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(clip_stage["status"], "partial")
        self.assertEqual(clip_stage["attempted_count"], 2)
        self.assertEqual(clip_stage["success_count"], 1)
        self.assertEqual(clip_stage["failed_count"], 1)
        self.assertIn("PARTIAL", stdout.getvalue())


class ClipperFailureStatusTests(unittest.TestCase):
    def test_missing_ffmpeg_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            report = {}

            with patch.object(clipper.shutil, "which", return_value=None), \
                    redirect_stdout(io.StringIO()):
                result = clipper.extract_clips(
                    source, [], output_dir, {}, stage_report=report,
                )

        self.assertEqual(result, [])
        self.assertEqual(report["status"], "failed")
        self.assertIn("ffmpeg", report["error"])

    def test_all_clip_attempts_failed_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            report = {}
            segments = [
                Segment(time_start=10.0, time_end=12.0, score=Score(total=20)),
            ]

            with patch.object(clipper.shutil, "which", return_value="ffmpeg"), \
                    patch.object(clipper, "_probe_duration", return_value=30.0), \
                    patch.object(
                        clipper.subprocess,
                        "run",
                        side_effect=subprocess.CalledProcessError(
                            1, ["ffmpeg"], stderr=b"all failed",
                        ),
                    ), redirect_stdout(io.StringIO()):
                result = clipper.extract_clips(
                    source,
                    segments,
                    output_dir,
                    {"highlight": {"clip_padding_sec": 0}},
                    vertical=True,
                    stage_report=report,
                )

        self.assertEqual(result, [])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["attempted_count"], 1)
        self.assertEqual(report["success_count"], 0)
        self.assertEqual(report["failed_count"], 1)
        self.assertIn("所有 1 個 clip", report["error"])
        self.assertIn("all failed", report["error"])

    def test_ffmpeg_success_without_output_file_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            report = {}
            segments = [
                Segment(time_start=10.0, time_end=12.0, score=Score(total=20)),
            ]

            with patch.object(clipper.shutil, "which", return_value="ffmpeg"), \
                    patch.object(clipper, "_probe_duration", return_value=30.0), \
                    patch.object(
                        clipper.subprocess,
                        "run",
                        return_value=subprocess.CompletedProcess([], 0),
                    ), redirect_stdout(io.StringIO()):
                result = clipper.extract_clips(
                    source,
                    segments,
                    output_dir,
                    {"highlight": {"clip_padding_sec": 0}},
                    vertical=True,
                    stage_report=report,
                )

        self.assertEqual(result, [])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["success_count"], 0)
        self.assertIn("未產生有效 clip 輸出檔", report["error"])

    def test_stale_reel_is_not_counted_when_current_reel_has_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "highlight_reel.mp4").write_bytes(b"stale reel")
            report = {}
            segments = [
                Segment(time_start=10.0, time_end=12.0, score=Score(total=20)),
                Segment(time_start=100.0, time_end=102.0, score=Score(total=25)),
            ]
            attempts = 0

            def run_ffmpeg(cmd, **_kwargs):
                nonlocal attempts
                attempts += 1
                if attempts <= 2:
                    Path(cmd[-1]).write_bytes(b"clip")
                return subprocess.CompletedProcess(cmd, 0)

            with patch.object(clipper.shutil, "which", return_value="ffmpeg"), \
                    patch.object(clipper, "_probe_duration", return_value=200.0), \
                    patch.object(clipper.subprocess, "run", side_effect=run_ffmpeg), \
                    redirect_stdout(io.StringIO()):
                result = clipper.extract_clips(
                    source,
                    segments,
                    output_dir,
                    {
                        "highlight": {
                            "clip_padding_sec": 0,
                            "clip_merge_gap_sec": 0,
                        }
                    },
                    vertical=True,
                    make_reel=True,
                    stage_report=report,
                )
            current_reel_exists = (output_dir / "highlight_reel.mp4").exists()
            archived_reel_exists = (
                output_dir / "clips_old" / "highlight_reel.mp4"
            ).exists()

        self.assertEqual(len(result), 2)
        self.assertEqual(report["status"], "partial")
        self.assertFalse(report["reel_created"])
        self.assertIn("精選合輯產出失敗", report["error"])
        self.assertFalse(current_reel_exists)
        self.assertTrue(archived_reel_exists)


class QuickClipStatusTests(unittest.TestCase):
    def test_fallback_ignores_zero_byte_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            clips_dir = output_dir / "clips"
            clips_dir.mkdir()
            (clips_dir / "empty.mp4").write_bytes(b"")

            with redirect_stdout(io.StringIO()):
                count, invalid = quick_clip._current_clip_counts(output_dir)

        self.assertEqual(count, 0)
        self.assertEqual(invalid, 1)

    def test_manifest_entry_without_file_counts_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "clips").mkdir()
            (output_dir / "clips_manifest.json").write_text(
                json.dumps(
                    {"version": 1, "clips": [{"filename": "missing.mp4"}]}
                ),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                count, invalid = quick_clip._current_clip_counts(output_dir)

        self.assertEqual(count, 0)
        self.assertEqual(invalid, 1)

    def test_zero_clips_reports_failure_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "clips_manifest.json").write_text(
                json.dumps({"version": 1, "clips": []}),
                encoding="utf-8",
            )
            (output_dir / "job.json").write_text(
                json.dumps(
                    {
                        "exit_code": 0,
                        "stages": {
                            "clipper": {
                                "status": "failed",
                                "failed_count": 2,
                                "reel_created": False,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with patch.object(pipeline, "run_pipeline", return_value=output_dir), \
                    redirect_stdout(stdout), self.assertRaises(typer.Exit) as raised:
                quick_clip.main(
                    input_file=source,
                    config=root / "config.yaml",
                    output=root,
                    chat_url=None,
                    title="",
                    vertical=True,
                    burn_subs=True,
                    reel=True,
                    fast=False,
                )

        output = stdout.getvalue()
        self.assertEqual(raised.exception.exit_code, 1)
        self.assertIn("出片失敗", output)
        self.assertIn("成功 0 / 失敗 2", output)
        self.assertIn("合輯：無", output)
        self.assertNotIn("出片完成", output)


if __name__ == "__main__":
    unittest.main()
