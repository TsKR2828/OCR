# VN-Transcribe：VN 實況結構化引擎 ROADMAP

> OCR-Tool × StreamClip-Tool 融合計畫
> 最後更新：2026-05-09

---

## 一句話定位

把一段 VN 實況錄影丟進去，自動產出**結構化時間軸**、**影片導航索引**、**可審稿的逐字稿**。

三隻感知層：**ASR**（耳朵：聽語音）、**Chat Log**（觀眾：讀聊天室）、**OCR**（眼睛：看畫面文字）。

不是全自動剪片機，是讓人類省掉 80% 重看影片的苦工。

---

## MVP 收斂原則

第一版不追求完整視聽理解，只追求「**長影片快速索引化**」。

MVP 先接 **ASR + Chat Log** 兩條管線（API 拉 JSON + 語音辨識），產出三個核心檔案：

1. **`timeline.json`** — ASR、Chat Log（及後續 OCR）按時間排序合併的結構化資料
2. **`index.md`** — 影片導航索引（章節、角色登場、選択肢、強反應段落、聊天室爆量段）
3. **`transcript.xlsx`** — 以時間戳為主軸的逐字稿，供人工篩選與後續整理

**OCR 接在後面**（Phase 1）——光學辨識的環境成本（MangaOCR 模型 + ROI 校準）比 API 拉 JSON 高很多，先用 Chat Log 量化觀眾反應 + ASR 抓語音，已經能覆蓋大部分索引需求。

MVP 不處理翻譯、不自動剪片、不做精細 speaker diarization。
先讓資料能對齊、能搜尋、能人工檢查，再往後疊加。

---

## 現有資產盤點

| 工具 | 位置 / 來源 | 狀態 | 能力 |
|------|-------------|------|------|
| **StreamClip-Tool** | `Desktop/Claude/StreamClip-Tool` | PoC 可用 | faster-whisper ASR、音量/笑聲/關鍵字多訊號評分、SRT/Markdown 輸出 |
| **YouTube Data API v3** | `liveChatMessages.list` | 可用 | 直播結束後拉 chat replay，取得帶時間戳的聊天室訊息 |
| **OCR-Tool** | `Desktop/Claude/OCR-Tool` | 可用 | MangaOCR 抓文字框（對白/角色名/章節）、pHash 變化偵測、Excel 輸出 |

三層互補：ASR 是耳朵（聽語音）、Chat Log 是觀眾（讀彈幕反應）、OCR 是眼睛（看畫面文字）。合在一起就是完整的感知。

---

## 中間格式（Timeline Segment Schema）

所有 Phase 的基礎。一段影片處理完後，產出 `timeline.json`，每個元素長這樣：

```jsonc
{
  // 時間
  "time_start": 763.2,
  "time_end": 768.5,
  "time_display": "00:12:43",

  // OCR 層（來自 OCR-Tool）
  "ocr": {
    "chapter": "Chapter 1 — 邂逅",
    "character": "ケイ",
    "dialogue": "君は、ここにいてくれるのか。",
    "confidence": 0.95,
    "source_frame": 1526
  },

  // ASR 層（來自 StreamClip-Tool）
  "asr": {
    "text": "啊啊啊他這句好溫柔我不行了",
    "speaker_guess": "streamer",   // streamer | game_voice | mixed | unknown
    "language": "zh",              // zh | ja | mixed
    "confidence": 0.82
  },

  // Chat Log 層（來自 YouTube Data API v3）
  "chat": {
    "message_count": 23,           // 該時間段內的聊天室訊息數
    "messages": [                  // 取前 N 則代表性訊息（由 density 排序或 superchat 優先）
      { "author": "user123", "text": "草wwww", "type": "normal" },
      { "author": "vip_fan", "text": "ケイ！！！", "type": "superchat", "amount": "¥500" }
    ],
    "superchat_count": 1,
    "density_per_min": 138.0,      // 該段的訊息密度（msgs/min）
    "baseline_per_min": 42.0,      // 整場直播的平均密度（用於計算 spike）
    "is_spike": true               // density_per_min > baseline × spike_threshold
  },

  // 事件標記
  "events": {
    "chapter_change": false,
    "new_character": false,
    "choice_point": false,
    "cg_unlock": false,
    "streamer_reaction": true,
    "chat_spike": true             // 聊天室訊息密度突然爆量
  },

  // 精彩度評分
  "score": {
    "total": 67,
    "breakdown": {
      "volume_spike": 0,
      "laughter": 12,
      "keyword_hit": 0,
      "streamer_reaction": 30,
      "chat_spike": 25             // 聊天室爆量加分
    }
  },

  // 合併元資料
  "merge": {
    "source_type": "ocr_asr",       // ocr_asr | ocr_only | asr_only | event_only
    "match_status": "consistent",   // consistent | conflict | readback_possible | unverified | not_applicable
    "conflict_note": null
  }
}
```

`ocr`、`asr`、`chat` 任一側可以是 `null`（該段沒有文字框 / 沒有語音 / 沒有聊天室資料）。

### merge 欄位語意

**`source_type`** — 這個 segment 的主要資料來源（chat 為附加層，不影響此欄位）：

| 值 | 意義 |
|----|------|
| `ocr_asr` | OCR 和 ASR 都有資料，已配對 |
| `ocr_only` | 只有畫面文字，無對應語音（靜音段、文字演出） |
| `asr_only` | 只有語音，無畫面文字（過場、實況主獨白） |
| `event_only` | 純事件段落，無對白內容（章節轉場、長時間靜默） |

> **Chat Log 與 source_type 的關係**：Chat 是附加資料層，永遠疊加在其他來源之上。一個 `asr_only` 的 segment 同時有 `chat` 資料是正常的（代表觀眾在那段有反應但畫面沒文字框）。判斷是否有 chat 資料直接看 `chat` 欄位是否為 `null`。

**`match_status`** — OCR 和 ASR 的一致性判斷：

| 值 | 意義 | 觸發條件 |
|----|------|----------|
| `consistent` | 兩側內容一致 | edit distance ratio < 0.2 |
| `conflict` | 兩側內容不一致，需人工確認 | edit distance ratio ≥ 0.2 |
| `readback_possible` | ASR 日文與 OCR 高度相似，可能是實況主跟讀 | `game_voice` 判定 + edit distance < 0.15 + 無明顯聲線差異 |
| `unverified` | 只有單側資料，無法比對 | `source_type` 為 `ocr_only` 或 `asr_only` |
| `not_applicable` | 不適用比對（純事件段落） | `source_type` 為 `event_only` |

---

## OCR Segment Duration 規則

OCR-Tool 逐幀偵測，每次觸發只產出一個瞬時 timestamp。要和 ASR 做 overlap matching，必須把逐幀結果轉換成有 `time_start` / `time_end` 的段落。

### 轉換規則

```
幀序列：  F1    F2    F3    F4    F5    F6    F7    F8
OCR 結果：  A     A     A     B     B     -     -     C
            ├─── seg A ───┤├── seg B ──┤            ├─ seg C
```

1. **time_start**：取該文字框**第一次被偵測到**的幀 timestamp
2. **time_end**（優先）：取**下一個不同 OCR 文字框出現的前一幀** timestamp
3. **連續相同文字框**：合併為同一段（pHash 判定為相同畫面）
4. **超時補值**：如果同一文字框持續超過 `max_dialogue_duration_sec`，強制以 `default_duration_sec` 截斷
5. **尾段處理**：最後一個文字框後面沒有新文字框時，使用 `default_duration_sec` 作為持續時間

### 預設參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `default_duration_sec` | `4.0` | 無法從下一段推算時的預設持續時間 |
| `max_dialogue_duration_sec` | `12.0` | 單段對白最長容許時間，超過強制截斷 |

這兩個值可在 `channel.yaml` 的 `ocr.default_duration_sec` 和 `ocr.max_dialogue_duration_sec` 覆寫。

### 為什麼這樣設計

- VN 對白框通常顯示 2–6 秒，`default = 4.0` 是合理中間值
- 超過 12 秒不動的文字框通常是玩家掛機或暫停，截斷避免拖長 segment
- 用「下一段出現時間」作為 time_end 而非固定長度，因為 VN 玩家的閱讀速度不固定

---

## ASR Speaker Handling 策略

VN 實況影片通常只有單一混音音軌，MVP 不做 diarization，改用**語言作為 proxy** 判斷說話者。

### speaker_guess 判斷規則

| 條件 | 判定 |
|------|------|
| ASR 文字語言為中文 | `streamer` |
| ASR 文字語言為日文，且時間與 OCR 對白重疊 | `game_voice` |
| 中文與日文混雜 | `mixed` |
| ASR 片段 < 2 秒且 language confidence < 0.7 | `unknown`（不硬猜） |
| ASR 文字和 OCR 文字 edit distance < 0.2 且時間重疊 | `mixed`（可能是實況主跟讀） |
| 無法判斷 | `unknown` |

### confidence 計算（MVP 版）

```python
confidence = 1.0 - segment.no_speech_prob  # faster-whisper 自帶
```

後續可加入 `language_detection_confidence` 和 `overlap_ratio_with_ocr` 做加權。

### 已知邊界與容忍

- 實況主跟讀日文台詞 → 可能被歸為 `game_voice`，用 OCR 比對緩解
- 短感嘆句（「えー」「草」）→ 語言偵測不穩，歸 `unknown`
- 不追求 100% 正確，標記出來讓人判斷即可

---

## Chat Log Handling 策略

資料來源：YouTube Data API v3 的 `liveChatMessages.list`，拉直播結束後的 chat replay。

### 為什麼優先於 OCR

| | Chat Log | OCR |
|---|---|---|
| 取得成本 | API 拉 JSON，幾秒完成 | 載入 MangaOCR 模型 + 逐幀影像處理 |
| 環境需求 | 只需 API key + 網路 | 需要 GPU 或長時間 CPU 運算 |
| 校準成本 | 零（JSON 直接有時間戳） | 需要手動校準 ROI 區域 |
| 觀眾反應量化 | 直接可算訊息密度、superchat | 無法量化觀眾反應 |

MVP 先接 ASR + Chat Log，已經能做到：語音轉錄 + 觀眾反應熱點定位 + 精彩段落標記。OCR 在 Phase 1 加入後補上畫面文字層。

### 資料取得流程

```
YouTube 影片 URL / video_id
    ↓
youtube.liveChatMessages.list (chat replay)
    ↓
原始 JSON（author, text, timestamp, type, amount）
    ↓
按 segment 時間窗口聚合
    ↓
計算 density_per_min + baseline + is_spike
    ↓
寫入 timeline.json 的 chat 欄位
```

### 時間對齊

Chat replay 的時間戳是相對於直播開始的 offset（毫秒），和影片播放時間直接對應，不需要額外對齊邏輯。

### Spike 偵測

```python
baseline = total_messages / total_duration_min   # 整場平均密度
segment_density = segment_messages / segment_duration_min
is_spike = segment_density > baseline * spike_threshold  # 預設 spike_threshold = 2.5
```

### 聊天室訊息保留策略

每個 segment 不保留所有訊息（一場 2 小時直播可能有上萬則），只保留：
- 所有 superchat / super sticker（金額 > 0 的訊息）
- 普通訊息取前 `max_messages_per_segment` 則（預設 5），優先保留含關鍵字的
- `message_count` 保留完整計數，用於密度計算

### 已知限制

- 需要 YouTube Data API key（免費額度每日 10,000 units，`liveChatMessages.list` 每次 5 units）
- 非公開直播或已刪除的 chat replay 無法取得
- 成員限定聊天訊息可能被 API 過濾
- 如果直播時未開啟聊天室，`chat` 欄位為 `null`

---

## MVP（Phase 0）— ASR + Chat Log + 三件產出

> 目標：ASR + Chat Log 兩條管線跑完，直接拿到 `timeline.json` + `index.md` + `transcript.xlsx`
>
> OCR 不在此 Phase，在 Phase 1 加入。

### 專案骨架

```
VN-Transcribe/
├── config/
│   └── channel.yaml          # 頻道設定（語言、角色、關鍵字、閾值）
├── src/
│   ├── pipeline.py           # 主流程控制
│   ├── asr_runner.py         # 包裝 StreamClip PoC，輸出標準時間戳格式
│   ├── chat_runner.py        # YouTube Data API v3 chat replay 拉取 + 聚合
│   ├── ocr_runner.py         # （Phase 1）包裝 OCR-Tool，輸出標準時間戳格式
│   ├── align.py              # 時間戳對齊 + 合併
│   ├── schema.py             # Segment dataclass / 驗證
│   └── renderers/
│       ├── index.py          # → index.md
│       └── excel.py          # → transcript.xlsx
├── output/                   # 每次執行的輸出目錄
├── requirements.txt
└── run.py                    # CLI 入口
```

### channel.yaml 範例

```yaml
# ============================================================
# VN-Transcribe 頻道設定
# 每個實況頻道 / 遊戲系列一份，放在 config/ 目錄下
# ============================================================

channel:
  name: "月上零韻"
  game_language: ja           # 遊戲原文語言
  default_language: zh        # 實況主使用語言

# --- Chat Log 設定 ---
chat:
  enabled: true               # 設為 false 可跳過 chat 層（非直播影片）
  video_id: null               # 指定 YouTube video ID；null = 從影片 URL 自動偵測
  spike_threshold: 2.5         # density > baseline × 此值 → is_spike = true
  max_messages_per_segment: 5  # 每段保留的代表性訊息數上限
  include_superchat: true      # 是否保留 superchat（金額 > 0 的訊息）
  aggregate_window_sec: 10.0   # 聊天室訊息聚合的時間窗口（秒）

# --- ASR 設定 ---
asr:
  model_size: medium          # tiny | base | small | medium | large-v3
  device: auto                # auto | cuda | cpu
  min_segment_sec: 0.5        # 短於此的 ASR 片段丟棄
  short_utterance_sec: 2.0    # 短於此 + 低信心 → speaker_guess = unknown
  language_confidence_threshold: 0.7  # 語言偵測信心低於此 → 不硬猜 speaker

# --- OCR 設定 ---
ocr:
  sample_interval_sec: 0.5    # 影片取樣間隔（秒）
  hash_diff_threshold: 4      # pHash 差異閾值，低於此視為同一畫面
  stable_threshold: 2         # 連續幾幀穩定才觸發 OCR
  default_duration_sec: 4.0   # 無法從下一段推算時的預設持續時間
  max_dialogue_duration_sec: 12.0  # 單段對白最長容許時間

# --- 對齊設定 ---
alignment:
  overlap_ratio_threshold: 0.3      # 時間重疊比例 > 此值才配對
  edit_distance_consistent: 0.2     # 低於此 → consistent
  edit_distance_readback: 0.15      # 低於此 + game_voice → readback_possible

# --- 精彩度評分權重 ---
highlight:
  weights:
    volume_spike: 15
    laughter: 20
    keyword_hit: 20
    chat_spike: 25              # 聊天室爆量 = 觀眾強反應
    speech_rate_change: 5
    silence_then_burst: 10
    repeated_word: 5
  top_n: 30                   # 取前 N 個精彩段落
  min_score: 15               # 低於此分數不列入精彩候選

# --- 關鍵字 ---
keywords:
  reaction:                   # 實況主反應相關
    - "www"
    - "草"
    - "ｗ"
    - "笑"
    - "やばい"
    - "嘘"
    - "かわいい"
    - "好強"
    - "不行了"
    - "太扯"
  story:                      # 劇情事件相關
    - "選択肢"
    - "CG"
    - "エンディング"
    - "分岐"
    - "セーブ"
    - "ロード"
    - "回想"
    - "告白"

# --- 角色名列表（用於 OCR 角色名比對與統計）---
characters:
  - name: "ケイ"
    aliases: ["けい", "KEI"]
  - name: "ユリ"
    aliases: ["ゆり", "YURI"]
  - name: "ハルカ"
    aliases: ["はるか", "HARUKA"]
  # 遊戲開始後可隨時追加，不影響已產出的 timeline.json
```

### ASR 端適配

StreamClip PoC 已經有時間戳，需要：
- 把 `poc.py` 的核心邏輯抽成可 import 的函式
- 輸出格式對齊到 Timeline Segment Schema 的 `asr` 欄位
- 加上 `speaker_guess` 判斷邏輯（語言 proxy）

### Chat Log 端實作 (`chat_runner.py`)

- 用 `google-api-python-client` 呼叫 `liveChatMessages.list`
- 輸入 video_id → 拉完整 chat replay → 按 `aggregate_window_sec` 聚合
- 計算 baseline density（整場平均）和每段 density → 標記 `is_spike`
- Superchat 獨立保留，不受 `max_messages_per_segment` 限制
- 輸出格式直接對齊 Schema 的 `chat` 欄位
- 如果 API 不可用（非直播、chat 已關閉），`chat` 欄位設為 `null`，不影響其餘管線

### 對齊演算法 (`align.py`)（MVP 版）

MVP 只有 ASR + Chat Log，對齊邏輯較簡單：
- ASR segments 已有 `time_start` / `time_end`，作為 timeline 的骨架
- Chat Log 按時間窗口聚合後，直接疊加到重疊的 ASR segment 上
- 無 ASR 的時段如果有 chat spike，獨立產生 `event_only` segment

Phase 1 加入 OCR 後，完整的三層對齊邏輯：

```
OCR segments:  |---A---|     |---B---|        |---C---|
ASR segments:    |--1--|  |--2--|  |---3---|     |--4--|
Chat density:  ▁▁▂▅█▅▂▁▁▁▁▂▃▂▁▁▁▁▁▃▅██▅▃▁▁▁▁▂▂▁▁▁▁
                 ↓ overlap matching ↓
Merged:        |---M1--|  |--M2--|  |--M3--|  |--M4--|
                (+chat)            (+chat spike)
```

策略：
- 以時間重疊（overlap ratio）做配對，閾值由 `alignment.overlap_ratio_threshold` 控制（預設 0.3）
- 兩側都有資料 → `source_type: "ocr_asr"`，用 edit distance 判斷 `match_status`
  - < `edit_distance_consistent` → `consistent`
  - < `edit_distance_readback` + speaker 為 `game_voice` → `readback_possible`
  - 其餘 → `conflict`，兩邊都保留
- 只有一側有資料 → `source_type: "ocr_only"` / `"asr_only"`，`match_status: "unverified"`
- 無對白的事件段落 → `source_type: "event_only"`，`match_status: "not_applicable"`
- Chat Log 作為附加層，疊加到已配對的 segment 上，不影響 `source_type`

### 產出 1：`timeline.json`

ASR 與 Chat Log（及後續 OCR）對齊合併後的完整結構化資料。格式見上方 Schema。
這是所有後續功能的基礎，也直接可當搜尋用資料庫。

### 產出 2：`index.md`

掃描 timeline.json 中的事件標記，輸出影片導航索引：

```markdown
# 影片索引：【ゲーム名】實況 #3

| 時間 | 事件 | 內容摘要 |
|------|------|----------|
| 00:00:00 | 開場 | 實況主開場白 |
| 00:03:12 | 章節 | Chapter 1 — 邂逅 |
| 00:08:45 | 新角色 | ケイ 初登場 |
| 00:15:20 | 選択肢 | 三個選項出現 |
| 00:27:33 | 強反應 | 實況主爆笑段落（score: 78） |
| 00:27:33 | 聊天室 | 訊息爆量 138 msgs/min（平均 42）、SC ×2 |
| 00:42:18 | CG | CG 解鎖 |
```

額外格式：
- YouTube 章節格式（`00:00 開場\n03:12 Chapter 1`）
- MPV chapter file（`.chapters`）

### 產出 3：`transcript.xlsx`

以時間戳為主軸，整合兩側資料：

| 時間戳 | 章節 | 角色 | 遊戲原文(OCR) | 語音辨識(ASR) | 說話者 | 聊天室密度 | SC | 實況主反應 | 一致性 | 精彩度 |
|--------|------|------|---------------|---------------|--------|-----------|-----|-----------|--------|--------|

保留 OCR-Tool 原本的 Excel 使用習慣，方便人工篩選台詞、剪輯候選與後續語料整理。

### 驗收標準

- [x] 對一段 10 分鐘的 VN 實況錄影跑完整 ASR + Chat Log 管線
- [x] `timeline.json` 通過 schema 驗證（asr + chat 欄位正確填入）
- [ ] Chat Log spike 偵測結果與人工觀察一致（抽查 5 段）— 待實測
- [x] `index.md` 包含聊天室爆量事件
- [x] `transcript.xlsx` 欄位完整，可正常開啟篩選
- [x] 無 chat replay 的影片（非直播）能正常跑完（chat = null）

---

## Phase 1 — OCR 整合 + 搜尋與衝突處理

> 目標：加入 OCR 第三層感知，補上畫面文字（對白、角色名、章節），並提供搜尋與衝突報告

### 1-1. OCR 端適配

OCR-Tool 現在輸出 Excel 行，沒有精確時間戳。需要：
- 修改 `video_processor.py`：每個 OCR 結果帶上 `frame_index` 和 `timestamp_sec`
- 新增一個 `export_json()` 函式，輸出列表格式而非直接寫 Excel
- 不動現有 GUI 流程，加一個 headless 模式給 pipeline 呼叫
- 套用 OCR Segment Duration 規則（見上方）轉換成 `time_start` / `time_end`

### 1-2. 三層對齊

在 MVP 的 ASR + Chat 基礎上，加入 OCR 層的 overlap matching：
- OCR segments 與 ASR segments 做時間重疊配對
- Chat Log 繼續作為附加層疊加
- `source_type` 開始出現 `ocr_asr`、`ocr_only` 等值
- `match_status` 開始有 `consistent`、`conflict`、`readback_possible` 判斷

### 1-3. 搜尋 CLI (`search.py`)

```bash
python search.py --character ケイ              # 某角色所有台詞
python search.py --keyword 舞台               # 提到某關鍵字的段落
python search.py --reaction --top 10          # 實況主反應最強的 10 段（含 chat spike）
python search.py --chapter "Chapter 3"        # 指定章節全文
python search.py --conflict                   # OCR/ASR 衝突清單
python search.py --superchat                  # 所有 superchat 時間點
```

### 1-4. 衝突報告 (`renderers/conflict.py`)

OCR 和 ASR 不一致的段落專用報告：

```markdown
## 衝突清單（共 12 處）

### #1 — 00:12:43
- OCR: 「お前は伺を言っているんだ」
- ASR: 「お前は何を言っているんだ」
- 建議：ASR 版（「伺」→「何」是常見 OCR 誤判）

### #2 — 00:35:17
- OCR: （無文字框）
- ASR: 「ここにいる」
- 建議：補入 ASR 版（過場語音，畫面無字幕）
```

### 1-5. 驗收標準

- [x] OCR 結果正確填入 timeline.json（chapter、character、dialogue）
- [ ] OCR 文字和 ASR 文字的配對率 > 70%（有語音的段落）— 待實測
- [x] 衝突段落有標記，可人工檢視
- [ ] 搜尋 CLI 回應時間 < 1 秒（2 小時影片量級）— 待 benchmark
- [x] 衝突報告能列出所有 `merge.match_status == "conflict"` 的段落

---

## Phase 2 — 字幕與翻譯輔助

> 目標：輸出可直接用於影片編輯的字幕檔，附翻譯草稿

### 2-1. SRT 生成 (`renderers/subtitle.py`)

- 日文原文 SRT（時間戳來自 OCR 或 ASR，取信心度高的）
- 實況主語音 SRT（ASR streamer 軌）
- 雙軌合併 SRT（上行原文、下行實況主）

### 2-2. 翻譯草稿（選配，需 LLM）

- 用 Claude API 或本地模型，對每段 `ocr.dialogue` 生成中文翻譯
- 標記信心度：高（常見句型）/ 中 / 低（俚語、雙關）
- 輸出 `translation_draft.xlsx`，低信心段落高亮，人工審稿用

### 2-3. 驗收標準

- [x] SRT 在 VLC / MPV 能正常載入並對齊（UTF-8 BOM 編碼）
- [ ] 翻譯草稿的可用率 > 60% — 翻譯功能暫緩

---

## Phase 3 — 智慧標記與自動化

> 目標：減少人工標記，讓系統自己判斷場景類型和重要程度（此 Phase 需要 OCR 層已在 Phase 1 整合）

### 3-1. 場景自動分類

用規則 + 可選 LLM 判斷每段的 `scene_type`：

| 類型 | 偵測方式 |
|------|----------|
| `dialogue` | OCR 有角色名 + 對白 |
| `narration` | OCR 有文字但無角色名 |
| `choice` | OCR 出現「選択肢」或多行短文字 |
| `transition` | 章節標題變化 / 長時間無文字 |
| `reaction` | 無遊戲文字 + ASR 有實況主語音 |
| `silence` | 兩側都無內容 |

### 3-2. 精彩片段自動剪輯（選配）

從 StreamClip 已有的評分機制延伸：
- 挑 score > 閾值的段落
- 前後各加 3 秒 padding
- 用 FFmpeg 直接切出 `.mp4` 片段
- 產出 `clips/` 目錄 + `clips_index.md`

### 3-3. 角色出場統計

```markdown
## 角色統計

| 角色 | 台詞數 | 首次出場 | 最後出場 | 總時長 |
|------|--------|----------|----------|--------|
| ケイ | 47 | 00:08:45 | 01:52:33 | 12m30s |
| ユリ | 31 | 00:22:10 | 01:48:00 | 8m15s |
```

### 3-4. 驗收標準

- [ ] 場景分類準確率 > 75%（人工抽查 50 段）— 待實測
- [x] 自動剪輯的片段前後無截斷對白（padding + merge intervals）
- [x] 角色統計與人工計數誤差 < 5%

---

## 技術決策紀錄

| 決策 | 選擇 | 理由 |
|------|------|------|
| 對齊演算法 | 時間重疊 overlap matching | 比 DTW 簡單，VN 對白節奏慢，不需要精密對齊 |
| Speaker 分離 | 語言 proxy（中文=實況主、日文=遊戲） | 不用 diarization，省 VRAM，VN 場景命中率夠高 |
| Chat Log 優先於 OCR | MVP 先接 Chat Log，Phase 1 才加 OCR | API 拉 JSON 零環境成本，且直接量化觀眾反應 |
| Chat Log 來源 | YouTube Data API v3 `liveChatMessages.list` | 官方 API，支援 chat replay，免費額度足夠 |
| 翻譯引擎 | Claude API（Phase 3 選配） | 日文翻譯品質好；本地模型可做 fallback |
| 專案結構 | 新 repo，import 現有兩個工具 | 不破壞現有工具的獨立運作能力 |
| CLI 框架 | Typer | StreamClip 已在用，保持一致 |
| 中間格式命名 | `timeline.json`（非 segments.json） | 語意更直覺，本質就是時間軸 |
| OCR 段落時長 | 以「下一段出現時間」為 time_end，超時用預設值 | VN 玩家閱讀速度不固定，固定長度不準 |
| merge 欄位 | 拆成 `source_type` + `match_status` | 原本混淆了「來源」和「一致性」兩個維度 |
| Chat 與 merge 的關係 | Chat 為附加層，不影響 `source_type` | Chat 是量化訊號，不參與文字一致性比對 |

---

## 不做的事

- **即時處理**：不做邊播邊分析，只處理錄影檔。即時太複雜、收益不夠大。
- **全自動剪片上傳**：只產出素材和索引，最終剪輯留給人。
- **通用影片支援**：只針對 VN / 劇情遊戲實況最佳化，不追求涵蓋所有影片類型。
- **Web UI**：CLI + 檔案輸出優先，有需要再做 GUI。
- **精細 diarization**：MVP 不用 pyannote，用語言 proxy 夠用。

---

## 依賴與環境需求

```
# 核心（MVP 就需要）
faster-whisper              # ASR
google-api-python-client    # YouTube Data API v3（Chat Log）
openpyxl                    # Excel 輸出
numpy, soundfile            # 音訊處理
typer                       # CLI

# Phase 1（OCR 整合時加入）
manga-ocr                   # OCR
opencv-python                # 影片處理
imagehash                    # 畫面變化偵測

# Phase 3 選配
anthropic                    # Claude API（翻譯）

# 外部
ffmpeg                       # 系統需安裝
```

硬體：
- **最低**：CPU only，`base` 模型，一小時影片約跑 20 分鐘
- **建議**：CUDA GPU（6GB+ VRAM），`medium` 模型，一小時影片約跑 5 分鐘

---

## 里程碑摘要

| Phase | 感知層 | 核心產出 | 狀態 |
|-------|--------|---------|------|
| **MVP (Phase 0)** | ASR + Chat Log | `timeline.json` + `index.md` + `transcript.xlsx` | DONE |
| **1** | + OCR | OCR 整合 + 搜尋 CLI + 衝突報告 | DONE |
| **2** | — | SRT 字幕（翻譯暫緩） | DONE |
| **3** | — | 自動分類 + 剪輯 + 統計 + EDL 標記 | DONE |
| **StreamClip 移植** | — | 重複詞 + 語速突變 + 加權關鍵字 + OpenCC | DONE |

全部程式碼階段完工。剩餘：真實影片端對端測試 + YouTube API 實測。
