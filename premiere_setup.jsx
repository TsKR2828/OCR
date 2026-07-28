/*  premiere_setup.jsx — Premiere Pro ExtendScript
    讀 sfx_selector.py 輸出的 JSON，自動匯入音效並放上時間軸。

    使用方式：
    1. 在 Premiere 裡開好你的專案（已有粗片序列）
    2. 選擇要放音效的序列（讓它成為 active sequence）
    3. 檔案 → 指令碼 → premiere_setup.jsx
    4. 選擇 .sfx.json 檔案
    5. 音效自動放到 A2 軌，與字幕時間對齊

    Premiere Pro 2023 (v23) + ExtendScript 相容。
*/

(function () {

    // ── 常數 ─────────────────────────────────────────────────────────
    var TICKS_PER_SEC = 254016000000;       // Premiere 內部時間刻度
    var SFX_TRACK_INDEX = 1;                // A2（索引從 0 起算）

    // ── 讀 JSON ──────────────────────────────────────────────────────
    function readJSON(filePath) {
        var f = new File(filePath);
        if (!f.open("r")) return null;
        f.encoding = "UTF-8";
        var raw = f.read();
        f.close();
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    // ── 在 Project bin 裡找同名項目 ─────────────────────────────────
    function findInBin(rootItem, name) {
        for (var i = 0; i < rootItem.children.numItems; i++) {
            var child = rootItem.children[i];
            if (child.name === name) return child;
            if (child.type === 2 && child.children) {  // bin
                var found = findInBin(child, name);
                if (found) return found;
            }
        }
        return null;
    }

    // ── 秒 → ticks 字串 ─────────────────────────────────────────────
    function secToTicks(sec) {
        var t = Math.round(sec * TICKS_PER_SEC);
        return t.toString();
    }

    // ── 確保有足夠的 audio tracks ────────────────────────────────────
    function ensureAudioTracks(seq, needed) {
        while (seq.audioTracks.numTracks <= needed) {
            app.project.activeSequence.audioTracks.numTracks;
            // Premiere 自動擴展 tracks 當你 insertClip 到不存在的 track 時
            // 但保險起見先檢查
            break;
        }
    }

    // ── 建一個 bin 來放匯入的音效 ────────────────────────────────────
    function getOrCreateBin(rootItem, binName) {
        for (var i = 0; i < rootItem.children.numItems; i++) {
            var child = rootItem.children[i];
            if (child.name === binName && child.type === 2) return child;
        }
        return rootItem.createBin(binName);
    }

    // ── 主流程 ───────────────────────────────────────────────────────
    function main() {
        // 1. 選擇 JSON 檔
        var jsonFile = File.openDialog(
            "選擇 sfx_selector 輸出的 .sfx.json",
            "JSON:*.json;*.sfx.json"
        );
        if (!jsonFile) return;

        var config = readJSON(jsonFile.fsName);
        if (!config || !config.assignments) {
            alert("JSON 格式錯誤或沒有 assignments");
            return;
        }

        // 2. 確認有 active sequence
        var seq = app.project.activeSequence;
        if (!seq) {
            alert("請先開啟或選擇一個序列 (sequence)");
            return;
        }

        var assignments = config.assignments;
        if (assignments.length === 0) {
            alert("沒有音效配對");
            return;
        }

        // 3. 收集需要匯入的 SFX 檔案（去重）
        var sfxPaths = {};
        var importList = [];
        for (var i = 0; i < assignments.length; i++) {
            var p = assignments[i].sfx_path;
            if (!sfxPaths[p]) {
                sfxPaths[p] = true;
                var f = new File(p);
                if (f.exists) {
                    importList.push(p);
                }
            }
        }

        // 4. 建 bin + 匯入
        var sfxBin = getOrCreateBin(app.project.rootItem, "SFX-Auto");

        if (importList.length > 0) {
            var importOK = app.project.importFiles(importList, false, sfxBin, false);
            if (!importOK) {
                alert("部分音效匯入失敗，繼續嘗試放置已匯入的");
            }
        }

        // 5. 放置音效到 A2
        var trackIdx = SFX_TRACK_INDEX;
        if (seq.audioTracks.numTracks <= trackIdx) {
            alert("序列只有 " + seq.audioTracks.numTracks +
                  " 條音軌，需要至少 " + (trackIdx + 1) +
                  " 條。請手動新增音軌後重試。");
            return;
        }
        var track = seq.audioTracks[trackIdx];

        var placed = 0;
        var failed = 0;
        for (var i = 0; i < assignments.length; i++) {
            var a = assignments[i];
            var sfxName = a.sfx;

            // 在 bin 或整個專案找這個音效
            var item = findInBin(sfxBin, sfxName);
            if (!item) {
                item = findInBin(app.project.rootItem, sfxName);
            }
            if (!item) {
                failed++;
                continue;
            }

            var startTicks = secToTicks(a.start);
            track.insertClip(item, startTicks);
            placed++;
        }

        // 6. 匯入 SRT（如果有的話）
        var srtPath = config.srt_file;
        if (srtPath && srtPath !== "") {
            var srtFile = new File(srtPath);
            if (srtFile.exists) {
                app.project.importFiles([srtPath], false,
                    getOrCreateBin(app.project.rootItem, "Subtitles"), false);
            }
        }

        // 7. 報告
        var msg = "完成！\n\n";
        msg += "放置音效: " + placed + " / " + assignments.length + "\n";
        if (failed > 0) {
            msg += "找不到: " + failed + " 個\n";
        }
        msg += "\n下一步：\n";
        msg += "1. 匯入 SRT → 字幕軌\n";
        msg += "2. 字幕 → 升級成圖形\n";
        msg += "3. 全選字幕 → 套用 apple 樣式";
        alert(msg);
    }

    main();
})();
