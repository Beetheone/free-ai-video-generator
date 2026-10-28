# Free AI Video Generator

## 中文遊戲紀錄片（新流程，仍需真實服務驗收）

到 [Actions → One Topic Game Documentary](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-documentary.yml)，輸入中文題材與 10、12 或 15 分鐘。腳本與搜尋詞由系統產生，不必手寫分鏡。流程包含中英文研究、原文引句與跨來源審核、原創繁體中文腳本、Commons 授權遊戲影片、實際影格匹配、中文旁白、字幕、1080p MP4、封面與來源報告。

**尚未證明能自動完成任意題材的高品質紀錄片。** 已驗證實際渲染、音畫同步與拒絕不合格內容，原有 82 項測試曾在 GitHub Actions 成功。先前 GPT 實測回報 `429 insufficient_quota`；使用者現已改選 Gemini，已切換專案預設並新增服務實測流程。缺少合法且相符的畫面時會回傳失敗與報告，沒有文字卡、無關素材或示範影片補位。詳見 [操作、驗證結果與限制](docs/DOCUMENTARY.md) 和 [第三方評估](docs/THIRD_PARTY.md)。

目前依使用者選擇，以 [config/model.json](config/model.json) 設定 Gemini `gemini-flash-latest` 與官方 OpenAI 相容端點；首次需安全填入 GitHub Secret `LLM_API_KEY`。`LLM_BASE_URL`、`LLM_MODEL` 的 Actions Variables 或 Secrets 仍會覆寫專案設定，請更新或移除舊的 GPT 覆寫值。Gemini 免費資格與額度依帳戶而異，不保證足夠每天產片。可先執行 [Verify Gemini documentary environment](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/verify-documentary-environment.yml)，以一個合成色塊圖與繁中輸入檢查推論，另檢查搜尋、Commons、實際台灣中文配音；這不是遊戲影片驗收。旁白預設 Edge，可選 Kokoro CPU。每日台灣時間 09:20 排程與最多三題批次已接上；[config/topics.json](config/topics.json) 預設空陣列，避免未設定就消耗額度。

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
