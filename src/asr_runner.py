"""ASR Runner — 從 StreamClip-Tool poc.py 抽取的語音辨識管線."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from opencc import OpenCC

from .schema import AsrData, Segment, Events, Score, ScoreBreakdown, MergeInfo

_cc = OpenCC("s2twp")  # 簡體 → 台灣正體（含詞彙轉換）


def to_traditional(text: str) -> str:
    """簡體中文 → 台灣正體（ASR 輸出常為簡體）."""
    return _cc.convert(text)


def extract_audio(video_path: Path, out_wav: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(out_wav),
    ]
    print(f"[ASR] 抽音訊 → {out_wav.name}")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def transcribe(wav_path: Path, model_size: str, language: str, device: str,
               cache_path: Optional[Path] = None) -> list[dict]:
    from faster_whisper import WhisperModel

    print(f"[ASR] 載入模型 {model_size} (device={device})...")
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"[ASR] 開始辨識...")
    t0 = time.time()
    segments, info = model.transcribe(
        str(wav_path),
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    result = []
    for seg in segments:
        result.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "no_speech_prob": getattr(seg, "no_speech_prob", 0.0),
            "language": language,
        })

    elapsed = time.time() - t0
    duration = info.duration
    print(f"[ASR] 完成：{len(result)} 段, 音訊 {duration:.0f}s, 耗時 {elapsed:.0f}s")

    if cache_path:
        cache_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[ASR] 快取 → {cache_path}")

    try:
        del model
    except Exception:
        pass

    return result


def detect_volume_peaks(
    wav_path: Path,
    window_sec: float = 1.0,
    threshold_db_above_baseline: float = 6.0,
    merge_gap_sec: float = 2.0,
) -> list[dict]:
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
        seen_ranges = {(int(p["start"] / window_sec), int(p["end"] / window_sec))
                       for p in peaks}
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


def detect_silence_bursts(raw_segments: list[dict], gap_sec: float = 3.0) -> list[dict]:
    if len(raw_segments) < 2:
        return []
    sorted_segs = sorted(raw_segments, key=lambda s: s["start"])
    bursts = []
    for i in range(1, len(sorted_segs)):
        prev = sorted_segs[i - 1]
        curr = sorted_segs[i]
        gap = curr["start"] - prev["end"]
        if gap < gap_sec:
            continue
        text = curr["text"].strip()
        duration = curr["end"] - curr["start"]
        is_large_gap = gap >= 8.0
        if not is_large_gap and (len(text) < 6 or duration < 1.5):
            continue
        bursts.append({
            "start": curr["start"],
            "end": curr["end"],
            "gap_before_sec": round(gap, 2),
        })
    return bursts


def _guess_speaker(text: str, language: str, duration: float,
                   no_speech_prob: float, lang_conf_threshold: float,
                   short_sec: float) -> str:
    confidence = 1.0 - no_speech_prob
    if duration < short_sec and confidence < lang_conf_threshold:
        return "unknown"
    if language == "zh":
        return "streamer"
    if language == "ja":
        return "game_voice"
    return "unknown"


def _detect_laughter(text: str) -> bool:
    markers = ["www", "ｗｗ", "草", "笑", "hhh", "ww"]
    t = text.lower()
    return any(m in t for m in markers)


def detect_repeated_words(raw_segments: list[dict]) -> dict[float, float]:
    """重複詞偵測：回傳 {start_time: score}.

    三層偵測（移植自 StreamClip-Tool）：
    1. 連續單字重複 3+（哈哈哈、對對對）
    2. 連續雙字重複 2+（不要不要、好吃好吃）
    3. 非連續 2-gram 出現 3+ 次
    """
    stopchars = set("的了是在不我你他她它們有這那個都也就要會可以，。！？、…～．·. ")
    scores: dict[float, float] = {}

    for seg in raw_segments:
        text = seg["text"].strip()
        if len(text) < 6:
            continue

        found = []

        # 1. 連續單字重複
        for m in re.finditer(r"(.)\1{2,}", text):
            if m.group(1) in stopchars:
                continue
            found.append(len(m.group(0)) * 3)

        # 2. 連續雙字重複
        for m in re.finditer(r"(.{2})\1{1,}", text):
            if len(set(m.group(1))) <= 1:
                continue
            count = len(m.group(0)) // len(m.group(1))
            if count >= 2:
                found.append(count * 5)

        # 3. 非連續 2-gram
        if len(text) >= 10:
            ngrams: dict[str, int] = {}
            for i in range(len(text) - 1):
                gram = text[i:i + 2]
                if any(c in stopchars for c in gram):
                    continue
                ngrams[gram] = ngrams.get(gram, 0) + 1
            for _word, count in ngrams.items():
                if count >= 3:
                    found.append(count * 4)

        if found:
            scores[seg["start"]] = float(max(found))

    if scores:
        print(f"[ASR] 重複詞命中: {len(scores)} 段")
    return scores


def detect_speech_rate_changes(
    raw_segments: list[dict],
    z_threshold: float = 2.0,
    min_chars: int = 6,
) -> dict[float, float]:
    """語速突變偵測：回傳 {start_time: score}.

    每段字/秒 vs 全場平均，偏離超過 z_threshold 標準差。
    """
    rates: list[tuple[dict, float]] = []
    for seg in raw_segments:
        text = seg["text"].strip()
        duration = seg["end"] - seg["start"]
        if duration < 0.5 or len(text) < min_chars:
            continue
        rates.append((seg, len(text) / duration))

    if len(rates) < 10:
        return {}

    all_rates = np.array([r for _, r in rates])
    mean_rate = float(np.mean(all_rates))
    std_rate = float(np.std(all_rates))

    if std_rate < 0.5:
        return {}

    scores: dict[float, float] = {}
    for seg, rate in rates:
        z = abs((rate - mean_rate) / std_rate)
        if z >= z_threshold:
            scores[seg["start"]] = round(z * 5, 1)

    if scores:
        print(f"[ASR] 語速突變: {len(scores)} 段 (均速 {mean_rate:.1f} 字/秒)")
    return scores


def score_keywords_weighted(
    raw_segments: list[dict],
    keywords: list[str],
) -> dict[float, float]:
    """加權關鍵字評分：回傳 {start_time: score}.

    同一 keyword 出現多次 → 乘以次數（移植自 StreamClip-Tool）。
    """
    if not keywords:
        return {}

    scores: dict[float, float] = {}
    for seg in raw_segments:
        text = seg["text"].strip()
        seg_score = 0.0
        for kw in keywords:
            count = text.count(kw)
            if count > 0:
                seg_score += count * 10.0  # 每次命中 10 分
        if seg_score > 0:
            scores[seg["start"]] = seg_score

    if scores:
        print(f"[ASR] 關鍵字加權命中: {len(scores)} 段")
    return scores


def run_asr(video_path: Path, config: dict, output_dir: Path) -> list[Segment]:
    """執行完整 ASR 管線，回傳 Segment 列表."""
    asr_cfg = config.get("asr", {})
    model_size = asr_cfg.get("model_size", "medium")
    device = asr_cfg.get("device", "auto")
    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    channel = config.get("channel", {})
    language = channel.get("default_language", "zh")
    min_seg_sec = asr_cfg.get("min_segment_sec", 0.5)
    short_sec = asr_cfg.get("short_utterance_sec", 2.0)
    lang_conf = asr_cfg.get("language_confidence_threshold", 0.7)

    keywords_cfg = config.get("keywords", {})
    reaction_kw = keywords_cfg.get("reaction", [])
    highlight_cfg = config.get("highlight", {})
    weights = highlight_cfg.get("weights", {})

    wav_path = output_dir / "audio.wav"
    if not wav_path.exists():
        extract_audio(video_path, wav_path)
    else:
        print(f"[ASR] 沿用既有音訊 {wav_path.name}")

    cache_path = output_dir / "asr_cache.json"
    if cache_path.exists():
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"[ASR] 沿用快取 ({len(raw)} 段)")
    else:
        raw = transcribe(wav_path, model_size, language, device, cache_path)

    volume_peaks = detect_volume_peaks(wav_path)
    peak_times = set()
    for p in volume_peaks:
        for t in range(int(p["start"]), int(p["end"]) + 1):
            peak_times.add(t)

    silence_bursts = detect_silence_bursts(raw)
    burst_starts = {round(b["start"], 1) for b in silence_bursts}

    # Phase 3 補完：重複詞 + 語速突變 + 加權關鍵字
    repeat_scores = detect_repeated_words(raw)
    speech_rate_scores = detect_speech_rate_changes(raw)
    keyword_scores = score_keywords_weighted(raw, reaction_kw)

    segments: list[Segment] = []
    for r in raw:
        duration = r["end"] - r["start"]
        if duration < min_seg_sec:
            continue

        text = r["text"].strip()
        if not text:
            continue

        # OpenCC 繁簡轉換（ASR 輸出常為簡體）
        if language == "zh":
            text = to_traditional(text)

        no_speech = r.get("no_speech_prob", 0.0)
        lang = r.get("language", language)
        speaker = _guess_speaker(text, lang, duration, no_speech, lang_conf, short_sec)

        has_volume = any(int(r["start"]) <= t <= int(r["end"]) for t in peak_times)
        has_laughter = _detect_laughter(text)
        has_burst = round(r["start"], 1) in burst_starts

        # 加權關鍵字分數（取代 boolean）
        kw_score = keyword_scores.get(r["start"], 0)
        has_keyword = kw_score > 0
        kw_weighted = min(kw_score, weights.get("keyword_hit", 20))  # 封頂

        is_reaction = has_volume or has_laughter or has_keyword

        bd = ScoreBreakdown(
            volume_spike=weights.get("volume_spike", 15) if has_volume else 0,
            laughter=weights.get("laughter", 20) if has_laughter else 0,
            keyword_hit=kw_weighted,
            silence_then_burst=weights.get("silence_then_burst", 10) if has_burst else 0,
            repeated_word=min(repeat_scores.get(r["start"], 0), weights.get("repeated_word", 5) * 3),
            speech_rate_change=min(speech_rate_scores.get(r["start"], 0), weights.get("speech_rate_change", 5) * 3),
            streamer_reaction=0,
        )
        total = (bd.volume_spike + bd.laughter + bd.keyword_hit +
                 bd.silence_then_burst + bd.repeated_word + bd.speech_rate_change)

        seg = Segment(
            time_start=r["start"],
            time_end=r["end"],
            asr=AsrData(
                text=text,
                speaker_guess=speaker,
                language=lang,
                confidence=round(1.0 - no_speech, 3),
            ),
            events=Events(streamer_reaction=is_reaction and speaker == "streamer"),
            score=Score(total=total, breakdown=bd),
            merge=MergeInfo(source_type="asr_only", match_status="unverified"),
        )
        segments.append(seg)

    print(f"[ASR] 產出 {len(segments)} 段 Segment")
    return segments
