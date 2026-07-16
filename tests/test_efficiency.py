import json
import subprocess
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from src import asr_runner, clipper
from src.schema import Score, Segment


def detect_volume_peaks_full_load(
    wav_path: Path,
    window_sec: float = 1.0,
    threshold_db_above_baseline: float = 6.0,
    merge_gap_sec: float = 2.0,
) -> list[dict]:
    """Reference implementation matching the pre-streaming algorithm."""
    audio, sr = sf.read(str(wav_path))
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    win = int(sr * window_sec)
    n_win = len(audio) // win
    rms = np.array([
        np.sqrt(np.mean(audio[i * win:(i + 1) * win] ** 2))
        for i in range(n_win)
    ])
    rms_db = 20 * np.log10(rms + 1e-10)

    baseline = float(np.median(rms_db))
    threshold = baseline + threshold_db_above_baseline
    is_peak = rms_db >= threshold

    peaks = []
    i = 0
    merge_gap_win = int(merge_gap_sec / window_sec)
    while i < n_win:
        if not is_peak[i]:
            i += 1
            continue
        start = i
        end = i
        j = i + 1
        while j < n_win:
            if is_peak[j]:
                end = j
                j += 1
            elif j - end <= merge_gap_win:
                j += 1
            else:
                break
        peak_db = float(rms_db[start:end + 1].max())
        peaks.append({
            "start": start * window_sec,
            "end": (end + 1) * window_sec,
            "peak_db": peak_db,
            "db_above_baseline": peak_db - baseline,
        })
        i = j

    if len(peaks) < 10:
        top_idx = np.argsort(rms_db)[-20:][::-1]
        seen_ranges = {
            (int(p["start"] / window_sec), int(p["end"] / window_sec))
            for p in peaks
        }
        for idx in sorted(top_idx):
            if any(s <= idx <= e for s, e in seen_ranges):
                continue
            peaks.append({
                "start": float(idx * window_sec),
                "end": float((idx + 1) * window_sec),
                "peak_db": float(rms_db[idx]),
                "db_above_baseline": float(rms_db[idx] - baseline),
            })
        peaks.sort(key=lambda p: p["start"])

    return peaks


class VolumePeakStreamingTests(unittest.TestCase):
    def test_streaming_matches_full_load_result_item_by_item(self):
        sample_rate = 1000
        window_sec = 0.25
        window_frames = int(sample_rate * window_sec)
        amplitudes = np.array([
            0.02, 0.03, 0.04, 0.40, 0.03, 0.02, 0.55, 0.02,
            0.03, 0.04, 0.02, 0.65, 0.03, 0.02, 0.04, 0.02,
            0.50, 0.03, 0.02, 0.04, 0.03, 0.60, 0.02, 0.03,
            0.04, 0.02, 0.45, 0.03, 0.02, 0.04, 0.03, 0.02,
        ])
        phase = np.arange(window_frames) / sample_rate
        windows = [
            amplitude * np.sin(2 * np.pi * 40 * phase)
            for amplitude in amplitudes
        ]
        mono = np.concatenate(windows + [np.full(window_frames // 2, 0.9)])
        stereo = np.column_stack((mono, mono * 0.75))

        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "synthetic.wav"
            sf.write(wav_path, stereo, sample_rate, subtype="FLOAT")
            expected = detect_volume_peaks_full_load(
                wav_path,
                window_sec=window_sec,
                threshold_db_above_baseline=6.0,
                merge_gap_sec=0.5,
            )
            with patch.object(
                asr_runner.sf,
                "read",
                side_effect=AssertionError("streaming path must not call sf.read"),
            ):
                actual = asr_runner.detect_volume_peaks(
                    wav_path,
                    window_sec=window_sec,
                    threshold_db_above_baseline=6.0,
                    merge_gap_sec=0.5,
                )

        self.assertEqual(actual, expected)


class ParallelClipRenderingTests(unittest.TestCase):
    def test_worker_limit_partial_counts_and_manifest_order(self):
        active = 0
        max_active = 0
        lock = threading.Lock()
        first_pair = threading.Barrier(2)
        release_first = threading.Event()
        completion_order: list[str] = []

        def run_ffmpeg(cmd, **_kwargs):
            nonlocal active, max_active
            clip_path = Path(cmd[-1])
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                if clip_path.name.startswith(("clip_001_", "clip_002_")):
                    first_pair.wait(timeout=2)
                if clip_path.name.startswith("clip_001_"):
                    if not release_first.wait(timeout=2):
                        raise RuntimeError("later clips did not finish")
                elif clip_path.name.startswith("clip_002_"):
                    raise subprocess.CalledProcessError(
                        1, cmd, stderr=b"mock clip 2 failure",
                    )

                clip_path.write_bytes(b"clip")
                completion_order.append(clip_path.name)
                if clip_path.name.startswith("clip_004_"):
                    release_first.set()
                return subprocess.CompletedProcess(cmd, 0)
            finally:
                with lock:
                    active -= 1

        segments = [
            Segment(time_start=start, time_end=start + 1, score=Score(total=20 + i))
            for i, start in enumerate((10.0, 30.0, 50.0, 70.0))
        ]
        config = {
            "highlight": {
                "min_score": 15,
                "clip_padding_sec": 0,
                "clip_merge_gap_sec": 0,
                "min_clip_sec": 1,
                "max_clip_sec": 30,
                "render_workers": 2,
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "video.mp4"
            source.write_bytes(b"video")
            output_dir = root / "output"
            report = {}

            with patch.object(
                clipper.shutil, "which", return_value="ffmpeg",
            ), patch.object(
                clipper, "_probe_duration", return_value=100.0,
            ), patch.object(
                clipper.subprocess, "run", side_effect=run_ffmpeg,
            ), redirect_stdout(StringIO()):
                results = clipper.extract_clips(
                    source,
                    segments,
                    output_dir,
                    config,
                    vertical=True,
                    stage_report=report,
                )

            manifest = json.loads(
                (output_dir / "clips_manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(max_active, 2)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["attempted_count"], 4)
        self.assertEqual(report["success_count"], 3)
        self.assertEqual(report["failed_count"], 1)
        self.assertIn("mock clip 2 failure", report["error"])
        self.assertEqual([result["index"] for result in results], [1, 3, 4])
        self.assertEqual(
            [clip["filename"] for clip in manifest["clips"]],
            [result["filename"] for result in results],
        )
        self.assertTrue(completion_order[0].startswith("clip_003_"))
        self.assertTrue(completion_order[-1].startswith("clip_001_"))


if __name__ == "__main__":
    unittest.main()
