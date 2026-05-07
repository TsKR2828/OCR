# VN-Transcribe TODO

## MVP（Phase 0）— ASR + Chat Log

### 基礎建設
- [ ] 建立 `src/` 目錄結構（pipeline, schema, align, renderers）
- [ ] 定義 `schema.py`：Segment dataclass + JSON 驗證
- [ ] 建立 `config/channel.yaml` 範本（從 ROADMAP 搬過來）
- [ ] 寫 `run.py` CLI 入口（Typer）
- [ ] 寫 `requirements.txt`

### ASR 管線
- [ ] 從 StreamClip `poc.py` 抽出核心 ASR 函式
- [ ] 寫 `asr_runner.py`：呼叫 ASR → 輸出 Schema 格式
- [ ] 實作 `speaker_guess` 語言 proxy 判斷
- [ ] 處理短句 < 2 秒 + 低信心 → unknown

### Chat Log 管線
- [ ] 申請 / 確認 YouTube Data API key
- [ ] 寫 `chat_runner.py`：video_id → liveChatMessages.list → 聚合
- [ ] 實作 spike 偵測（baseline density × threshold）
- [ ] 實作訊息保留策略（superchat 優先、普通訊息取前 N 則）
- [ ] 處理 API 不可用時的 graceful fallback（chat = null）

### 對齊 + 合併
- [ ] 寫 `align.py` MVP 版：ASR 骨架 + Chat 疊加
- [ ] 無 ASR 時段有 chat spike → 產生 event_only segment
- [ ] 組裝 `pipeline.py`：串接 ASR → Chat → align → render

### 輸出
- [ ] 寫 `renderers/index.py` → `index.md`（含聊天室爆量事件）
- [ ] 寫 `renderers/excel.py` → `transcript.xlsx`（含聊天室密度、SC 欄位）
- [ ] timeline.json 直接由 pipeline 輸出

### 驗收
- [ ] 找一段 10 分鐘 VN 實況錄影跑完整管線
- [ ] timeline.json 通過 schema 驗證
- [ ] Chat spike 抽查 5 段
- [ ] 非直播影片（無 chat）能正常跑完

---

## Phase 1 — OCR 整合 + 搜尋

### OCR 適配
- [ ] OCR-Tool `video_processor.py` 加 `frame_index` + `timestamp_sec`
- [ ] 新增 `export_json()` 函式
- [ ] 加 headless 模式
- [ ] 套用 OCR Segment Duration 規則（default 4s / max 12s）
- [ ] 寫 `ocr_runner.py`

### 三層對齊
- [ ] `align.py` 升級：加入 OCR overlap matching
- [ ] 實作 match_status 判斷（consistent / conflict / readback_possible）

### 搜尋 + 衝突
- [ ] 寫 `search.py` CLI（--character / --keyword / --reaction / --conflict / --superchat）
- [ ] 寫 `renderers/conflict.py` → 衝突報告

---

## Phase 2 — 字幕與翻譯

- [ ] `renderers/subtitle.py` → SRT 生成（日文原文 / 實況主 / 雙軌）
- [ ] 翻譯草稿（Claude API，選配）

---

## Phase 3 — 智慧標記

- [ ] 場景自動分類（dialogue / narration / choice / transition / reaction / silence）
- [ ] 精彩片段自動剪輯（FFmpeg）
- [ ] 角色出場統計
