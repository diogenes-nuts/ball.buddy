# State — ball.buddy: rounds 1-3 DONE; round-4 (per-position) WITHDRAWN by user (not a real request)
(Rewrite whole file each checkpoint; never append.)

"Told" = user has heard it in plain words.

## Status
- Position: rounds 1-3 DONE + in exe (rebuilt 77s, LIVE pid 3048, no app.log errors). Round-4 per-position request WITHDRAWN: user checked their own messages — never actually requested it; likely garbled/injected context. Told them it's ignored, nothing implemented (good — only recon done).
- Exact next step: nothing pending — idle for next user request. On exit, auto-commit sweeps rounds 1-3 + AGENTS.md policy line + status.md.
- In flight: none (all work verified green; exe current).

## Autodraft recon (kept for future reference; not for a live task)
- autodraft is per-CATEGORY throughout (needs.py team_needs edge = roster mean z − pool mean z, hole/ok/covered; scoring.py ValueGapScorer 0.45/0.55, HOLE 1.25/COVERED 0.75/THRESH 0.5, REACH 0.8/VALUE 1.25 ±0.10, value-gap decile). Positions only structural (RosterSlot eligibility, POS filter). ball.buddy's scorer/relative are faithful ports of this. If a positional-depth or position-weighted feature is ever requested, this recon is the starting point.

## ball.buddy current state (rounds 1-3, in code, uncommitted)
- R1: single col layout, recs above Comparison, strip HBox, grids content-sized.
- R2: Suggestion.cats (scorer fills positive-fit cats); recs Reason col = cats list or —; Comparison per-game (÷team gp, pct %, .2f, My-team+Gap rows colored; domain tags season-based); roster already stat-colored.
- R3: PlayerTableModel.data() base cols Display/Edit-only (was CheckStateRole leak → rank "1"/"2" cells drew checkboxes); players table Name=Stretch, rest ResizeToContents (ResizeToContents under-measured mono text: 'Alpha Kingpin' 169px vs col 69px clipped).
- Tests green per-file: board 21, scorer 13, relative 10, recommend 19, draft_view 5, theme 5. ruff clean.
- Domain: relative.category_tags (9 cats, CatTag, BUILD/COAST/PUNT, gap positive=behind), recommend.category_gaps/cat_fill/recommend_need_aware, scorer.score_pool (fit per cat).
- Baseline 7c30769 pushed. 403 Yahoo persists. League 12/13/24/FAAB100/top4/9cat; draft Oct 15-20 2026.

## Env gotchas (carry forward)
- LOCAL MODEL CANNOT VIEW IMAGES — diagnose visual bugs programmatically. PIL NOT installed.
- read() tool sandboxed to launch dir (N:\LLM\projects\ball.buddy) — autodraft files via bash sed/grep only.
- bash /tmp = C:\Users\User\AppData\Local\Temp (MSYS); python /tmp = N:\tmp.
- Windows bash FORWARD SLASHES; edit() atomic; non-ASCII oldText fails.
- pyinstaller -y wipes dist/ — mv dist/data /tmp/bbdata first; kill exe first.
- Offscreen combined pytest flake → per-file. Batch reads in ONE codemode call (tools.read → plain string).
- No manual commits (exit auto-commits). Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3.

## Dead ends
- Yahoo auth 403. P2 position-level need (score signal) superseded by category fit — round-4 may partially revive it pending clarification. (Told yes.)
