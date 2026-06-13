# VN-Transcribe TODO

> 最後更新：2026-05-23

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

## 黑星劇場子專案 — 進行中

### OCR 前處理（DONE 2026-05-23）
- [x] 對白 ROI 前處理：高閾值 190 二值化 + 反轉 + morphological close + 放大
- [x] 角色名 ROI 前處理：CLAHE + 銳化 + 放大（金字不適合二值化）
- [x] `_ocr_image()` 加 `roi_type` 參數自動選策略
- [x] `dialogue_text_ratio` 裁切右側人物透出噪點（0.65）
- [x] 亮度閘門（brightness_mean_min / brightness_std_min）過濾無對白框畫面

### 影片分類（DONE 2026-05-23）
- [x] `organize_videos.py` 將 1134 MP4 分入 121 資料夾
- [x] 結構：`主線/S3~S7/chXX_標題/`、`季節/2020~2026/活動名/`、`季節/周年/`
- [ ] 刪除根目錄 1128 支重複 MP4（3 位前綴版本，需手動 `Remove-Item`）

### 批次處理（TODO）
- [ ] `batch_ocr.ps1` 適配新目錄結構（影片已從根目錄移至子目錄）
- [ ] `batch_ocr.ps1` 加 `$env:PYTHONIOENCODING = "utf-8"`（Windows cp950 修正）
- [ ] 跑第二支影片驗證 OCR 品質穩定度
- [ ] 全量 1134 支影片批次跑 pipeline

### 已知限制
- [ ] `dialogue_text_ratio 0.65` 是硬裁——長對白右側 35% 會被截掉，未來可改動態偵測文字邊界
- [ ] 少數畫面 OCR 仍有個別漢字誤讀（如 関示→開示）

---

## 2026-06-13 GPU 加速 + large-v3 — DONE

- [x] 診斷 GPU 未生效（torch `+cpu` build → cuda 不可用）
- [x] 換 torch `2.11.0+cu126`，`torch.cuda.is_available()` = True
- [x] 驗證 CTranslate2 在 GPU 載入（cuDNN 9 由 torch 自帶，免另裝 nvidia-cudnn-cu12）
- [x] config 改 `large-v3` + `device: auto`，GPU RTF 0.04~0.12（5min→12s）
- [x] 雜談 74min 全片端對端 + 抽樣驗收（字準估 92-95%，達標）
- [x] 文件更新（ROADMAP / DEVLOG / HANDOFF）+ memory（`reference-gpu-whisper`）
- [x] **把 large-v3 設為專案預設**（2026-06-13 完成：`config/channel.yaml` → `model_size: large-v3` + `device: auto`，YAML 載入已驗證）

---

## 快速自動剪片流程優化（Phase 4）— DONE (2026-06-13)

> **目標**：把「辨識 → 精彩定位 → 切片 → 燒字幕」串成一條龍，產出可直接用的短影音素材。守 ROADMAP 原則：產出素材、最終剪輯留給人。
> **成果**：`quick_clip.py` 一條指令從影片產出直式燒字幕 clip + 精選合輯；三條驗收標準全過（GATE 1/2/3 實測，見 DEVLOG 2026-06-13 Phase 4）。

### A. 精彩定位 — DONE
- [x] **yt-dlp 拉 chat replay**（免 API key）：`src/chat_ytdlp.py` 下載+解析 `.live_chat.json`（offset 直接來自 `videoOffsetTimeMsec`），`chat_runner` 接 yt-dlp 來源 + `run.py --chat-url`
- [x] **spike 雙閘門修正**：實測稀疏聊天室 243/243 窗口全判 spike（baseline 被空窗拉低 + 10s 量化）→ 加 `min_spike_messages` 絕對閘門，活俠傳 243→7 個有意義 spike
- [x] **中文 reaction 關鍵字常駐**：`config/channel.yaml` reaction 併入中文（哈哈/笑死/不行了/太扯/傻眼/天啊/什麼鬼…），日中並列

### B. 切片品質 — DONE
- [x] **keyframe 對齊**：`_list_keyframes`（ffprobe packet flags，不解碼）+ 切點吸附 ≤start 最近 keyframe；實測首幀亮度 122（非黑）
- [x] **clip 長度夾制**：`_clamp_duration`（min_clip_sec / max_clip_sec，太短對稱外擴、太長從頭截）

### C. 短影音適配 — DONE
- [x] **clip 燒錄字幕**：`slice_srt`（切片+時間平移）+ ffmpeg `subtitles=` filter；Windows 路徑用 cwd+純檔名避跳脫；CJK 用 Microsoft JhengHei 實測渲染正常（非 tofu）
- [x] **9:16 直式輸出**：`_vertical_filter`（blur-pad 保全畫面 / crop 置中裁切），`--vertical`；實測 1080×1920
- [x] **精選合輯**：`render_highlight_reel`（top-N 按分數選、按時間排、concat demuxer，失敗退回重編碼）

### D. 一鍵化 + 文件 — DONE
- [x] **一鍵出片 wrapper**：`quick_clip.py`（預設直式+燒字幕+合輯，`--fast` 橫式快切，`--chat-url` 補 chat 訊號）
- [x] **補主 README.md**：根目錄 README（這是什麼 / 安裝含 GPU 配方 / 怎麼跑 / 輸出說明）

### 驗收標準 — 全過
- [x] 一條指令從影片到「可直接發的短影音 clip（含字幕、直式）」— GATE 3：3min 樣本→5 個 1080×1920 燒字幕 clip
- [x] `chat_spike` 訊號回到評分 — GATE 1：yt-dlp→解析→雙閘門 spike→align overlay→score.breakdown.chat_spike
- [x] 切點無黑畫面 / 無破格 — GATE 2/3：首幀亮度 120~126、直式尺寸正確

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
