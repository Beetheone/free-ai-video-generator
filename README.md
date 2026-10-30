# Free AI Video Generator

## 歷史模式：丟一個題目，產出 10–15 分鐘 MP4（新）

到 [Actions → One Topic History Video](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-history.yml) 輸入歷史題目，會自動完成研究與查核、勾人腳本、授權歷史圖片運鏡、旁白、字幕、背景音樂、縮圖與 YouTube 說明欄，可選擇以私人上傳。用法、限制與設定見 [docs/HISTORY.md](docs/HISTORY.md)。

## 中文遊戲紀錄片（新流程，仍需真實服務驗收）

到 [Actions → One Topic Game Documentary](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-documentary.yml)，輸入中文題材與 10、12 或 15 分鐘。腳本與搜尋詞由系統產生，不必手寫分鏡。流程包含中英文研究、原文引句與跨來源審核、原創繁體中文腳本、Commons 授權遊戲影片、實際影格匹配、中文旁白、字幕、1080p MP4、封面與來源報告。

先看 [白話使用說明：現在輸入題目能做到哪裡](docs/USER_STAGE.md)。新增 `goal=research`、`script`、`movie` 三個明確階段，研究包附 `PROGRESS.md`；證據審核通過才有 `RESEARCH.md`，腳本審核通過才有 `SCRIPT.md`。研究與腳本成功都不代表影片完成。另有不安裝配音模型的 [研究入口](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-research.yml)，獨立檢查 Commons 授權候選並輸出 `FOOTAGE_GAPS.md`。

[真實寶可夢研究包已通過](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40678067902)：12 篇本文、6 篇有相關引句、5 項主張通過本次自動審核，約 2 分鐘完成；尚無合格長稿或 MP4。

**尚未證明能自動完成任意題材的高品質紀錄片。** 已驗證實際渲染、音畫同步與拒絕不合格內容，115 項測試在 GitHub Actions 成功。研究已整合 DDGS、Wikipedia-API、BM25、pySBD，使用真實來源、原文字元位置與片段編號，最多一輪缺口補查；不強迫模型湊故事。Gemini 真實文字＋圖片推論可用，Kokoro CPU 曾產出 9.625 秒中文語音與字幕並通過解碼檢查，自然度尚未聆聽驗收。缺少合法且相符的畫面時會回傳失敗與報告，沒有文字卡、無關素材或示範影片補位。詳見 [操作、驗證結果與限制](docs/DOCUMENTARY.md) 和 [第三方評估](docs/THIRD_PARTY.md)。

目前依使用者選擇，以 [config/model.json](config/model.json) 設定 Gemini `gemini-flash-latest` 與官方 OpenAI 相容端點；實測使用者覆寫的 `gemini-3.5-flash-lite` 可用。Actions 接受 `LLM_API_KEY`／`GEMINI_API_KEY`／`GOOGLE_API_KEY` Secret，非機密的端點與模型可放在 Variables 或 Secrets 覆寫。Gemini 免費資格與額度依帳戶而異，不保證足夠每天產片。[服務檢查](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/verify-documentary-environment.yml) 與 [Kokoro 語音檢查](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/verify-kokoro-voice.yml) 已接上，合併前透過功能分支推送觸發，合併後可手動執行。Actions 旁白預設已驗證的 Kokoro CPU 普通話；Edge 台灣中文仍保留，但當前測試沒有取得音訊。每日台灣時間 09:20 排程與最多三題批次已接上，單次驗證後會清空題材清單。

原本 `render.py`、Kokoro、Pixabay、Wikimedia、Piper 與以下舊工作流程均保留。下方介紹的是既有腳本／圖片動畫流程，不代表新遊戲紀錄片的品質或免費保證。

---

Turn a plain-text script into a fully narrated, long-form video — automatically, for free.

**Pipeline:** your script → AI voiceover (edge-tts) → word-accurate captions → AI-generated
images per scene (Pollinations.ai) → Ken Burns motion → stitched into one video with ffmpeg.
No paid APIs, no API keys.

## 1. Write a script

Create a `.txt` file like `scripts/example_script.txt`:

```
VOICE: en-US-AriaNeural
MUSIC:

---
IMAGE: a cozy coffee shop window on a rainy day, warm light, aesthetic photography
Rain taps gently against the window as steam rises from a fresh cup of coffee.
---
IMAGE: person journaling by candlelight, cozy bedroom
There's something quietly powerful about writing your thoughts down before bed.
```

- `VOICE:` and `MUSIC:` at the top are optional global settings.
- Each scene is separated by a line with just `---`.
- `IMAGE:` is optional — if you skip it, the narration text itself is used as the image prompt.
- One scene = one AI image + the Ken Burns pan/zoom + that scene's narration + captions.
  For a longer video, just add more scenes.

### Voices (free, no key needed)
Some options relevant to your channels:
- English: `en-US-AriaNeural`, `en-US-GuyNeural`, `en-GB-SoniaNeural`
- Persian: `fa-IR-DilaraNeural`, `fa-IR-FaridNeural`
- Japanese: `ja-JP-NanamiNeural`, `ja-JP-KeitaNeural`

Full list: run `edge-tts --list-voices` after installing.

## 2. Run it automatically (GitHub Actions — no computer needed)

1. This repo is already set up — just add your script under `scripts/your_script.txt` and push,
   or go to **Actions → Generate AI Video → Run workflow** and type in the script path
   (and optionally a voice override).
2. When it finishes, download the finished video from the run's **Artifacts** section.

This works the same way as your Hoshi Studio setup — everything happens in the cloud,
nothing runs on your own machine.

## 3. Run it locally (optional)

```bash
pip install -r requirements.txt
python generate_video.py --script scripts/example_script.txt --out output/final_video.mp4
```

Requires `ffmpeg` installed locally (`ffmpeg -version` to check).

### Useful flags
- `--voice en-US-GuyNeural` — override the voice for the whole video
- `--music assets/lofi.mp3` — mix in background music at low volume
- `--width 1080 --height 1920` — vertical video (Shorts/Reels)
- `--keep-temp` — keep per-scene files for debugging

## Honest limitations

- **Pollinations.ai is a free public service**, so occasionally an image request is slow
  or needs a retry — the script auto-retries but very rarely a scene's image may look off.
  You can just re-run the script; each run uses a new random seed.
- Captions are generated from edge-tts's real word timings, not guessed — they should
  stay in sync even for long narration.
- Each scene = one still image with motion, not an AI-generated video clip. True AI
  video-clip generation (Runway/Pika/Sora-style) isn't free at any real length or volume,
  so this uses the "narrated slideshow" approach instead — which is exactly the format
  most faceless/cozy content channels use anyway.
- A ~5-minute video (roughly 15-20 scenes) typically takes 5-15 minutes to render in
  GitHub Actions, mostly spent waiting on image generation.

## Possible next steps

- Auto-upload the finished video straight to YouTube via Composio (same setup you're
  already using for Cup Diaries metadata) — happy to wire that in if useful.
- Swap Pollinations for a different free image source if you want a specific visual style.
- Add a second video track (e.g. gameplay/footage) instead of AI images, for something
  like the Kickoff Zone clips.
