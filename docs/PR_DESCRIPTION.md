## Problem and behavior

The former topic-only workflow exported RSS leads without producing a documentary, while the separate renderer uses fixed archaeology scenes and text-card fallbacks. This draft adds a topic-driven production controller with fail-closed evidence, rights, visual matching and output-quality gates.

The controller supports bilingual research, retrieved exact-quote evidence, cross-publisher/duplicate-source checks, dated claim and narration audits, original Traditional Chinese chapters, strict Commons licensing, PySceneDetect intervals, actual-frame vision checks, measured Chinese narration and captions, 1080p FFmpeg rendering, thumbnail and attribution reports. Unsupported claims, missing licensed gameplay or quality failures produce a nonzero exit and explicit diagnostics, never a substitute title-card film.

Narration is measured as decoded PCM and encoded to AAC once for the whole edit, fixing cumulative decoder padding from per-scene AAC concatenation. QA compares stream and decoded audio lengths. Durable stage checkpoints, cancellation handling and Actions annotations preserve useful failure evidence. Existing render.py, Kokoro, Piper, Pixabay and Wikimedia workflows remain available.

## Provider configuration

Real Actions runs exposed an invalid default: GitHub officially retired GitHub Models, including inference, on 2026-07-30. That provider is now rejected explicitly. Configure an active text+vision provider with repository Secret `LLM_API_KEY` and Variables `LLM_BASE_URL` / `LLM_MODEL`; no key is sent to an implicit provider and GitHub tokens are not reused as other providers' keys. Gemini is a possible free-tier option where eligible, not a promise of sufficient free daily capacity.

## Validation

- 70 tests passed locally on Python 3.12.14. Includes actual 1080p encoding, subtitle burn-in, thumbnail, scene detection, full decode, 12-scene decoded tone-transition synchronization, early-ending narration rejection and a real SIGTERM child-process test.
- Provider responses, research and vision fixtures are explicitly synthetic. Tone markers are not AI narration; testsrc is not gameplay.
- GitHub Actions Python 3.11 tests succeeded at commits 17476a8 and 2e8a8f8; links and measured results are in docs/VALIDATION.md.
- Real Pokémon topic runs were blocked at model inference. The safe diagnostic revealed HTTP 200 with a non-JSON API envelope; official documentation confirmed the provider's retirement. No documentary was produced.
- Repeated dependency installation/pip check, Actionlint v1.7.12 (official checksum verified) and git diff --check passed.

## Usage and acceptance remaining

Actions → One Topic Game Documentary → Run workflow → Chinese topic. Batch supports 1–3 topic strings via config/topics.json; topic-list pushes trigger a run and the daily schedule is 09:20 Asia/Taipei. The queue is restored to empty after validation. Failed gates retain reports and upload no finished MP4.

An active model credential/provider must still be configured and tested. Real source research, rights-cleared Pokémon footage, actual visual matching, natural Chinese narration and a complete 10–15 minute film remain unverified. Automated quote/model checks and sampled frames are not guarantees of factual accuracy or legal rights. Cloud draft changes do not populate GitHub repository secrets or apply network policy automatically.

See docs/DOCUMENTARY.md for operation/cost limits, docs/VALIDATION.md for evidence, docs/REPOSITORY_REVIEW.md for existing defects, and docs/THIRD_PARTY.md for the source/license/CPU evaluation of PySceneDetect, SentrySearch, GhostCut, DirectorX and footage-retrieval-automation. Keep this a draft pending real end-to-end acceptance.
