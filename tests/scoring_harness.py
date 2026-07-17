"""Offline scoring baseline harness.

Golden regeneration is allowed only when a scoring-semantics change has been
explicitly approved. Use ``python tests/scoring_harness.py --regenerate``.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import asr_runner  # noqa: E402
from src.align import align_mvp  # noqa: E402
from src.clipper import (  # noqa: E402
    _clamp_duration,
    _merge_intervals,
    select_highlights,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_PATH = FIXTURE_DIR / "scoring_baseline.json"


def _load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def generate_scoring_baseline() -> dict:
    """Run the current scoring-to-merged-candidate path without external I/O."""
    metadata = _load_json("huoxia_fixture_meta.json")
    raw_asr = _load_json("huoxia_raw_asr.json")
    chat_windows = _load_json("huoxia_chat_windows.json")
    volume_peaks = _load_json("huoxia_volume_peaks.json")
    config = _load_json("huoxia_scoring_config.json")

    runtime_config = copy.deepcopy(config)
    runtime_config.setdefault("asr", {})["device"] = "cpu"
    raw_path = FIXTURE_DIR / "huoxia_raw_asr.json"

    with patch.object(
        asr_runner, "_cache_metadata_valid", return_value=True,
    ), patch.object(
        asr_runner, "_load_valid_json_cache", return_value=raw_asr,
    ), patch.object(
        asr_runner, "detect_volume_peaks", return_value=volume_peaks,
    ), io.StringIO() as stdout, patch("sys.stdout", stdout):
        asr_segments = asr_runner.run_asr(
            raw_path, runtime_config, FIXTURE_DIR,
        )
        timeline = align_mvp(asr_segments, chat_windows, config)

    highlight = config.get("highlight", {})
    selected = select_highlights(
        timeline,
        min_score=highlight.get("min_score", 15),
        top_n=highlight.get("top_n", 30),
    )

    padding = highlight.get("clip_padding_sec", 3.0)
    merge_gap = highlight.get("clip_merge_gap_sec", 2.0)
    min_clip = highlight.get("min_clip_sec", 4.0)
    max_clip = highlight.get("max_clip_sec", 90.0)
    video_duration = float(metadata["fixture_duration_sec"])

    intervals = [
        (max(0.0, segment.time_start - padding), segment.time_end + padding)
        for segment in selected
    ]
    merged = _merge_intervals(intervals, merge_gap)
    merged = [
        _clamp_duration(start, end, min_clip, max_clip, video_duration)
        for start, end in merged
    ]

    candidates = []
    for start, end in merged:
        contributors = [
            segment for segment in selected
            if segment.time_start < end and segment.time_end > start
        ]
        winner = max(contributors, key=lambda segment: segment.score.total)
        breakdown = {
            key: round(float(value), 1)
            for key, value in asdict(winner.score.breakdown).items()
        }
        candidates.append({
            "start": round(float(start), 1),
            "end": round(float(end), 1),
            "score": round(float(winner.score.total), 1),
            "breakdown": breakdown,
        })

    candidates.sort(key=lambda item: (-item["score"], item["start"], item["end"]))
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank

    return {
        "schema_version": 1,
        "fixture": metadata["fixture_id"],
        "source_time_start": metadata["source_time_start"],
        "source_time_end": metadata["source_time_end"],
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="rewrite the golden snapshot after an approved scoring-semantics change",
    )
    args = parser.parse_args()
    if not args.regenerate:
        parser.error(
            "refusing to write golden without --regenerate; regeneration requires approval"
        )

    payload = generate_scoring_baseline()
    GOLDEN_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {GOLDEN_PATH} ({payload['candidate_count']} candidates)")


if __name__ == "__main__":
    main()
