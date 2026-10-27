# Game Documentary Agent Factory (free cloud MVP)

This is a **research/planning + footage matching + QA gate** pipeline, not yet an autonomous uploaded-video creator. Your original `Render Chinese documentary` workflow remains unchanged.

## Start in GitHub web
1. Actions > **Game Documentary Agent Factory** > Run workflow.
2. Enter an English gaming event or fact-check topic. Leave `scenes_file` as `scenes.json` only to smoke-test the existing Herculaneum scenes; replace it with a fact-checked gaming `scenes.json` later.
3. Download the `game-agent-planning` artifact. Inspect `research_leads.json`, `storyboard.json`, `edit_decisions.json` and `qa_report.json`.
4. Research headlines are **unverified leads**. Neither the title nor narration is automatically fact-checked. The pipeline must remain blocked until claims and media rights are verified.

## Optional authorized gameplay library
Upload lawful video files under `game_assets/`, and describe them in `game_assets/manifest.json`:

```json
[
  {
    "path": "game_assets/my_capture.mp4",
    "rights": "own_recording",
    "source_url": "",
    "game": "Pokemon Red",
    "event": "Mew glitch",
    "description": "Player enters battle and triggers encounter",
    "tags": ["Pokemon", "Mew", "glitch", "battle"]
  }
]
```

`rights`: one of `own_recording`, `licensed`, or `public_domain`. Licensed/public-domain clips **must** have `source_url`. Claims of license are not independently confirmed by the script. Large video files should generally be stored outside Git or supplied as smaller approved assets; GitHub has per-file and storage limitations.

A gaming scene should include:
```json
[
  {
    "narration": "經過多年探索，玩家發現另一種觸發方式。",
    "visual": "Pokemon Red battle triggering Mew glitch",
    "source_verified": true,
    "source_urls": ["https://example.org/source"]
  }
]
```
Only mark `source_verified` after manually checking original reliable evidence.

## What each agent currently does
- Researcher: Google News RSS query, saves article leads with their URLs. RSS results may be incomplete, unavailable, unrelated, or inaccurate.
- Storyboard planner: parses human-approved scenes. No paid LLM and no invented automated original scripts.
- Asset librarian: checks local existence, duration via FFprobe and declared usage rights.
- Matchmaker: conservative token-overlap matching, returns missing footage instead of inventing a clip.
- QA reviewer: blocks release if scenes or fact source evidence is missing, footage coverage is incomplete, or rights manifest is invalid.
- Producer: existing FFmpeg documentary renderer is separate; publication is **never automatic**.

## Current limits
This is an honest infrastructure MVP. It does not yet download gameplay from YouTube, automatically write verified 12-minute scripts, use CLIP-based semantic video retrieval, or render gaming-specific videos. Do not publish an edited video without confirming third-party rights and YouTube rules.
