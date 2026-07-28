# VN-Transcribe Dashboard — Devlog

---

## 2026-05-20 — Dashboard 復活：從死 Mockup 到可用的 Timeline Viewer

### 背景

uiux/ 資料夾裡有一套完整的 7 頁 dashboard mockup（React CDN + Babel inline），
視覺做得很完整——sidebar、segment cards、conflict diff view、clips browser、stats charts 全都有。
但 `data.jsx` 裡面是 **100% 寫死的假資料**（深紅の月夜 ep07），
沒有任何地方可以導入影片或載入 pipeline 跑完的結果。

同時 `web/` 裡有一份 Vite + React 19 + TypeScript 的移植版，同樣是寫死假資料，src/ 沒接上真資料。

### 目標

> 「救活它」—— 讓 dashboard 能載入任何 VN-Transcribe pipeline 產出的 `timeline.json`，
> 所有面板都用真實資料驅動。

### 做了什麼

**只改了 2 個檔案**，其餘 5 個 JSX + CSS 完全不動：

#### 1. `data.jsx` — 全部重寫

舊版：232 行寫死的 mock data，`Object.assign(window, {...})` 丟到全域。

新版：
- `computeFromTimeline(rawSegments, filename)` — 核心函式，從 timeline.json 的 segment 陣列算出 UI 需要的 **13 個 window 全域變數**：

  | 全域變數 | 來源 |
  |---|---|
  | `VIDEO_DURATION` | max(time_end) |
  | `CHANNEL` | 檔名 + 預設值 |
  | `CHARACTERS` | 統計所有 `ocr.character`，自動分配顏色 |
  | `SCENE_TYPES` | 按 `scene_type` 分組計數 |
  | `FEATURED_SEGMENTS` | score 前 30 名，轉換成 UI 格式 |
  | `CONFLICTS` | `merge.match_status === "conflict"` 的 segments |
  | `CLIPS` | score 前 20 名，clips browser 格式 |
  | `DENSITY` | 時間軸分桶 (80-400 桶)，正規化到 0-1 |
  | `SCENE_BAND` | 每桶的主場景類型 |
  | `HOT_SPOTS` | density 前 5% 的桶 index |
  | `CHAR_PRESENCE` | 36 桶 binary 甘特圖 |
  | `STATS` | 總計 + score histogram |
  | `generateAllSegments()` | 全部 segments 的 UI 格式 |

- `_toUI(seg, idx)` — 把 schema.py 定義的 Segment 物件轉成 SegmentCard 期望的 UI 格式（events 陣列、score breakdown 重命名、chat SC 提取等）

- `loadTimelineFile(file)` — 接收 File 物件 → JSON parse → compute → 通知 React

- `window._VNT` — loading 狀態管理（loaded / filename / segmentCount / onLoad callback）

#### 2. `app-v2.jsx` — 加入 Landing Page

- 新增 `LandingPage` 元件：VN-TRANSCRIBE 品牌 + 拖放區 + 檔案選取按鈕 + 錯誤提示
- 新增 `AppShell` 外殼：檢查 `_VNT.loaded`，未載入 → LandingPage，已載入 → App
- 原本的 `App` 元件幾乎不動，只是被包在 AppShell 裡

#### 沒動的檔案（確認相容）

- `shared.jsx` — Sidebar, Topbar, Statusbar, SegmentCard, TimelineThumbnail, badges
- `pages-1.jsx` — Dashboard, Timeline, Search 頁面
- `pages-2.jsx` — Conflict, Clips, Stats, Settings 頁面
- `icons.jsx` — SVG icon library
- `tweaks-panel.jsx` — 外觀微調面板
- `styles-v2.css` — 全部樣式
- `VN-Transcribe v2.html` — 入口 HTML

### 驗證結果

用 200 段合成 timeline 測試（5 角色、8 場景類型、衝突、事件），
**全部 7 頁正常渲染，console 零錯誤**：

| 頁面 | 狀態 | 資料來源 |
|---|---|---|
| Dashboard | OK | stats, density, scene distribution, character gantt |
| Timeline | OK | segment cards with OCR/ASR/score/events |
| Search | OK | character/keyword 搜尋結果 |
| Conflict Review | OK | OCR vs ASR diff, suggestion, queue |
| Clips | OK | top highlights grid + detail panel |
| Stats | OK | character table, donut, histogram |
| Settings | OK | channel info, pipeline 參數 |

### 技術筆記

- **為什麼不改 shared/pages？** 所有 UI 元件都透過 `window` 全域讀資料，只要 `computeFromTimeline` 算出正確格式的全域變數，元件就能直接用。零耦合改動 = 零回歸風險。
- **SpeakerBadge 顏色**：shared.jsx 裡硬寫了 ケイ/ユリ/ハルカ 三個名字對應顏色，其他角色會 fallback 到 `--text-secondary`。Phase 2 可以改成查表。
- **Statusbar**：仍然顯示寫死的 "OCR: 1,247 / 1,247" 等。Phase 2 可以改讀 STATS。
- **web/ 資料夾**：同一套 UI 的 TypeScript 移植版，同樣寫死假資料。目前不需要，但如果以後要做正式 build/deploy 可以把 loader 邏輯搬過去。

---

## 2026-05-20 — Phase 1：動態化殘留硬寫值

把 Phase 0 沒動到的 shared.jsx / pages-1.jsx / pages-2.jsx 裡殘留的寫死值全部換成動態讀取。

- **SpeakerBadge** (`shared.jsx`)：查 `CHARACTERS` 陣列取 `ch.color`，streamer fallback `--amber`，其餘 `--text-secondary`
- **Statusbar** (`shared.jsx`)：`SEG: n | CHARS: n | CONFLICTS: n` + duration，從 `STATS` 讀
- **Stats 副標** (`pages-2.jsx`)：從 `STATS.duration` 動態計算 `Xh Ym Zs`
- **Conflict ASR label** (`pages-2.jsx`)：改讀 `CHANNEL.game_language`
- **Settings 預設值** (`pages-2.jsx`)：GAME_LANGUAGE / DEFAULT_LANGUAGE 反映 `CHANNEL` 資料
- **Search scope** (`pages-1.jsx`)：`STATS.totalSegments.toLocaleString()` 取代寫死的 "1,247"

---

## 2026-05-21 — Phase 3：匯出與互動

從「看」到「用」，讓 dashboard 能匯出資料並支援行內編輯。

### 新增檔案

#### `export.jsx` — 全部匯出函式

- `_dl(content, filename, mime)` — Blob → objectURL → 觸發下載
- `_baseName()` — 從 `CHANNEL.file` 取檔名基底
- `_applyEdits(seg)` — 把 `_VNT_EDITS` 疊加到 segment 上
- `exportExcel()` — SheetJS 匯出 .xlsx，3 sheets：Segments (13 欄) / Characters / Conflicts，自動欄寬
- `exportConflictJSON(conflicts, decisions)` — 含 decision 的衝突報告 JSON
- `exportChapters()` — clips → `.chapters` 格式（`HH:MM:SS.sss title`）
- `exportSRT()` — clips → `.srt` 字幕格式
- `exportEDL()` — clips → CMX 3600 EDL 格式
- `exportEditedTimeline()` — 帶編輯的完整 timeline.json 重新匯出

### 修改檔案

#### `VN-Transcribe v2.html`
- 加入 SheetJS CDN：`xlsx-0.20.3/xlsx.full.min.js`
- 加入 `export.jsx` script tag

#### `pages-1.jsx`
- Dashboard topbar：Export Excel / Export JSON 按鈕接上 `exportExcel()` / `exportEditedTimeline()`

#### `pages-2.jsx`
- Conflict Review：匯出 JSON 按鈕接上 `exportConflictJSON()`
- Clips：chapters / SRT / EDL 按鈕接上對應函式
- Stats：Export Excel / Export JSON 按鈕接上對應函式

#### `shared.jsx` — SegmentCard inline 編輯
- 新增 `editing` / `editSpeaker` / `editText` 狀態
- 讀取 `_VNT_EDITS[seg.idx]` 覆蓋顯示值
- 編輯模式：SPEAKER input + TEXT textarea + 儲存/取消/還原按鈕
- 已編輯的卡片顯示 amber 左邊條 + `●edited` 標記
- footer 新增「✎ 編輯」按鈕

#### `styles-v2.css`
- `.segment-card--edited::before` — amber accent bar
- `.segment-card__edit-area` — 編輯區 padding

#### `data.jsx`
- `_toUI()` 加入 `chapter` 欄位（Excel 匯出用）
- `window._VNT_EDITS = {}` 初始化

### 驗證

60 段合成 timeline 測試：
- 所有匯出函式可呼叫（`typeof` 均為 `function`）
- SheetJS 正常載入
- SegmentCard 編輯 → 儲存 → 顯示 edited 標記 → `_VNT_EDITS` 寫入正確
- 7 頁全部正常，console 無 runtime error

---

## 2026-05-21 — 黒星劇場 應援色整合

### 背景

黒星劇場 28 角色各有官方應援色（五星覺醒卡的主題色），
在 dashboard 中角色 badge、甘特圖等需要顯示正確的識別色。

### 做了什麼

#### `data.jsx`

- 新增 `_BLACKSTAR_COLORS` 常量：28 角色 name → HEX 對照表
  - K: ケイ 金色、銀星 靛藍、吉野 粉紅、ソテツ 深綠、ギィ 亞麻、夜光 藍紫
  - W: 黒曜 紅、晶 淺藍、シン 淺藍綠、鷹見 深藍、大牙 紫
  - P: リンドウ 綠、メノウ 紅緋、真珠 天藍、マイカ 玫瑰、ネコメ 淺紫
  - B: ミズキ 朱橙、リコ 珊瑚、ヒース 海松、藍 群青、金剛 黃、ヒナタ 向日葵黃
  - C: モクレン 紫羅蘭、カスミ 黃綠、クー 燕子花、玻璃 碧、柘榴 緋、青桐 群青

- 新增 `window._VNT_CHAR_COLORS` — 外部覆蓋接口（Phase 2 config 載入用）

- `computeFromTimeline` 角色顏色查找改為三級優先：
  1. `_VNT_CHAR_COLORS[name]` — 外部覆蓋
  2. `_BLACKSTAR_COLORS[name]` — 內建應援色
  3. `_CHAR_PALETTE[i]` — 通用自動分配

### 驗證

用 8 個黒星角色（ケイ/黒曜/リンドウ/ミズキ/モクレン/晶/真珠/大牙）測試：
- SpeakerBadge 顏色正確（金/紅/綠/橙/紫/淺藍/天藍/紫）
- Character Presence 甘特圖色塊正確
- 非黒星角色仍 fallback 到 `_CHAR_PALETTE`
