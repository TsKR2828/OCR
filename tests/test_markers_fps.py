import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src import pipeline
from src.renderers.markers import _smpte_tc, render_edl


class TimecodeTests(unittest.TestCase):
    # Fixed SMPTE values. DF boundaries follow SMPTE ST 12-1 and Apple TN2310:
    # https://developer.apple.com/library/archive/technotes/tn2310/_index.html

    def test_30fps_ndf_known_value(self):
        self.assertEqual(_smpte_tc(3661.5, 30.0), "01:01:01:15")

    def test_2997_drop_frame_known_minute_and_ten_minute_values(self):
        fps = 30000 / 1001
        self.assertEqual(_smpte_tc(61.0, fps), "00:01:01;00")
        self.assertEqual(_smpte_tc(600.0, fps), "00:10:00;00")

    def test_25fps_ndf_known_value(self):
        self.assertEqual(_smpte_tc(3661.4, 25.0), "01:01:01:10")

    def test_23976_is_ndf_and_does_not_skip_minute_frame_zero(self):
        fps = 24000 / 1001
        self.assertEqual(_smpte_tc(60.06, fps), "00:01:00:00")

    def test_5994_uses_four_frame_drop_at_ten_minute_boundary(self):
        self.assertEqual(_smpte_tc(600.0, 60000 / 1001), "00:10:00;00")


class EdlRegressionTests(unittest.TestCase):
    def test_30fps_edl_is_byte_for_byte_compatible(self):
        clips = [
            {"index": 2, "time_start": 3661.5, "time_end": 3662.0, "score": 87.6},
        ]
        expected = (
            "TITLE: Regression\n"
            "FCM: NON-DROP FRAME\n"
            "\n"
            "001  001      V     C        "
            "01:01:01:15 01:01:02:00 01:01:01:15 01:01:02:00\n"
            "* FROM CLIP NAME: Clip #2 (score: 88)\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "markers.edl"
            render_edl(clips, output_path, "Regression", fps=30.0)
            actual = output_path.read_text(encoding="utf-8")

        self.assertEqual(actual, expected)

    def test_drop_frame_edl_header_and_separator(self):
        clips = [{"index": 1, "time_start": 600.0, "time_end": 601.0, "score": 50.0}]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "markers.edl"
            render_edl(clips, output_path, fps=30000 / 1001)
            actual = output_path.read_text(encoding="utf-8")

        self.assertIn("FCM: DROP FRAME", actual)
        self.assertIn("00:10:00;00", actual)


class MediaFpsProbeTests(unittest.TestCase):
    def test_fractional_ffprobe_rate_is_parsed(self):
        completed = SimpleNamespace(stdout="30000/1001\n")
        source = Path("video.mp4")

        with patch.object(subprocess, "run", return_value=completed) as run:
            fps = pipeline._get_media_fps(source)

        self.assertAlmostEqual(fps, 30000 / 1001)
        command = run.call_args.args[0]
        self.assertIn("stream=r_frame_rate", command)
        self.assertIn("v:0", command)

    def test_ffprobe_failure_falls_back_to_30_and_warns(self):
        output = io.StringIO()

        with patch.object(subprocess, "run", side_effect=FileNotFoundError("ffprobe")), \
                redirect_stdout(output):
            fps = pipeline._get_media_fps(Path("missing.mp4"))

        self.assertEqual(fps, 30.0)
        self.assertIn("[Pipeline] 警告：ffprobe 無法取得媒體 fps", output.getvalue())
        self.assertIn("改用 30.0 fps", output.getvalue())


if __name__ == "__main__":
    unittest.main()
