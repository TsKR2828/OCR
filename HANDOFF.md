# VN-Transcribe 交接事項

> 最後更新：2026-05-17

---

## 專案一句話

VN 實況結構化引擎 — 三層感知（ASR + Chat Log + OCR）把實況錄影變成結構化時間軸 + 字幕 + 精彩剪輯。

位置：`C:\Users\admin\Desktop\Claude\VN-Transcribe`

---

## 目前狀態：後端 + 前端全部完工，待實測

| Phase | 內容 | 狀態 |
|-------|------|------|
| 0 (MVP) | ASR + Chat Log → timeline.json + index.md + xlsx | DONE |
| 1 | OCR 整合 + search CLI + conflict report | DONE |
| 2 | SRT 字幕（原文/實況主/雙軌）| DONE |
| 3 | 場景分類 + 精彩剪輯 + 統計 + EDL | DONE |
| StreamClip 移植 | 重複詞/語速突變/加權關鍵字/OpenCC | DONE |
| DESIGN-BRIEF | Web UI 介面規格書 | DONE |
| **Web UI** | **Vite + React + TS 前端（7 頁面 SPA）** | **DONE** |

---

## Git 狀態

```
分支：
  main          — Phase 0-3 程式碼
  audit/streamclip-merge — StreamClip 功能移植（1 commit ahead of main）

最新 commit（audit/streamclip-merge）：
  ded8f6f feat: StreamClip-Tool 功能移植（補完空殼 + 增強評分）

尚未合併回 main。
```

**2026-05-17（Web UI session）：**
1. 新建 `web/` — 完整 Vite + React 18 + TypeScript 前端
2. 更新 `HANDOFF.md` / `TODO.md` / `DEVLOG.md`
3. 新建 `dev.bat` — 一鍵啟動前端 dev server

**這些檔案目前全部 unstaged**（月月的 feedback：動工不自動 commit）。

---

## 待辦（月月尚未指示，但邏輯上接下來的事）

### 短期
- [ ] 合併 `audit/streamclip-merge` → `main`（git merge，月月要先看 diff）
- [ ] commit 本次進度文件更新 + web/
- [ ] 真實影片端對端測試（需要一段 VN 實況 .mp4）
- [ ] YouTube Data API key 設定 + chat replay 實測

### 中期
- [ ] Web UI 接真實 API（目前跑 mock data，需接 timeline.json）
- [ ] 翻譯功能（Claude API，月月說「不著急」）

---

## 檔案結構（關鍵檔案）

```
VN-Transcribe/
├── run.py                    # CLI 入口（Typer）
├── search.py                 # 搜尋 CLI（6 子命令）
├── dev.bat                   # 一鍵啟動前端 dev server
├── config/channel.yaml       # 頻道設定範本
├── src/
│   ├── pipeline.py           # 主流程：ASR→Chat→OCR→Align→Classify→Render
│   ├── asr_runner.py         # faster-whisper + OpenCC + 重複詞/語速/加權關鍵字
│   ├── chat_runner.py        # YouTube Data API v3 chat replay
│   ├── ocr_runner.py         # MangaOCR headless
│   ├── align.py              # align_mvp() + align_full() 三層對齊
│   ├── classifier.py         # 場景分類（6 類 rule-based）
│   ├── clipper.py            # FFmpeg 精彩片段切片
│   ├── schema.py             # Segment dataclass + JSON 序列化
│   └── renderers/
│       ├── index.py          # → index.md
│       ├── excel.py          # → transcript.xlsx
│       ├── conflict.py       # → conflict_report.md
│       ├── subtitle.py       # → SRT ×3（原文/實況主/雙軌）
│       ├── stats.py          # → stats.md（角色統計+場景分佈）
│       └── markers.py        # → EDL + MPV chapters
├── web/                      # 前端 SPA（Vite + React 18 + TypeScript）
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── App.tsx           # App shell + 路由 + 鍵盤快捷鍵
│       ├── types.ts          # 全域型別定義
│       ├── data/mock.ts      # Mock data（角色/段落/衝突/片段/密度）
│       ├── styles/main.css   # Brass Library 深色主題 CSS
│       ├── components/       # 9 共用元件（Sidebar, Topbar, Icons, ...）
│       └── pages/            # 7 頁面（Dashboard → Settings）
├── ROADMAP.md                # 完整設計文件 + schema 定義
├── TODO.md                   # 進度追蹤
├── DEVLOG.md                 # 開發日誌
├── DESIGN-BRIEF.md           # Web UI 介面規格書
├── HANDOFF.md                # 本檔
└── requirements.txt
```

---

## CLI 用法

```bash
# 基本（ASR + Chat → timeline + index + xlsx + stats）
python run.py video.mp4

# 三層模式
python run.py video.mp4 --ocr --ocr-config path/to/config.json

# 全開
python run.py video.mp4 --ocr --srt --clips --video-id "dQw4w9WgXcQ"

# 搜尋
python search.py character ケイ
python search.py reaction --top 10
python search.py conflict
```

---

## 設計決策快速參考

- Speaker 判斷：語言 proxy（中文=streamer, 日文=game_voice），不做 diarization
- Chat spike：density > baseline × 2.5
- OCR 段長：以下一段出現時間為 time_end，超時 12s 截斷
- 對齊：overlap ratio > 0.3 配對，edit distance < 0.2 = consistent
- SRT：UTF-8 BOM（相容性），整數毫秒運算（避免浮點 bug）
- 場景分類：零成本 rule-based，不用 LLM
- 剪輯：FFmpeg `-c copy`（keyframe 快切），padding 3s，gap < 2s 合併
- 繁簡轉換：OpenCC `s2twp`（含詞彙轉換，不是純字對字）

---

## 月月的偏好提醒

- 動工不自動 commit/push — 留 unstaged，她自己審完再決定
- 中文回覆
- 她是 SEO 內容工作者 + 個人開發者
- 喜歡先計畫再動手（"先計畫"）
- 不喜歡冗餘確認，直接做
