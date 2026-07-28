import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src import ocr_runner


ROI = {
    "dialogue": {
        "x1_norm": 0.0,
        "y1_norm": 0.0,
        "x2_norm": 1.0,
        "y2_norm": 1.0,
    }
}


def _pipe_process(payload: bytes, return_code: int = 0) -> MagicMock:
    process = MagicMock()
    process.stdout = io.BytesIO(payload)
    process.stderr = io.BytesIO()
    process.wait.return_value = return_code
    process.poll.return_value = return_code
    return process


class FfmpegOcrDecoderTests(unittest.TestCase):
    def test_mock_pipe_frame_count_timestamps_and_source_frames(self):
        frames = [
            np.full((2, 2, 3), fill_value=value, dtype=np.uint8).tobytes()
            for value in (10, 20, 30)
        ]
        process = _pipe_process(b"".join(frames))
        report: dict = {}

        with patch.object(ocr_runner, "_probe_video_stream", return_value=(2, 2, 30.0)), \
                patch.object(ocr_runner.subprocess, "Popen", return_value=process) as popen, \
                patch.object(ocr_runner.imagehash, "phash", side_effect=[0, 10, 20]), \
                patch.object(ocr_runner, "_ocr_image", side_effect=["對白一", "對白二", "對白三"]):
            results = ocr_runner._process_video_headless(
                Path("video.mp4"),
                ROI,
                sample_interval_sec=0.5,
                stable_threshold=1,
                decoder="ffmpeg",
                stage_report=report,
            )

        self.assertEqual(len(results), 3)
        self.assertEqual([row["frame_time"] for row in results], [0.0, 0.5, 1.0])
        self.assertEqual([row["frame_index"] for row in results], [0, 15, 30])
        self.assertEqual(report["decoder"], "ffmpeg")
        command = popen.call_args.args[0]
        self.assertIn("fps=1/0.5", command)
        self.assertIn("rgb24", command)
        self.assertIn("pipe:1", command)

    def test_pipe_start_failure_falls_back_to_opencv_and_warns(self):
        report: dict = {}
        output = io.StringIO()
        expected = [{"dialogue": "fallback"}]

        with patch.object(ocr_runner, "_probe_video_stream", return_value=(2, 2, 30.0)), \
                patch.object(
                    ocr_runner.subprocess,
                    "Popen",
                    side_effect=FileNotFoundError("ffmpeg"),
                ), \
                patch.object(
                    ocr_runner, "_process_video_opencv", return_value=expected,
                ) as opencv, redirect_stdout(output):
            results = ocr_runner._process_video_headless(
                Path("video.mp4"), ROI, decoder="ffmpeg", stage_report=report
            )

        self.assertIs(results, expected)
        opencv.assert_called_once()
        self.assertEqual(report["decoder"], "opencv")
        self.assertIn("ffmpeg decoder 失敗", output.getvalue())
        self.assertIn("改用 opencv", output.getvalue())

    def test_midstream_short_frame_falls_back_to_opencv(self):
        complete_frame = bytes(2 * 2 * 3)
        process = _pipe_process(complete_frame + b"short")
        output = io.StringIO()

        with patch.object(ocr_runner, "_probe_video_stream", return_value=(2, 2, 30.0)), \
                patch.object(ocr_runner.subprocess, "Popen", return_value=process), \
                patch.object(ocr_runner.imagehash, "phash", return_value=0), \
                patch.object(ocr_runner, "_process_video_opencv", return_value=[]) as opencv, \
                redirect_stdout(output):
            results = ocr_runner._process_video_headless(
                Path("video.mp4"), ROI, stable_threshold=2, decoder="ffmpeg"
            )

        self.assertEqual(results, [])
        opencv.assert_called_once()
        self.assertIn("中途斷流", output.getvalue())


class OcrDecoderCacheTests(unittest.TestCase):
    def test_decoder_is_in_fingerprint_and_switch_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            output_dir.mkdir()
            roi_path = root / "ocr_config.json"
            roi_path.write_text(json.dumps({"rois": ROI}), encoding="utf-8")

            with patch.object(ocr_runner, "_process_video_headless", return_value=[]) as process:
                ocr_runner.run_ocr(
                    source,
                    {"ocr": {"decoder": "ffmpeg"}},
                    output_dir,
                    ocr_config_path=roi_path,
                )
                process.reset_mock()
                first_meta = json.loads(
                    (output_dir / "ocr_cache.meta.json").read_text(encoding="utf-8")
                )

                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    ocr_runner.run_ocr(
                        source,
                        {"ocr": {"decoder": "opencv"}},
                        output_dir,
                        ocr_config_path=roi_path,
                    )

            second_meta = json.loads(
                (output_dir / "ocr_cache.meta.json").read_text(encoding="utf-8")
            )

        self.assertEqual(first_meta["settings"]["decoder"], "ffmpeg")
        self.assertEqual(second_meta["settings"]["decoder"], "opencv")
        process.assert_called_once()
        self.assertEqual(process.call_args.kwargs["decoder"], "opencv")
        self.assertIn("decoder", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
