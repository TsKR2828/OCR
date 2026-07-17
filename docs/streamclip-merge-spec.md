# StreamClip → VN-Transcribe 整併規格 v1

> 日期：2026-07-16
> 依據：Codex 對 StreamClip-Tool 的審查報告（基準 StreamClip `667270d` / VN `ea732e3`）+ Claude 抽查複驗
> 狀態：草案，待月月核可後拆批執行
> 執行模式：沿用四批已驗證的接力流程——Claude 出指令 → 月月轉貼 → Codex 修 → Claude 複驗 → 月月授權 commit

---

## 0. 目的與非目標

**目的**：StreamClip-Tool 的獨有能力併入 VN-Transcribe，VN 成為唯一入口（ASR、timeline、狀態管理、評分、出片）。StreamClip 退役。

**非目標**：
- 不追求「完美的訊號評分」。已實證（活俠傳 179min 實驗）訊號評分只懂能量不懂語意，真正的選段解是 LLM 讀逐字稿。評分在本整併中只定位為**候選預篩**。
- 不修 StreamClip 本體的 P1 bug（工具退役，修了浪費）。
- 不在本整併中處理 utterance 級語言辨識（見 DR-5）。

---

## 1. 決策記錄（Decision Records）

### DR-1：StreamClip 退役，VN 為唯一實作
理由：VN 已移植 StreamClip 多數邏輯（重複詞/語速/OpenCC/音量），且 VN 有 StreamClip 沒有的：Segment schema、快取指紋、原子寫入、job/stage status、clip manifest、字幕與渲染器。保留兩套=雙倍維護+兩套評分語意漂移。
StreamClip 剩餘獨有價值僅三項，全部遷入 VN：**每關鍵字獨立權重**、**chat JSONL 解析**、**teardown 前落盤教訓**（已於 VN `7d3b118` 完成）。

### DR-2：評分語意採「VN 絕對分數 + StreamClip 關鍵字權重」
- 保留 VN 的絕對分數制（每訊號固定權重、可封頂）。
- 引入 StreamClip 的「每關鍵字獨立權重」（神回:30、事故:25…）。
- **廢棄** StreamClip 的 per-video max normalization（弱峰值也拿滿分，平淡影片必產假精彩）。
- **廢棄** StreamClip 的合併分數累加（docstring 說取最高、實作卻累加，實測膨脹到 151 > 權重總和 130）。合併採「取最高分」+ 候選間最小間距（non-max suppression 簡化版）。

### DR-3：評分只做預篩，選段交 LLM
候選預篩目標＝高召回（寧可多列不可漏），排序精度交給 LLM 語意選段（`make_fcpxml --ranges` 接口已實證可行）。因此評分改動的驗收標準是「不漏掉已知好段」而非「排名完美」。

### DR-4：UI 以 `uiux/` 為正，`web/` 退役
`web/`（Vite 版）全頁 mock 空殼、無讀檔能力；`uiux/` 已有真實 timeline loader + DTO adapter + 匯出。停止對 `web/` 的一切投資；`uiux/` Phase 2（config 載入/多檔案/conflict diff）維持原 roadmap。`web/` 目錄暫留不刪（歷史參考），README 註明棄用。

### DR-5：語言/speaker 判定以 OCR 時段錨點為主，utterance LID 不做
實證：中文遊戲場語言 proxy 完全失效（活俠傳全片誤判）；日文遊戲場檔案級語言也會把混合語音全判給實況主。方向：**OCR 偵測到對白框的時段 → 該時段 ASR 傾向 game_voice**，交叉修正 speaker_guess。此為獨立設計題，不入本整併批次，記於此避免評分改動與它衝突（評分不得依賴 speaker_guess 的正確性）。

---

## 2. Canonical Schema

### 2.1 Raw ASR schema v1（現狀即為 v1，補版本標記）
```json
{
  "schema_version": 1,
  "segments": [
    {"start": 0.0, "end": 2.3, "text": "...", "no_speech_prob": 0.01, "language": "zh"}
  ]
}
```
- 現行 `asr_cache.json` 是裸陣列 → 讀取端相容裸陣列（視為 v0），寫入端一律寫 v1 包裝。
- StreamClip 舊 `segments.json`（僅 start/end/text）視為 legacy：僅在月月明示要匯入時轉換，`no_speech_prob` 設 null 不得假造、`speaker_guess` 設 unknown。

### 2.2 HighlightCandidate schema v1（新增，取代「Segment.score 隱式承載」）
```json
{
  "schema_version": 1,
  "start": 123.4,
  "end": 145.6,
  "score": 62.5,
  "breakdown": {"volume_spike": 15, "keyword_hit": 27.5, "chat_spike": 20},
  "reasons": ["關鍵字:神回", "chat spike ×3"],
  "segment_ids": [41, 42, 43],
  "clamped_to_media_end": false
}
```
- 時間一律 float 秒（canonical）；格式化字串只存在於 renderer 輸出。
- `segment_ids` 回鏈 timeline，供 LLM 選段與 UI 跳轉。
- 落盤為 `highlights.json`（原子寫入 + meta 指紋，沿用既有機制）。

### 2.3 keywords 設定格式擴充（向下相容）
```yaml
keywords:
  reaction:            # 既有格式：純列表 → 每項預設權重 10
    - "哈哈"
  weighted:            # 新增：關鍵字 → 權重 map（StreamClip 能力）
    神回: 30
    事故: 25
```
- 舊設定檔（純列表）行為完全不變。
- `keyword_hit` breakdown 上限 = `weights.keyword_hit`（維持封頂，防單段堆疊膨脹）。

---

## 3. 演算法修正規格（合併/邊界）

1. **合併取最高**：重疊或 gap ≤ `clip_merge_gap_sec` 的候選合併時，score = max，不累加；reasons 聯集。
2. **最小間距**：合併後任兩候選起點間距 < `min_candidate_gap_sec`（新設定，預設 30s）時，只留分高者——防同一事件吃掉多個名額（Codex 審查已指出 chat spike 複製問題）。
3. **padding 後重疊消解**：加 padding 後若相鄰候選重疊 → 在重疊中點切開，不產生重複內容片段。
4. **媒體尾端 clamp**：所有候選 end ≤ ffprobe 實際時長（機制已在 `_get_media_duration`），clamp 發生時標記 `clamped_to_media_end`。
5. **廢除音量強制補 Top 20**：音量訊號不足就是不足，不硬補（假精彩來源之一）。`min_score` 維持絕對門檻。

---

## 4. 遷移/修正項目 → 批次計畫

| 批 | 內容 | 風險 | 依賴 |
|---|------|------|------|
| 批5 | **效率**：音量分析改 block streaming（現一次載入整支 WAV，3hr>1GB RAM）；clip 渲染改受控 worker pool（預設 2–3 併發） | 低（機械） | 無 |
| 批6 | **評分回歸基準**：固定 fixture（用 D:\VN-Transcribe-test 的活俠傳 timeline 抽 10min 子集）+ 現行 top-N 候選 snapshot 測試。動評分前先鎖基準 | 低 | 無 |
| 批7 | **評分語意**：§2.3 關鍵字權重 + §3 全部修正 + HighlightCandidate 落盤。驗收=基準 fixture 中已知好段不消失、假精彩（151 分型膨脹）不再現 | 中 | 批6 |
| 批8 | **chat JSONL 強化**：損毀行計數+警告（現靜默略過）；混合時間格式不丟資料；納入 stage_report | 低 | 無 |
| 批9 | **OCR 解碼效率**：逐幀 read() 改 ffmpeg `fps+crop` image pipe（現解碼整支影片只用 1/15 的幀） | 中 | 無 |
| 批10 | **markers fps**：EDL/markers 以 ffprobe 實際 fps 產 timecode（現兩專案都寫死 30fps NDF） | 低 | 無 |
| 批11 | **StreamClip 退役**：README 標 deprecated 指向 VN；channels/*.yaml 權重搬到 VN config；不刪 repo | 低 | 批7 |

- 批5/6/8/10 彼此獨立可任意排序或並行；批7 必須在批6 之後。
- 每批沿用既有指令模板：branch 回報、驗收測試、邊界條款、不 commit。

## 5. 回歸與驗收

- **全程綠燈**：既有 30 測試任何批次不得變紅。
- **評分漂移門檻**（批7 專用）：基準 fixture 的人工標定好段（月月挑 5 段）必須全數留在 top-30 候選內；總候選數變動 ±50% 內。
- **整併完成定義**：VN 單一命令可產出 StreamClip 原有全部產物（逐字稿 md/CSV 候選/markers/clips）且品質不低於原工具；StreamClip README 已標退役。

## 6. 開放問題（不阻塞動工）

- 舊 StreamClip `segments.json` 是否需要批量匯入？（月月決定；預設不匯入）
- `web/` 目錄何時實際刪除？（預設 uiux Phase 2 完工後）
- GPU 依賴鎖版（constraints.txt + 單一 CUDA runtime 策略）——值得做，但屬環境工程，另開不入本整併。
