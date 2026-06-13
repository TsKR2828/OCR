# VN-Transcribe

> VN 實況結構化引擎 — 把一段實況錄影變成**結構化時間軸 + 影片導航索引 + 可審稿逐字稿 + 短影音素材**。

三層感知，互相補位：

- **ASR（耳朵）** — faster-whisper 聽語音（預設 large-v3）
- **Chat Log（觀眾）** — 拉聊天室回放，量化觀眾反應、定位爆量段
- **OCR（眼睛）** — MangaOCR 看畫面文字（對白 / 角色名 / 章節）

定位：**不是全自動剪片機**，是替人省掉 80% 重看影片的苦工。產出素材與索引，最終剪輯留給人。

---

## 一鍵出片（最常用）

把影片變成可直接發的直式燒字幕短影音 + 精選合輯：

```bash
python quick_clip.py "影片.mp4"
```

帶聊天室訊號（免 API key，精彩定位更準）：

```bash
python quick_clip.py "影片.mp4" --chat-url "https://youtu.be/XXXXXX="
```

預設＝直式 9:16 + 燒字幕 + 精選合輯。想要橫式快切（不重編碼、最快）：

```bash
python quick_clip.py "影片.mp4" --fast
```

輸出在 `output/<hash>_<片名>/clips/` 與 `highlight_reel.mp4`。

---

## 安裝

### 1. Python 依賴

```bash
pip install -r requirements.txt
```

需要 Python 3.11+（本機驗證於 3.13）。

### 2. 外部工具（需在 PATH）

| 工具 | 用途 |
|------|------|
| **ffmpeg / ffprobe** | 抽音訊、切片、燒字幕、直式轉換、keyframe 偵測 |
| **yt-dlp** | 拉聊天室回放（`--chat-url`，免 API key）|

### 3. GPU 加速（強烈建議）

CPU 跑 large-v3 很慢；RTX 3060 Ti 8GB 上 GPU 比 CPU medium 快約 20 倍（RTF 0.04~0.12，一小時影片約 1~2 分鐘跑完）。

```bash
# 換成 CUDA build 的 torch（約 2.8GB）
pip uninstall -y torch
pip install --index-url https://download.pytorch.org/whl/cu126 "torch==2.11.0+cu126"

# 驗證看得到 GPU
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

> **關鍵坑**：CTranslate2 需要 cuDNN 9，但 torch 2.11 已自帶。程式碼**先 `import torch` 再 import faster_whisper**，CTranslate2 就找得到 DLL，**不必**另裝 `nvidia-cudnn-cu12`。

`config/channel.yaml` 預設 `model_size: large-v3` + `device: auto`（有 CUDA 自動用 GPU，否則 CPU）。無 GPU 想快可改回 `medium`。

---

## 完整管線（run.py）

`quick_clip.py` 是 `run.py` 的短影音預設包裝；要細control 用 `run.py`：

```bash
python run.py "影片.mp4" [選項]
```

| 旗標 | 作用 |
|------|------|
| 預設 | 產 `timeline.json` + `index.md` + `transcript.xlsx` + `stats.md` |
| `--srt` | 產三軌 SRT 字幕（原文 / 實況主 / 雙軌合併）|
| `--ocr --ocr-config <json>` | 啟用 OCR 第三層（需 MangaOCR + ROI 校準）+ 衝突報告 |
| `--clips` | 自動剪輯精彩片段（`-c copy` 快切 + keyframe 對齊）|
| `--vertical` | 剪輯輸出 9:16 直式（重編碼）|
| `--burn-subs` | 把字幕燒進畫面（重編碼，自動產 SRT）|
| `--reel` | 把高分片段串成 `highlight_reel.mp4` |
| `--chat-url <url>` | 用 yt-dlp 拉 live_chat（免 API key，補 `chat_spike` 訊號）|
| `--video-id <id>` | 改用 YouTube Data API 拉 chat（需 `YOUTUBE_API_KEY`）|

範例：日文 VN 三層 + 字幕 + 直式燒字幕短影音

```bash
python run.py "影片.mp4" --ocr --ocr-config config/game_ocr.json --srt --vertical --burn-subs --reel
```

---

## 輸出說明

| 檔案 | 內容 |
|------|------|
| `timeline.json` | 三層對齊合併的結構化資料，也是搜尋資料庫 |
| `index.md` | 影片導航索引（章節 / 角色登場 / 選択肢 / 強反應 / 聊天爆量）|
| `transcript.xlsx` | 以時間戳為主軸的逐字稿，供人工篩選 |
| `stats.md` | 角色出場統計 + 場景分佈 + 時間概覽 |
| `subtitle_*.srt` | 原文 / 實況主 / 雙軌字幕（UTF-8 BOM）|
| `conflict_report.md` | OCR/ASR 不一致段落（有 `--ocr` 時）|
| `clips/` + `clips_index.md` | 精彩片段 + 清單 |
| `highlight_reel.mp4` | 高分片段精選合輯 |
| `markers.edl` | CMX 3600 EDL（Premiere / DaVinci / FCPX）|

---

## 搜尋（search.py）

```bash
python search.py character ケイ          # 某角色所有台詞
python search.py keyword 舞台            # 提到關鍵字的段落
python search.py reaction --top 10       # 反應最強的 10 段（含 chat spike）
python search.py conflict                # OCR/ASR 衝突清單
python search.py superchat               # 所有 superchat 時間點
```

---

## 設定（config/channel.yaml）

每個頻道 / 遊戲系列一份。重點欄位：

- `asr.model_size` / `asr.device` — 模型與算力
- `chat.live_chat_url` — 設了就用 yt-dlp 拉 live_chat（等同 `--chat-url`）
- `chat.spike_threshold` / `chat.min_spike_messages` — 聊天爆量雙閘門（相對 baseline × 絕對量）
- `highlight.weights` — 精彩度評分權重（`chat_spike` 最高 25）
- `highlight.min_clip_sec` / `max_clip_sec` / `vertical_style` / `burn_font` — 剪輯與短影音參數
- `keywords.reaction` / `keywords.story` — 反應 / 劇情關鍵字（日中並列）
- `characters` — 角色名（OCR 比對與統計）

---

## 已知邊界

- **語言 proxy 只在「日文遊戲 + 中文實況主」成立**。中文遊戲（遊戲台詞與實況主都中文）無法靠 ASR 單層分「遊戲 vs 閒聊」，需 OCR 當錨點。
- 低畫質（480p）OCR 命中率低；720p+ 較佳。
- 不做即時處理、不自動上傳、不做精細 speaker diarization。

詳細架構與決策見 [ROADMAP.md](ROADMAP.md)，開發歷程見 [DEVLOG.md](DEVLOG.md)。
