import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from src import chat_ytdlp


def _chat_entry(text: str, replay_time: dict | None = None, **entry_time) -> dict:
    replay = {
        "actions": [
            {
                "addChatItemAction": {
                    "item": {
                        "liveChatTextMessageRenderer": {
                            "authorName": {"simpleText": "viewer"},
                            "message": {"runs": [{"text": text}]},
                        }
                    }
                }
            }
        ]
    }
    replay.update(replay_time or {})
    return {"replayChatItemAction": replay, **entry_time}


def _write_jsonl(path: Path, records: list[dict | str]) -> None:
    lines = [record if isinstance(record, str) else json.dumps(record) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ChatYtdlpRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "chat": {
                "enabled": True,
                "aggregate_window_sec": 10.0,
                "spike_threshold": 2.0,
                "max_messages_per_segment": 5,
                "min_spike_messages": 3,
            },
            "keywords": {"reaction": ["哈哈"]},
        }

    def test_corrupt_lines_are_counted_warned_and_mark_stage_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chat_path = root / "mixed.live_chat.json"
            _write_jsonl(
                chat_path,
                [
                    _chat_entry("正常一", {"videoOffsetTimeMsec": "1000"}),
                    "{broken json",
                    _chat_entry("缺時間"),
                    _chat_entry("正常二", {"videoOffsetTimeMsec": "12000"}),
                ],
            )
            report: dict = {}
            output = io.StringIO()

            with redirect_stdout(output), chat_ytdlp.chat_stage_report(report):
                windows = chat_ytdlp.run_chat_ytdlp(
                    str(chat_path), self.config, root, total_duration_sec=30.0
                )
                # Simulate chat_runner's success update after the backend returns.
                report["status"] = "success"

        self.assertIn("[Chat] 警告：跳過 2 行無法解析的 chat 記錄", output.getvalue())
        self.assertEqual(sum(w["message_count"] for w in windows if w), 2)
        self.assertEqual(report["message_count"], 2)
        self.assertEqual(report["skipped_count"], 2)
        self.assertEqual(report["chat_line_count"], 4)
        self.assertEqual(report["corruption_rate"], 0.5)
        self.assertEqual(report["time_sources"], {"video_offset_msec": 2})
        self.assertEqual(report["status"], "partial")
        self.assertIn("跳過 2/4 行", report["reason"])

    def test_mixed_time_formats_are_kept_with_numeric_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            chat_path = Path(tmp) / "times.live_chat.json"
            _write_jsonl(
                chat_path,
                [
                    _chat_entry("數字", {"time_in_seconds": 12.5}),
                    _chat_entry("文字", {"time_text": "00:34"}),
                    _chat_entry(
                        "兩者都有",
                        {"time_text": "00:50"},
                        timestamp=44,
                    ),
                ],
            )
            stats: dict = {}

            messages = chat_ytdlp.parse_live_chat(chat_path, stats=stats)

        self.assertEqual([m["text"] for m in messages], ["數字", "文字", "兩者都有"])
        self.assertEqual([m["offset_sec"] for m in messages], [12.5, 34.0, 44.0])
        self.assertEqual(stats["skipped_count"], 0)
        self.assertEqual(
            stats["time_sources"],
            {"numeric_seconds": 2, "time_text": 1},
        )

    def test_normal_ytdlp_format_keeps_existing_windows_and_spike_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chat_path = root / "normal.live_chat.json"
            _write_jsonl(
                chat_path,
                [
                    _chat_entry("哈哈一", {"videoOffsetTimeMsec": "1000"}),
                    _chat_entry("一般二", {"videoOffsetTimeMsec": "2000"}),
                    _chat_entry("一般三", {"videoOffsetTimeMsec": "3000"}),
                    _chat_entry("一般四", {"videoOffsetTimeMsecText": "12000"}),
                ],
            )

            windows = chat_ytdlp.run_chat_ytdlp(
                str(chat_path), self.config, root, total_duration_sec=30.0
            )

        self.assertEqual(
            windows,
            [
                {
                    "message_count": 3,
                    "superchat_count": 0,
                    "density_per_min": 18.0,
                    "baseline_per_min": 8.0,
                    "is_spike": True,
                    "messages": [
                        {"author": "viewer", "text": "哈哈一", "type": "normal", "amount": None},
                        {"author": "viewer", "text": "一般二", "type": "normal", "amount": None},
                        {"author": "viewer", "text": "一般三", "type": "normal", "amount": None},
                    ],
                    "time_start": 0.0,
                    "time_end": 10.0,
                },
                {
                    "message_count": 1,
                    "superchat_count": 0,
                    "density_per_min": 6.0,
                    "baseline_per_min": 8.0,
                    "is_spike": False,
                    "messages": [
                        {"author": "viewer", "text": "一般四", "type": "normal", "amount": None}
                    ],
                    "time_start": 10.0,
                    "time_end": 20.0,
                },
                None,
                None,
            ],
        )


if __name__ == "__main__":
    unittest.main()
