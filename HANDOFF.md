# VN-Transcribe 交接事項

> 最後更新：2026-06-13

---

## 專案一句話

VN 實況結構化引擎 — 三層感知（ASR + Chat Log + OCR）把實況錄影變成結構化時間軸 + 字幕 + 精彩剪輯。

位置：`C:\Users\admin\Desktop\Claude\VN-Transcribe`

---

## 目前狀態：後端 + 前端全部完工，黑星劇場 GT 測試進行中

| Phase | 內容 | 狀態 |
|-------|------|------|
| 0 (MVP) | ASR + Chat Log → timeline.json + index.md + xlsx | DONE |
| 1 | OCR 整合 + search CLI + conflict report | DONE |
| 2 | SRT 字幕（原文/實況主/雙軌）| DONE |
| 3 | 場景分類 + 精彩剪輯 + 統計 + EDL | DONE |
| StreamClip 移植 | 重複詞/語速突變/加權關鍵字/OpenCC | DONE |
| DESIGN-BRIEF | Web UI 介面規格書 | DONE |
| **Web UI** | **Vite + React + TS 前端（7 頁面 SPA）** | **DONE** |
| **Pipeline 修正** | **Whitelist + SRT dedup + name ROI crop** | **DONE (unstaged, 黑星)** |
| **GT 比對工具** | **compare_gt.py — Excel GT vs pipeline output** | **DONE (unstaged, 黑星)** |
| **GPU 加速 + large-v3** | **torch cu126 修復 + large-v3，真實影片端對端達標** | **DONE (2026-06-13)** |
| **Phase 4 快速自動剪片** | **yt-dlp chat 訊號 + 燒字幕 + 9:16 直式 + quick_clip** | **DONE (2026-06-13, branch feat/quick-clip)** |

---

## ⭐ 最新進度：Phase 4 快速自動剪片流程 (2026-06-13)

### 一句話
`quick_clip.py` 一條指令從影片產出可直接發的直式燒字幕短影音 + 精選合輯。三條驗收標準全過（GATE 1/2/3 實測），詳見 DEVLOG 2026-06-13 Phase 4 條目。

### 做了什麼（已 commit 在 `feat/quick-clip` 分支）
- `src/chat_ytdlp.py`（新）：yt-dlp 拉 `.live_chat.json`（免 API key）→ 解析 → 補回 `chat_spike` 訊號
- spike 雙閘門修正：稀疏聊天室原本 243/243 全誤判 spike → 加 `min_spike_messages` 絕對閘門，活俠傳 243→7
- `src/clipper.py` 大擴充：keyframe 對齊（修 `-c copy` 黑畫面）+ 長度夾制 + 燒字幕（CJK 正黑體）+ 9:16 直式（blur-pad/crop）+ 精選合輯
- `quick_clip.py`（新）一鍵 wrapper + 根目錄 `README.md`（含 GPU 配方）

### 用法
```powershell
$env:PYTHONIOENCODING="utf-8"; cd C:\Users\admin\Desktop\Claude\VN-Transcribe
python quick_clip.py "影片.mp4"                       # 預設：直式+燒字幕+合輯
python quick_clip.py "影片.mp4" --chat-url "<URL>"    # 補 chat 訊號（免 API key）
python quick_clip.py "影片.mp4" --fast                # 橫式快切（不重編碼）
```

### 給下個視窗
- **驗收/微調**：clip 預設可能偏長（3min 樣本切出 52s clip）；想要更短可調 `channel.yaml` 的 `max_clip_sec` / `clip_merge_gap_sec`。字幕位置 `MarginV=60` 在直式底部，可依喜好調。
- **合分支**：`feat/quick-clip` 可考慮合回 main（連同 `audit/streamclip-merge` 一起；見下方 Git 狀態）。
- runbook + 測試腳本在 `D:\VN-Transcribe-test\`（QUICKCLIP-WORKFLOW.md / _test_*.py），非 repo 內。

---

## 前一進度：GPU 修復 + large-v3 達標 (2026-06-13)

### 一句話
torch 之前裝成 CPU build，GPU 完全沒生效。換成 `+cu126` 後 large-v3 在 RTX 3060 Ti 上 RTF 0.04~0.12（比 CPU medium 快 ~20 倍），雜談中文辨識字準估 92-95% 達標。

### 做了什麼
- **GPU 修復**：`pip install --index-url https://download.pytorch.org/whl/cu126 torch==2.11.0+cu126`（配方見 memory `reference-gpu-whisper` 或 `D:\VN-Transcribe-test\WORKFLOW.md`）
- **large-v3 升級**：config `model_size: large-v3` + `device: auto`
- **真實影片端對端**：雜談 74min 全片跑出 timeline + SRT，達標
- **實證語言 proxy 在中文遊戲失效**：活俠傳（中文遊戲）全判 streamer/reaction、零 game_voice

### 測試資產（在 `D:\VN-Transcribe-test`，非 repo 內）
- `WORKFLOW.md` — Opus 規劃／Sonnet 執行的分工 runbook（A 修 GPU → B large-v3 → C 驗收）
- `config_largev3.yaml` — GPU large-v3 設定（換影片只改路徑）
- `output_v3\...雜談...\` — timeline.json + subtitle_streamer.srt

### 給下個視窗
**第一優先是「快速自動剪片流程優化」**——TODO.md 有完整清單。GPU 修好後辨識瓶頸解除，可以開始把「辨識→定位→切片→燒字幕」串成一條龍。

---

## 最新進度（前）：黑星劇場 GT 比對 (2026-05-24)

### compare_gt.py 測試結果

**S1 SideA 第1話 (25 GT lines, 2 chars, 90s, 480p)**

| 模式 | 配對率 | 平均相似度 |
|------|--------|-----------|
| OCR (SRT) | 28% | 14.5% |
| ASR + split | **88%** | **67.8%** |

**S1 共通 第1話 テイクアウト (50 GT lines, 3 chars, 165s, 480p)**

| 模式 | 配對率 | 平均相似度 | 說明 |
|------|--------|-----------|------|
| ASR + split | 68% | 47.7% | 含無配音角色 |
| ASR 扣除無配音行 | **89.5%** | — | 風見咲月 24% 行無聲 |

**結論：480p 下 OCR 幾乎廢掉，Whisper ASR 日文品質很高（有配音行 ~90% 配對）。瓶頸是無配音角色（風見早希/咲月）。**

### 角色配音狀況
- 銀星: 28 lines (56%) — 全配音，ASR 品質好
- 風見咲月: 12 lines (24%) — **無配音**，ASR 完全抓不到
- ミズキ: 10 lines (20%) — 全配音，ASR 品質好

### 1080P 下載問題
- `cookies.txt` 帳號**無大会員**
- yt-dlp 報: `720P, 1080P are missing; you have to become a premium member`
- **解法**: `yt-dlp --cookies-from-browser chrome` 或重新匯出瀏覽器 cookies

---

## compare_gt.py 用法

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd C:\Users\admin\Desktop\Claude\VN-Transcribe

# 列出 Excel 分頁
python compare_gt.py --list-sheets "D:\Blackstar-game-video\Excel\BS-1.Back in the BLACK劇情翻譯.xlsx"

# ASR 品質測試（推薦）
python compare_gt.py output/<name>/<hash>/timeline.json "D:\...\BS-1.Back in the BLACK劇情翻譯.xlsx" --sheet "<分頁名>" --from-timeline --prefer-asr --split-sentences -v

# OCR 品質測試
python compare_gt.py output/<name>/<hash>/subtitle_original.srt "D:\...\BS-1.Back in the BLACK劇情翻譯.xlsx" --sheet "<分頁名>" -v
```

Flags: `--prefer-asr` (用 ASR 文字) / `--split-sentences` (拆長段落) / `-v` (逐句細節)

---

## Pipeline 測試指令

```powershell
$env:PYTHONIOENCODING = "utf-8"
cd C:\Users\admin\Desktop\Claude\VN-Transcribe
python -u run.py "<video.mp4>" -c config/blackstar.yaml --ocr --ocr-config config/blackstar_ocr.json --srt -o output/<name>
```

### 已有測試輸出
```
output/s1_sideA_ep01/   # SideA 第1話 (25 GT lines, 90s)
output/s1_ch01_ep01/    # 共通 第1話 (50 GT lines, 165s)
```

---

## Unstaged 改動清單

Phase 4 快速剪片 + GPU/large-v3 文件 + channel.yaml 已 **commit 在 `feat/quick-clip`**。
以下是**仍 unstaged**、屬黑星劇場/UI 原型/暫存的改動，留給月月自己審：

```
# 黑星劇場（2026-05-24，仍 unstaged）
compare_gt.py               # NEW — GT 比對工具
src/ocr_runner.py           # whitelist 硬鎖 + name_text_ratio + event guard
src/renderers/subtitle.py   # SRT _dedup_overlapping()
.gitignore                  # blackstar.yaml + blackstar_ocr.json
config/blackstar.yaml       # （已從追蹤移除，worktree 刪除待提交）
config/blackstar_ocr.json   # （同上）

# UI 原型迭代（仍 unstaged）
uiux/*.jsx, uiux/*.css, uiux/*.html, uiux/DEVLOG.md, uiux/ROADMAP.md, uiux/export.jsx

# 暫存/harness（不該進 repo）
_debug_*.py                 # OCR 前處理除錯腳本（可刪）
.claude/                    # harness 設定
```

> 註：Phase 4 commit 一併帶入 `config/channel.yaml`（含 2026-06-13 的 large-v3 預設 + 新的 chat/clip 參數）。測試用的 `config_largev3.yaml`、runbook、`_test_*.py` 在 `D:\VN-Transcribe-test`，不在 repo。

---

## 建議下一步

### 主線：Phase 4 快速自動剪片流程 —— ✅ 已完成 (2026-06-13)
「辨識 → 精彩定位 → 切片 → 燒字幕」一條龍已做完並實測（GATE 1/2/3 全過，已 commit 在 `feat/quick-clip`）。剩可選的收尾：
1. **真實素材試跑微調**：拿月月實際想剪的影片跑 `quick_clip.py`，依成片感覺微調 `max_clip_sec` / `clip_merge_gap_sec` / 字幕 `MarginV`。
2. **帶 chat-url 跑一場**：用 `--chat-url` 對有聊天室的直播跑，看 `chat_spike` 加權後精彩定位是否更貼觀眾反應。
3. **合分支**：`feat/quick-clip` → `audit/streamclip-merge` → `main`（兩條都還沒回 main）。
4.（選配）`crop` 直式風格、合輯轉場、字幕樣式模板。

### 支線：黑星劇場 GT 測試（沿用 2026-05-24）
1. **解決 1080P**: `--cookies-from-browser chrome` 或重新匯出 cookies
2. **跑更多 S1 分頁測試**: 37 分頁可比對，挑有配音的（非風見早希獨白）
3. **S3 720p 完整 pipeline**: OCR ROI 已校準，品質應比 S1 480p 好很多
4. **批次跑 S3**: 修 `batch_ocr.ps1` 路徑 + 編碼設定
5. **改善句子拆分**: Whisper 日文不加句號，逗號拆分有 min_part_len=4 限制

---

## Git 狀態

```
分支：
  main                    — Phase 0-3 程式碼
  audit/streamclip-merge  — StreamClip 移植 + Web UI + OCR 修正（3 commits ahead of main）
  feat/quick-clip         — ← 目前在這；從 audit/streamclip-merge 分出，Phase 4 快速剪片

feat/quick-clip 最新 commit：
  feat: 快速自動剪片流程優化（yt-dlp chat 訊號 + 切片品質 + 短影音）
  docs: Phase 4 快速剪片流程文件更新

合併路徑（建議）：feat/quick-clip → audit/streamclip-merge → main
（audit/streamclip-merge + feat/quick-clip 都尚未合回 main）
```

---

## 重要路徑

| 用途 | 路徑 |
|------|------|
| Pipeline 入口 | `C:\Users\admin\Desktop\Claude\VN-Transcribe\run.py` |
| 比對工具 | `C:\Users\admin\Desktop\Claude\VN-Transcribe\compare_gt.py` |
| 頻道設定 | `VN-Transcribe\config\blackstar.yaml` |
| OCR ROI | `VN-Transcribe\config\blackstar_ocr.json` |
| Excel GT | `D:\Blackstar-game-video\Excel\BS-1.Back in the BLACK劇情翻譯.xlsx` |
| S1 影片 | `D:\Blackstar-game-video\videos\主線\S1\` (168 mp4, 480p) |
| S3+ 影片 | `D:\Blackstar-game-video\videos\主線\S3~S7\` (720p) |
| Cookies | `D:\Blackstar-game-video\cookies.txt` (無大会員) |

---

## 檔案結構（關鍵檔案）

```
VN-Transcribe/
├── run.py                    # CLI 入口（Typer）
├── compare_gt.py             # GT 比對工具（NEW）
├── search.py                 # 搜尋 CLI（6 子命令）
├── dev.bat                   # 一鍵啟動前端 dev server
├── config/
│   ├── channel.yaml          # 頻道設定範本
│   ├── blackstar.yaml        # 黑星劇場專用設定（gitignored）
│   └── blackstar_ocr.json    # 黑星 OCR ROI（gitignored）
├── src/
│   ├── pipeline.py           # 主流程
│   ├── asr_runner.py         # Whisper + OpenCC
│   ├── ocr_runner.py         # MangaOCR + whitelist + name_text_ratio
│   ├── align.py              # 三層對齊
│   ├── classifier.py         # 場景分類
│   └── renderers/
│       ├── subtitle.py       # SRT ×3 + _dedup_overlapping()
│       └── ...
├── web/                      # 前端 SPA
└── output/                   # Pipeline 測試輸出
```

---

## 設計決策快速參考

- Speaker 判斷：語言 proxy（中文=streamer, 日文=game_voice），不做 diarization
- 角色名: whitelist 硬鎖（不在角色表→清空），name_text_ratio 裁切防噪點
- SRT 去重: overlap > 50% 保留優先級高的（ocr_asr > ocr_only > asr_only）
- SRT：UTF-8 BOM（相容性），整數毫秒運算（避免浮點 bug）
- GT 比對: 貪婪序列對齊 + 正規化 edit distance，threshold 0.3
- 預設 name_map: 風見咲月→風見早希（用戶自訂名→遊戲預設名）
