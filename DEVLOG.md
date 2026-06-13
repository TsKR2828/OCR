# VN-Transcribe 開發日誌

---

## 2026-06-13 — Phase 4 快速自動剪片流程優化（Dynamic Workflow）

### 一句話
GPU 辨識瓶頸解除後，把「辨識 → 精彩定位 → 切片 → 燒字幕」串成一條龍。`quick_clip.py` 一條指令從影片產出可直接發的直式燒字幕短影音 + 精選合輯，三條驗收標準全過。

### 做了什麼（Opus 規劃+寫碼+審查 / Sonnet 跑 GATE 驗證，runbook 見 `D:\VN-Transcribe-test\QUICKCLIP-WORKFLOW.md`）

**A. 精彩定位 — 補回最重訊號**
- `src/chat_ytdlp.py`（新）：yt-dlp `--write-subs --sub-langs live_chat` 下載 `.live_chat.json`，解析 YouTube replay renderer（一般/superchat/sticker/membership），offset 直接取 `videoOffsetTimeMsec`（免回推 stream_start）。
- `chat_runner.run_chat` 加 yt-dlp 來源分支（優先於 Data API），`aggregate_chat` 加「已有 offset_sec 不重算」guard。
- 中文 reaction 關鍵字併入 `channel.yaml`。

**B. 切片品質 — 修 `-c copy` 的坑（clipper.py）**
- `_list_keyframes`：ffprobe packet flags（demux-only 不解碼），切點吸附 ≤start 最近 keyframe → 開頭不黑。
- `_clamp_duration`：min/max 長度夾制（太短對稱外擴、太長從頭截）。

**C. 短影音適配（clipper.py）**
- `slice_srt` + ffmpeg `subtitles=` 燒字幕（重編碼）；Windows 路徑用 cwd+純檔名避 libass 跳脫地獄；CJK 用 Microsoft JhengHei。
- `_vertical_filter`：blur-pad（模糊鋪底保全畫面）/ crop（置中裁切）→ 9:16。
- `render_highlight_reel`：top-N concat 成精選合輯。

**D. 一鍵化**
- `quick_clip.py`：薄 wrapper，預設直式+燒字幕+合輯；`--fast` 橫式快切；`--chat-url` 補 chat 訊號。
- 根目錄 `README.md`（含 GPU 配方）。

### 關鍵發現：spike 雙閘門（Opus 審查抓出）
GATE 1 拉活俠傳真實 live_chat（298 則）跑聚合，Sonnet 回報「PASS」但 Opus 一看數字不對：**243 非空窗口全部是 spike**。根因：稀疏聊天室 baseline 被大量空窗拉低（~1.7/min），10s 窗口任何單則訊息密度就 6/min > baseline×2.5 → 每個非空窗都誤判 spike，weight-25 訊號等於攤平失效。
修法：`is_spike` 改雙閘門＝相對（density > baseline×threshold）**AND** 絕對（count ≥ `min_spike_messages`，預設 3）。活俠傳 243 → 7 個有意義 spike。

### GATE 驗證（Sonnet 執行，Opus 判定）
| GATE | 內容 | 結果 |
|------|------|------|
| 1 | 活俠傳真實 live_chat 解析+聚合 | 298 則（含 SC NT$15/membership）、offset 對齊 3hr、修正後 7 spike ✅ |
| 2 | 雜談 timeline+影片切片品質 | 5 copy clip 夾制內+首幀亮度 122、3 直式 1080×1920 燒字幕、合輯時長相符 ✅ |
| 3 | quick_clip 端對端 3min 樣本 | GPU large-v3 60 段 17s → 5 個直式燒字幕 clip + 114s 合輯 ✅ |

Opus 另抽燒字幕直式幀目視：CJK（正黑體）渲染正常、blur-pad 構圖正確、字幕底置中可讀，非 tofu。

### 動到的檔案
`src/chat_ytdlp.py`(新) `quick_clip.py`(新) `README.md`(新) `src/chat_runner.py` `src/clipper.py` `src/pipeline.py` `run.py` `config/channel.yaml`

---

## 2026-06-13 — GPU 修復 + large-v3 真實影片端對端達標

### 背景
拿月上零韻三部實況（活俠傳 3hr 中文遊戲 / 大富翁 1.9hr / 雜談 1.25hr）做真實影片端對端測試。
先用活俠傳跑 MVP，意外揪出兩個問題：GPU 根本沒生效 + 語言 proxy 在中文遊戲失效。

### 問題 1：GPU 沒被用到（torch 裝成 CPU build）
- 症狀：3hr 影片 ASR 跑了 8958s（CPU medium，RTF 0.83）
- 根因：環境是 `torch 2.11.0+cpu`，`asr_runner.py:316` 的 `torch.cuda.is_available()` 永遠 False → 退回 CPU 分支
- 硬體其實沒問題：RTX 3060 Ti 8GB + driver 560.94（支援 CUDA 12.6）

### 修復流程（Opus 規劃／Sonnet 執行的 dynamic workflow，runbook 見 D:\VN-Transcribe-test\WORKFLOW.md）

| Phase | 動作 | 結果 |
|-------|------|------|
| A | torch `+cpu` → `2.11.0+cu126` | `cuda.is_available()` = True |
| A | 驗證 CTranslate2 在 GPU 載入模型 | 一次過，未踩 cuDNN DLL 坑 |
| B | config 改 `large-v3` + GPU 跑 | 短測 5min → 12s（RTF 0.04） |
| C | 雜談 74min 全片 + 抽樣驗收 | 字準估 92–95%，月月判定達標 |

**關鍵坑**：CTranslate2 4.7.1 需要 cuDNN 9，但 torch 2.11 自帶——只要**先 `import torch` 再 import faster_whisper**，CTranslate2 就找得到 DLL，**不必**另裝 `nvidia-cudnn-cu12`/`nvidia-cublas-cu12`。

### 效能躍進

| | 修復前 | 修復後 |
|---|---|---|
| 算力 | CPU | GPU RTX 3060 Ti |
| 模型 | medium | large-v3 |
| RTF | 0.83 | 0.04~0.12 |
| 3hr 影片 | 2.5 小時 | 數分鐘 |

### large-v3 中文選字品質
同句開場白為證：medium 辨成「進入奇幻的**塑造**世界」→ large-v3「進入奇幻的**書中**世界」✅（靠上下文選對同音字）。
雜談全片 1484 段：日文殘留僅 0.1%、與前段完全重複 2.1%。

### 問題 2：語言 proxy 在中文遊戲失效（實證）
活俠傳是中文遊戲，遊戲台詞與實況主配音都是中文 → `speaker_guess` 全判 `streamer`、scene 全判 `reaction`、零 `game_voice`。
**結論**：語言 proxy 只在「日文遊戲 + 中文實況主」成立；中文遊戲要分「遊戲台詞 vs 實況閒聊」只能靠 OCR 當錨點，ASR 單層做不到。此為既有設計決策「用語言 proxy、不做 diarization」的適用邊界補充。

### 產物
- 測試資產 `D:\VN-Transcribe-test\`：WORKFLOW.md（runbook）+ config_largev3.yaml + output_v3（雜談 timeline + SRT）
- GPU 修復配方已寫入 memory（`reference-gpu-whisper`），其他本機 faster-whisper 專案可複用
- 待辦：把 large-v3 設為專案預設 config（見 TODO.md）

---

## 2026-05-23 — 黑星劇場 OCR 品質修正 + 影片分類

### 問題診斷

黑星劇場 1134 支 Bilibili 影片跑 OCR pipeline 後，對白辨識率 ~10%。
花一整個 session 做分層排查：

| 測試 | 結果 | 結論 |
|------|------|------|
| CLAHE + 銳化 + 放大 | 角色名改善、對白仍亂 | 不夠 |
| Otsu 二值化 | 角色名崩壞、對白仍亂 | 金字灰度偏中，Otsu 吃掉 |
| 高閾值 190 二值化 | 對白仍亂 | 背景噪點殘留 |
| **單行 crop（去右側 35%）** | **對白 ~80% 正確** | **根因是右側人物透出** |

GPT-5.5 給出關鍵建議：不要過早歸因模型，先做「單行乾淨 crop 最小驗證」。
驗證結果證實 MangaOCR 本身沒問題，瓶頸是 dialogue ROI 右側 ~35% 有角色立繪透出造成幻覺。

### 修改檔案

**`src/ocr_runner.py`**
- 新增 `_preprocess_dialogue()`：高閾值 190 二值化 + 反轉 + morphological close + 放大
- 新增 `_preprocess_name()`：CLAHE + 銳化 + 放大（金字不適合二值化）
- 新增 `_upscale()` 共用函式
- `_ocr_image()` 加 `roi_type` 參數，自動選前處理策略
- `_process_video_headless()` 加 `dialogue_text_ratio` 參數，OCR 前裁掉右側噪點
- `run_ocr()` 從 config 讀取 `dialogue_text_ratio` 並傳遞

**`config/blackstar.yaml`**
- 新增 `ocr.dialogue_text_ratio: 0.65`

### 品質對比（測試影片 S3ch01 p06）

| 指標 | 修正前 | 修正後 |
|------|--------|--------|
| Name exact | 11 | 17 |
| Name unfixed | 6 | 5 |
| 對白正確率 | ~10% | ~80% |
| 代表句 | 「よし、金融まではなく」 | 「よぉし、全員集まってんな？」✅ |

### 影片分類

- 執行 `organize_videos.py --execute`
- 1134 MP4 + 1133 info.json → 121 資料夾
- 結構：`videos/主線/S3~S7/chXX_標題/`、`videos/季節/2020~2026/活動名/`、`videos/季節/周年/`
- 根目錄另有 1128 支重複 MP4（3 位前綴，與 videos/ 的 4 位前綴版本相同），待使用者手動刪除

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
