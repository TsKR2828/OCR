# VN-Transcribe 開發日誌

---

## 2026-05-07 — 專案初始化

- 建立專案目錄 `VN-Transcribe/`
- 完成 ROADMAP 定稿（三層感知：ASR + Chat Log + OCR）
- MVP 範圍確定：ASR + Chat Log → `timeline.json` + `index.md` + `transcript.xlsx`
- OCR 移至 Phase 1，降低 MVP 的環境門檻

### 設計決策

- `timeline.json` 作為中間格式名稱（取代 segments.json）
- Chat Log 作為附加層，不影響 `merge.source_type`
- Speaker 判斷用語言 proxy（中文=實況主、日文=遊戲語音），不做 diarization
- OCR segment duration 規則：以下一段出現時間為 time_end，超時用預設值
- `merge` 欄位拆成 `source_type` + `match_status` 兩個維度

### 待決事項

- YouTube Data API key 尚未設定
- 尚未決定是否需要 `.env` 管理 API key 或直接寫在 channel.yaml
- StreamClip PoC 的 `poc.py` 需確認哪些函式要抽出來給 `asr_runner.py` import
