## Problem and behavior

The former topic-only workflow exported RSS leads without producing a documentary, while the separate renderer uses fixed archaeology scenes and text-card fallbacks. This draft adds a topic-driven production controller with fail-closed evidence, rights, visual matching and output-quality gates.

The controller supports bilingual research, retrieved exact-quote evidence, cross-publisher/duplicate-source checks, dated claim and narration audits, original Traditional Chinese chapters, strict Commons licensing, PySceneDetect intervals, actual-frame vision checks, measured Chinese narration and captions, 1080p FFmpeg rendering, thumbnail and attribution reports. Unsupported claims, missing licensed gameplay or quality failures produce a nonzero exit and explicit diagnostics, never a substitute title-card film.

Narration is measured as decoded PCM and encoded to AAC once for the whole edit, fixing cumulative decoder padding from per-scene AAC concatenation. QA compares stream and decoded audio lengths. Durable stage checkpoints, cancellation handling and Actions annotations preserve useful failure evidence. Existing render.py, Kokoro, Piper, Pixabay and Wikimedia workflows remain available.

## Provider configuration

Real Actions runs exposed an invalid default: GitHub officially retired GitHub Models, including inference, on 2026-07-30. That provider is now rejected explicitly. The user's latest Gemini choice is recorded in config/model.json (official OpenAI-compatible endpoint / gemini-flash-latest). Optional `LLM_BASE_URL` / `LLM_MODEL` overrides work from Variables or Secrets. A separate small service-check workflow rejects leftover GPT overrides before sending a Gemini key, validates actual text+vision inference with a synthetic image, and checks search, Commons and Taiwan TTS independently. Keys are never read from configuration files; GitHub tokens are not reused as model keys. Eligible free-tier access is not a promise of sufficient daily capacity.

## Validation

- 89 tests passed locally on Python 3.12.14. Includes actual 1080p encoding, subtitle burn-in, thumbnail, scene detection, full decode, 12-scene decoded tone-transition synchronization, early-ending narration rejection and a real SIGTERM child-process test. Additional tests cover safe provider errors, provider mismatch before key transmission, synthetic image request validation, and voice-only checks that never call a model API.
- Provider responses, research and vision fixtures are explicitly synthetic. Tone markers are not AI narration; testsrc is not gameplay.
- GitHub Actions Python 3.11 tests succeeded through commit cfbcbf8 (89-test workflow, 54 seconds): https://github.com/Beetheone/free-ai-video-generator/actions/runs/40610009032 . Earlier runs and measured results are in docs/VALIDATION.md.
- Actual Gemini inference passed using the user's gemini-3.5-flash-lite override: https://github.com/Beetheone/free-ai-video-generator/actions/runs/40609620530 . One synthetic red/blue image plus Traditional Chinese echo used 1,171 input and 35 output tokens. Search returned ten real RSS items and Commons API site metadata was accessible; article claims and gameplay permissions were not checked by this probe. Edge TTS 7.3.1 still returned NoAudioReceived. Kokoro CPU is checked independently without further model API calls.
- Real Pokémon topic runs were blocked at model inference. The safe diagnostic revealed HTTP 200 with a non-JSON API envelope; official documentation confirmed the provider's retirement. No documentary was produced.
- Repeated dependency installation/pip check, Actionlint v1.7.12 (official checksum verified) and git diff --check passed.

## Usage and acceptance remaining

Actions → One Topic Game Documentary → Run workflow → Chinese topic. Batch supports 1–3 topic strings via config/topics.json; topic-list pushes trigger a run and the daily schedule is 09:20 Asia/Taipei. The queue is restored to empty after validation. Failed gates retain reports and upload no finished MP4.

The earlier OpenAI inference returned HTTP 429, code=insufficient_quota: https://github.com/Beetheone/free-ai-video-generator/actions/runs/40604393457 . The user has now selected Gemini, whose key, endpoint and text/vision access have been verified on Actions; no replacement key is requested. The validation queue remains empty. Real research, rights-cleared Pokémon footage, visual matching, natural Chinese narration and a complete 10–15 minute film remain unverified. Automated checks are not guarantees of factual accuracy or legal rights. Cloud draft changes do not populate GitHub repository secrets or apply network policy automatically.

See docs/DOCUMENTARY.md for operation/cost limits, docs/VALIDATION.md for evidence, docs/REPOSITORY_REVIEW.md for existing defects, and docs/THIRD_PARTY.md for the source/license/CPU evaluation of PySceneDetect, SentrySearch, GhostCut, DirectorX and footage-retrieval-automation. Keep this a draft pending real end-to-end acceptance.
