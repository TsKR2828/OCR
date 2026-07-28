# VN-Transcribe Dashboard — Roadmap

> uiux/ 資料夾的 timeline viewer，從 pipeline 產出的 timeline.json 驅動。

---

## Phase 0 — Mockup 復活 (DONE 2026-05-20)

- [x] `data.jsx` 重寫：hardcoded mock → `computeFromTimeline()`
- [x] Landing page：拖放 / 選取 timeline.json
- [x] 7 頁全部可用（Dashboard / Timeline / Search / Conflict / Clips / Stats / Settings）
- [x] 驗證通過，console 零錯誤

---

## Phase 1 — 動態化殘留的硬寫部分 (DONE 2026-05-20)

讓所有面板完全反映載入的資料，消除 mockup 時代殘留的寫死值。

- [x] **SpeakerBadge 動態顏色**：查 `CHARACTERS` 陣列取 `color`，不再硬寫 ケイ/ユリ/ハルカ
- [x] **Statusbar 動態數值**：SEG / CHARS / CONFLICTS 計數從 `STATS` 讀取
- [x] **Stats 頁副標文字**：從 `VIDEO_DURATION` 動態計算
- [x] **Settings 頁雙向綁定**：channel info 欄位反映 `CHANNEL` 資料

---

## Phase 2 — 資料增強

讓 dashboard 顯示更豐富的 pipeline 資訊。

- [ ] **Config 載入**：支援同時載入 `.yaml` 頻道設定檔，填充 CHANNEL.name / game / characters aliases
- [ ] **多檔案支援**：Landing page 可選多個 timeline.json，sidebar 切換
- [ ] **Conflict diff 演算**：自動計算 OCR vs ASR 的字元級差異（目前 diff 陣列為空）
- [ ] **Chat 面板真實化**：segment card 展開時顯示真實 chat messages（目前 spike 時顯示寫死的日文訊息）

---

## Phase 3 — 匯出與互動 (DONE 2026-05-21)

從「看」到「用」。

- [x] **匯出 Excel**：`exportExcel()` — 3 sheets（Segments 13 欄 / Characters / Conflicts），SheetJS CDN
- [x] **Conflict 批次審核**：`exportConflictJSON()` — 含 decisions 的結構化報告
- [x] **Segment 編輯**：SegmentCard inline edit（speaker + text），`_VNT_EDITS` 追蹤，amber 標記
- [x] **Clip 標記匯出**：`exportChapters()` / `exportSRT()` / `exportEDL()` — chapters / SRT / CMX 3600
- [x] **Edited timeline 匯出**：`exportEditedTimeline()` — 帶編輯的 timeline.json 重新匯出

---

## Phase 4 — Pipeline 整合

讓 dashboard 跟 VN-Transcribe CLI pipeline 無縫銜接。

- [ ] **Output 目錄掃描**：指定 output 資料夾，自動列出所有已處理影片的 timeline.json
- [ ] **即時進度**：pipeline 執行時透過 WebSocket 顯示 OCR / ASR 進度
- [ ] **Batch 總覽**：黑星劇場等大量影片的批次處理進度 dashboard

---

## Phase 5 — Vite 正式版（可選）

如果需要正式部署或效能優化，把 uiux/ 的 CDN 架構遷移到 `web/` 的 Vite + TypeScript 版本。

- [ ] 把 `computeFromTimeline` 邏輯移植到 TypeScript
- [ ] 把 Landing page + AppShell 移植
- [ ] 用 proper module imports 取代 `window` 全域
- [ ] Production build + 靜態部署

---

### 優先級建議

**下一步**：Phase 2 的 config 載入 + 多檔案 + chat 真實化

**長期 / 視需求**：Phase 4 pipeline 整合、Phase 5 Vite 遷移
