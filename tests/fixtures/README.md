# 活俠傳評分回歸 fixture

本 fixture 只用於鎖定 VN-Transcribe 現行精彩候選評分、篩選、合併與排序語意。

## 出處

- 原始輸出目錄：`D:\VN-Transcribe-test\output_huoxia_v3\07fa2465_【活俠傳】趙活一嘴好砲，暴雷指導絕對BA`
- Raw ASR：上述目錄的 `asr_cache.json`，全檔 3885 段
- Timeline：上述目錄的 `timeline.json`，對齊後全檔 3869 段
- Chat：上述目錄的 `live_chat.live_chat.json`
- 音量來源：上述目錄的 `audio.wav`
- 設定：`D:\VN-Transcribe-test\config_huoxia.yaml`
- 擷取時間：原片 `00:00:00.0–00:15:00.0`，時間戳未重設

這個連續 15 分鐘區間含現行 timeline 中 57.2、45.0、40.0 等高分段，也包含大量 0 分平淡段。

## 檔案

- `huoxia_raw_asr.json`：範圍內完整 raw ASR，共 272 段。
- `huoxia_chat_windows.json`：前 90 個 10 秒窗口，共 3 個 spike。窗口先以全片 10723.950295 秒聚合，再擷取本區間，保留全片 baseline 語意。
- `huoxia_volume_peaks.json`：先用完整 `audio.wav` 執行現行音量偵測，再擷取與本區間重疊的 30 個 peaks。
- `huoxia_scoring_config.json`：評分、chat 與 clip 範圍計算會讀取的有效設定子集；原設定未明列的 clip 參數以現行預設值展開。
- `huoxia_fixture_meta.json`：機器可讀的來源、範圍與計數。
- `scoring_baseline.json`：現行程式產生的 golden snapshot。

Harness 路徑為 `tests/scoring_harness.py`，依序執行現有 `run_asr` 評分、`align_mvp` chat 疊加、`select_highlights`、`_merge_intervals` 與 `_clamp_duration`。ASR cache 與音量 peaks 由 fixture 注入，因此不需要 GPU、模型、ffmpeg 或網路。

## 重生成 golden

僅允許在評分語意變更已明確獲准時執行：

```powershell
python tests/scoring_harness.py --regenerate
```

一般程式修改不得藉由重生成 snapshot 掩蓋未預期的評分漂移。
