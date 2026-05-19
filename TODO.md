# VN-Transcribe TODO

> 最後更新：2026-05-17

## MVP（Phase 0）— ASR + Chat Log — DONE

### 基礎建設
- [x] 建立 `src/` 目錄結構（pipeline, schema, align, renderers）
- [x] 定義 `schema.py`：Segment dataclass + JSON 驗證
- [x] 建立 `config/channel.yaml` 範本
- [x] 寫 `run.py` CLI 入口（Typer）
- [x] 寫 `requirements.txt`

### ASR 管線
- [x] 從 StreamClip `poc.py` 抽出核心 ASR 函式
- [x] 寫 `asr_runner.py`：呼叫 ASR → 輸出 Schema 格式
- [x] 實作 `speaker_guess` 語言 proxy 判斷
- [x] 處理短句 < 2 秒 + 低信心 → unknown
- [x] 音量峰值偵測（`detect_volume_peaks`）
- [x] 靜默爆發偵測（`detect_silence_bursts`）

### Chat Log 管線
- [x] 寫 `chat_runner.py`：video_id → liveChatMessages.list → 聚合
- [x] 實作 spike 偵測（baseline density × threshold）
- [x] 實作訊息保留策略（superchat 優先、普通訊息取前 N 則）
- [x] 處理 API 不可用時的 graceful fallback（chat = null）

### 對齊 + 合併
- [x] 寫 `align.py` MVP 版：ASR 骨架 + Chat 疊加
- [x] 無 ASR 時段有 chat spike → 產生 event_only segment
- [x] 組裝 `pipeline.py`：串接 ASR → Chat → align → render

### 輸出
- [x] 寫 `renderers/index.py` → `index.md`
- [x] 寫 `renderers/excel.py` → `transcript.xlsx`
- [x] timeline.json 直接由 pipeline 輸出

---

## Phase 1 — OCR 整合 + 搜尋 — DONE

### OCR 適配
- [x] 套用 OCR Segment Duration 規則（default 4s / max 12s）
- [x] 寫 `ocr_runner.py`：包裝 MangaOCR，headless 模式

### 三層對齊
- [x] `align.py` 升級：加入 OCR overlap matching（`align_full`）
- [x] 實作 match_status 判斷（consistent / conflict / readback_possible）

### 搜尋 + 衝突
- [x] 寫 `search.py` CLI（character / keyword / reaction / chapter / conflict / superchat）
- [x] 寫 `renderers/conflict.py` → 衝突報告 + 自動建議

---

## Phase 2 — SRT 字幕 — DONE

- [x] `renderers/subtitle.py` → SRT 生成
  - [x] 日文原文軌（OCR 優先、fallback ASR game_voice）
  - [x] 實況主語音軌（streamer / mixed）
  - [x] 雙軌合併（上行原文、下行實況主）
- [x] UTF-8 BOM 編碼（VLC / MPV / PotPlayer 相容）
- [x] 整數毫秒時間戳運算（避免浮點誤差 ms=1000）
- [ ] 翻譯草稿（Claude API，選配，不急）

---

## Phase 3 — 智慧標記 + 自動剪輯 — DONE

### 場景分類
- [x] 寫 `classifier.py`：rule-based 六類分類
  - [x] dialogue / narration / choice / transition / reaction / silence
- [x] `classify_all()` 零成本批次分類

### 精彩片段剪輯
- [x] 寫 `clipper.py`：select_highlights + FFmpeg 切片
- [x] 時間區間合併（`_merge_intervals`）
- [x] `render_clips_index()` → clips_index.md

### 統計與標記
- [x] 寫 `renderers/stats.py`：角色出場統計 + 場景分佈 + 時間概覽
- [x] 寫 `renderers/markers.py`：EDL + MPV chapters

---

## StreamClip-Tool 功能移植 — DONE

- [x] OpenCC 繁簡轉換整合（`s2twp`，ASR 中文自動轉正體）
- [x] 重複詞偵測三層演算法（連續單字 ×3+ / 連續雙字 ×2+ / 散佈 2-gram ×3+）
- [x] 語速突變偵測（z-score，chars/sec vs 全場均值）
- [x] 加權關鍵字評分（count × 10，取代 boolean）
- [x] CMX 3600 EDL 標記輸出（Premiere / DaVinci / FCPX）
- [x] MPV chapter file 輸出
- [x] SRT 時間戳改為整數毫秒運算（修正浮點 bug）

---

## 待辦（未排期）

### 功能
- [ ] 翻譯草稿（Claude API / 本地模型，Phase 2 選配）
- [x] Web UI — Vite + React + TS 前端（DONE 2026-05-17）
- [ ] Web UI 接真實 API（目前跑 mock data）
- [ ] YouTube 章節格式輸出（`00:00 開場` 純文字）
- [ ] `.env` 管理 API key（目前 channel.yaml 直接設定）

### 測試
- [ ] 真實影片端對端測試
- [ ] YouTube Data API 實測（需 API key）
- [ ] OCR + ASR 三層對齊實測

### 品質
- [ ] search.py 回應速度 benchmark（目標 < 1 秒）
- [ ] 場景分類準確率人工抽查
- [ ] 衝突報告自動建議準確率
