# VN-Transcribe 開發日誌

---

## 2026-05-17 — Web UI 前端建置

**技術棧：** Vite 8 + React 18 + TypeScript

依照 `DESIGN-BRIEF.md` 規格 + `uiux/` 原型（HTML prototype），完整建置 Web 前端 SPA。

### 新增目錄 `web/`

| 類型 | 檔案數 | 說明 |
|------|--------|------|
| 元件 | 9 | Icons, Sidebar, Topbar, Statusbar, Badges, SegmentCard, TimelineThumbnail, PillRow, EmptyState |
| 頁面 | 7 | Dashboard, Timeline, Search, Conflict, Clips, Stats, Settings |
| 資料 | 2 | types.ts（全域型別）、mock.ts（Mock data） |
| 樣式 | 1 | main.css（Brass Library 深色主題，1400+ 行） |
| 核心 | 2 | App.tsx（路由 + 鍵盤快捷鍵 + accent theming）、main.tsx |

### 特色

- **State-based routing**：⌘1-7 切頁，無 react-router 依賴
- **Brass Library 設計系統**：深海軍藍底 + 金色 accent + 書頁奶白文字
- **36 個 SVG 圖標**：手刻 20×20 viewBox，統一 `I.xxx` 存取
- **4 色 accent 可切換**：Gold / Brass / Copper / Verdigris
- **完整 Mock data**：角色、段落、衝突、片段、密度、聊天活動
- **Production build 通過**：266KB JS (gzip 80KB) + 27KB CSS (gzip 5KB)

### 字型

Google Fonts: Cormorant Garamond, Inter, IBM Plex Mono, Noto Serif JP, Noto Serif TC

---

## 2026-05-09 — StreamClip-Tool 功能移植

**分支：** `audit/streamclip-merge`

審查 `StreamClip-Tool/poc.py`（1230 行），識別出可移植到 VN-Transcribe 的功能模組，完成以下整合：

### 移植項目

| 來源函式 | 整合至 | 改動 |
|----------|--------|------|
| `detect_repeated_words()` | `asr_runner.py` | 三層偵測（單字連續 ×3+、雙字連續 ×2+、散佈 2-gram ×3+），分數寫入 `ScoreBreakdown.repeated_word` |
| `detect_speech_rate_changes()` | `asr_runner.py` | z-score 語速突變，填入 `ScoreBreakdown.speech_rate_change` |
| `score_keywords` → `score_keywords_weighted()` | `asr_runner.py` | 原本 boolean（命中=滿分），改為 count × 10 加權，封頂 |
| `write_markers()` | `renderers/markers.py`（新） | CMX 3600 EDL + MPV chapter file，獨立模組 |
| `write_srt()` 整數毫秒 | `renderers/subtitle.py` | SRT 時間戳改用 `int(round(seconds * 1000))` 再整除，修正潛在 ms=1000 |
| OpenCC 繁簡轉換 | `asr_runner.py` | `opencc-python-reimplemented` 已在 requirements 但未使用，現在 ASR 中文自動 `s2twp` |

### 發現的問題

- `ScoreBreakdown.repeated_word` 和 `.speech_rate_change` 定義於 schema 但從未被 populate → 已修正
- `opencc-python-reimplemented` 是死依賴（列在 requirements 但沒 import）→ 已啟用
- 關鍵字評分 boolean 打分遺失精度 → 改為加權計數

---

## 2026-05-08 — Phase 3 完工（智慧標記 + 自動剪輯）

### 新增檔案

- `src/classifier.py` — Rule-based 場景分類器
  - 6 種類型：dialogue / narration / choice / transition / reaction / silence
  - 判斷優先順序：choice_point → chapter_change → OCR+character → OCR only → streamer ASR → chat_spike → silence
  - `classify_all()` 批次分類，寫入 `Segment.scene_type`，零外部依賴

- `src/clipper.py` — 精彩片段自動剪輯
  - `select_highlights()`：min_score 過濾 + top_n 取前幾
  - `_merge_intervals()`：合併相鄰時間區間（gap < tolerance）
  - `extract_clips()`：FFmpeg `-c copy` 快速切片，前後 padding
  - `render_clips_index()`：Markdown 剪輯索引

- `src/renderers/stats.py` — 統計報告
  - 角色出場統計（台詞數、首末出場、總時長）
  - 場景類型分佈
  - 時間概覽

### 修改檔案

- `src/schema.py` — 新增 `scene_type` 欄位 + `dict_to_segment()` 處理
- `src/pipeline.py` — 加入 Classify 步驟（永遠執行）、Clips 步驟（選配）、Stats 輸出（永遠產出）
- `run.py` — 新增 `--clips` 旗標

---

## 2026-05-08 — Phase 2 完工（SRT 字幕）

### 新增檔案

- `src/renderers/subtitle.py` — 三軌 SRT 生成器
  - `render_srt_original()`：日文原文（OCR 優先 → fallback ASR game_voice）
  - `render_srt_streamer()`：實況主語音（streamer / mixed）
  - `render_srt_dual()`：雙軌合併（上行原文、下行實況主）
  - `render_all_srt()`：一次產出三種
  - UTF-8 BOM（`utf-8-sig`）確保 VLC / MPV / PotPlayer 相容
  - 整數毫秒時間戳運算避免浮點 bug

### 修改檔案

- `src/pipeline.py` — 加入 SRT 步驟（`--srt` 啟用時產出）
- `run.py` — 新增 `--srt` 旗標

### 設計決策

- 翻譯功能暫緩（API 實測最後再說）
- SRT 用 UTF-8 BOM 而非純 UTF-8，理由是日文字幕在 Windows 播放器常遇編碼問題

---

## 2026-05-08 — Phase 1 完工（OCR 整合 + 搜尋 + 衝突報告）

### 新增檔案

- `src/ocr_runner.py` — MangaOCR 包裝
  - headless 模式，pipeline 呼叫
  - OCR Segment Duration 規則（default 4s / max 12s / 下一段出現時間為 time_end）
  - pHash 變化偵測 + stable threshold

- `src/renderers/conflict.py` — OCR/ASR 衝突報告
  - 掃描 `match_status == "conflict"` 段落
  - `_suggest_resolution()` 自動建議（例如「伺」→「何」OCR 常見誤判）
  - 統計摘要

- `search.py`（頂層）— Typer CLI 搜尋工具
  - 6 個子命令：character / keyword / reaction / chapter / conflict / superchat
  - `_resolve_timeline()` 自動找最新 timeline.json
  - 每個命令載入 timeline.json 做篩選排序

### 修改檔案

- `src/align.py` — 新增 `align_full()` 三層對齊
  - OCR ↔ ASR overlap matching + edit distance 判斷
  - Chat 疊加不變
- `src/pipeline.py` — 加入 OCR 步驟 + 衝突報告（有 OCR 時才產出）
- `run.py` — 新增 `--ocr` / `--ocr-config` 旗標
- `requirements.txt` — 加入 manga-ocr / opencv-python / imagehash / Pillow

---

## 2026-05-07 — MVP（Phase 0）完工

### 新增檔案

- `src/schema.py` — Segment / AsrData / ChatData / OcrData / Events / Score / MergeInfo dataclass
- `src/asr_runner.py` — faster-whisper ASR 管線
  - 音訊抽取（FFmpeg → 16kHz mono WAV）
  - 轉錄 + 快取（asr_cache.json）
  - speaker_guess 語言 proxy（zh=streamer, ja=game_voice）
  - 音量峰值偵測 + 靜默爆發偵測
- `src/chat_runner.py` — YouTube Data API v3 chat replay
  - liveChatMessages.list 分頁拉取
  - 時間窗口聚合 + baseline density 計算
  - spike 偵測（density > baseline × threshold）
  - superchat 獨立保留
  - API 不可用時 graceful fallback
- `src/align.py` — `align_mvp()` ASR + Chat 對齊
- `src/pipeline.py` — 主流程控制
- `src/renderers/index.py` — index.md 影片導航索引
- `src/renderers/excel.py` — transcript.xlsx 逐字稿
- `run.py` — Typer CLI 入口
- `config/channel.yaml` — 頻道設定範本
- `requirements.txt`

---

## 2026-05-07 — 專案初始化

- 建立專案目錄 `VN-Transcribe/`
- 完成 ROADMAP 定稿（三層感知架構）
- MVP 範圍收斂：ASR + Chat Log → timeline.json + index.md + transcript.xlsx
- OCR 移至 Phase 1

### 設計決策

- `timeline.json` 作為中間格式名稱（取代 segments.json）
- Chat Log 作為附加層，不影響 `merge.source_type`
- Speaker 判斷用語言 proxy（中文=實況主、日文=遊戲語音），不做 diarization
- OCR segment duration 規則：以下一段出現時間為 time_end，超時用預設值
- `merge` 欄位拆成 `source_type` + `match_status` 兩個維度
