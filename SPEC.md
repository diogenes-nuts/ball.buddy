# ball.buddy — Top-Level Design Spec

A **self-contained Windows desktop app** for a Yahoo Fantasy Basketball
9-category H2H weekly league. The centerpiece is *matchup-aware decision
support*: knowing, every week, how you project against your specific opponent
and which of your available levers (waiver picks, drops, daily active/bench
choices) best tilt that matchup.

**Status:** design spec only. No code in this dir yet. Scaffolding
(`/init-docs`, component dirs, `pyproject.toml`) happens when Phase M0 starts.
This spec is the single source of truth for scope and architecture until the
repo is scaffolded; it then feeds `agents/ROADMAP.md` + `agents/info.md` in the
new repo.

## 1. Domain

Standard Yahoo 9-category H2H, weekly format, snake draft, keepers. Category
set, directions (TO negative — lower is better), and per-week scaling rules are
inherited unchanged from the AutoDraft domain brief
(`N:\LLM\projects\autodraft\agents\info.md` — copied into the new repo's
`agents/info.md` at scaffold time, extended with the weekly-matchup concepts in
§5).

Win condition per week: win ≥ 5 of 9 categories vs. the opponent (ties count
per-category per Yahoo rules).

### 1.1 Confirmed league settings (interviewed with user, pre-draft 2026)

| Setting | Value |
|---|---|
| Platform / format | Yahoo, 9-category H2H, weekly, 12 teams |
| Draft | Snake, 13 rounds, 60s pick timer, autopick on miss (Yahoo defaults, unconfirmed but standard) |
| Keepers | 2 per team. Cost = previous draft round + variable penalty (commissioner-assigned, not derivable). Finalized before the draft; **manual entry in-app for all 24 keepers** (player + team + cost round). Owners may **opt out of one or both keepers** — the app must support marking a keeper opted-out (player returns to the pool, the cost-round pick returns to that team). |
| Roster | 14 total: 10 active (PG, SG, G, SF, PF, F, C, 3 UTL) + 3 BN + 1 IR. IR is a **conditional 14th slot with no draft round**: empty for everyone at season start, usable only once an owned player becomes injured (Yahoo "injured while on roster" eligibility). Draft pool math: 12 x 13 drafted/FA slots = 156, minus keepers. |
| Lineups | Daily. Deadline is per-player: a player can be moved until his game starts. |
| Adds/drops | 3 adds per week, unlimited drops. **FAAB claims are the only way to add** (no free adds even at top waiver priority). Every add event counts against the 3, including re-adding the same player. Dropped players are on league hold (Yahoo default ≈ 3 days) before anyone can claim. |
| Waivers | FAAB, $100 budget, nightly processing, blind bids. |
| Trades | Unlimited, commissioner approval per Yahoo default (vetos rare). Trade deadline exists; date not yet set this year — read from Yahoo at sync, manual-entry fallback. |
| Standings | Regular season: total category wins. |
| Playoffs | Top 4 advance, top 2 get a first-round bye, single elimination, same 9-cat H2H rules. The entire fantasy season (incl. playoffs) ends 2–3 weeks **before** the NBA regular season ends. |
| Scoring | Pure 9-cat, unweighted, no special rules (no double-count days, no POTW bonuses). |
| IR rule | Custom per league: IR-eligible only if the player was added to the owner's roster *before* becoming injured (no stashing season-injured players). |
| Commissioner overrides | None. |

**Open items (flagged, not blocking):**
- **Matchup-level tie-break**: per-category ties are handled Yahoo-default (tie counts for *both* teams). What happens when a *matchup* ends 4-4 is disputed in this league (Yahoo default: more total category wins that season; alternate theory: better regular-season head-to-head record — was a source of controversy last year). **Confirm with commissioner.** Engine must make this a configurable setting, defaulting to Yahoo default.
- Transaction cutoff time (~2-3 AM user-local; read from Yahoo league settings at M1 sync).

### 1.2 Priority (user-stated, pre-draft)

The **draft tracker/board is the first feature built** — after whatever scaffolding and league data sync are necessary to run it. The weekly-season features (matchup view, advisors) come after.

## 2. Non-goals (for v1; candidates for later phases)

- Live draft-day assistant (now the **first** feature, M2, per §1.2).
- Multi-league management (one league, one user, local).
- Cloud sync, accounts, telemetry — the app is offline-capable and local-only.
- ML models. Statistical projection + Monte-Carlo only.
- Any feature requiring write access to Yahoo beyond what the user would do
  manually (the app *recommends*; the human clicks on Yahoo).

## 3. Stack (decided)

| Concern | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.14, venv, pytest, ruff, doc-structure repo conventions (same as AutoDraft) | existing toolchain + salvage is Python |
| UI | **PySide6** (Qt, LGPL), native widgets | self-contained exe, no web stack, no build step, salvage drops in as plain calls. Not PyQt6 (license), not Tkinter (too limited), not Electron/Tauri (web frontend + bundle size/toolchain, and the Python backend would need a sidecar server) |
| Packaging | **PyInstaller `--onedir`** | one-file is slow to start; a `ball.buddy/` folder with `ball.buddy.exe` is the distribution unit. Charts: Qt-native or pyqtgraph (evaluate at M2, keep matplotlib as fallback) |
| Yahoo access | **`yffapi` (or `pyffl`) behind an internal adapter** (002_yahoo). Official OAuth2 browser flow for auth; the library handles the unofficial `sport-fantasy` JSON endpoints. One adapter module isolates endpoint breakage | faster + more reliable than bespoke; the library is the maintained layer, the adapter is the seam |
| Player projections | **Hashtag import-v4 pool** (salvaged importer), *not* Yahoo data | division of labor: **Yahoo = who is where** (rosters, moves, standings, schedule, waiver wire); **pool = how good players are** (per-game projections + z-scores). Bridged by player name (see risk R3) |
| Persistence | Local JSON (state versioned, atomic writes — salvage the AutoDraft `state.py` pattern) | v1 scale; SQLite only if a later phase needs query power |

## 4. Architecture

One process: the PySide6 app calls domain modules directly (no HTTP layer —
the FastAPI/web frontend from AutoDraft is discarded). Layering is strict so
domain code stays testable headless (all tests run without Qt):

```
UI (PySide6 widgets)  →  services (sync, advise, optimize)  →  domain (league,
engine, pool, board)  →  I/O adapters (yahoo client, pool CSV, state JSON)
```

### Components (doc-structure dirs, created when first planned)

| Dir | Responsibility |
|---|---|
| `000_app` | App shell: PySide6 bootstrap, window/nav layout, settings (league, pool import, auth), PyInstaller spec + packaging. |
| `001_data` | Player projection pool: Hashtag import-v4 importer + `players.csv` (salvaged from AutoDraft `001_data`), name-normalized lookup. |
| `002_yahoo` | Yahoo client: OAuth flow, `yffapi`-backed adapter (league, rosters, box scores, standings, schedule, waiver wire, moves), auth state on disk, manual-entry fallback surface. |
| `003_league` | League/roster model: teams, roster slots/eligibility, lineups, schedule, standings; Yahoo state → typed domain (superset of salvaged AutoDraft `002_league` — that one is draft-time oriented). |
| `004_engine` | Winrate engine: category projection, variance, matchup win-prob, per-category gap analysis (§5). Salvaged z-score/needs math as the projection substrate. |
| `005_advisor` | Decision levers: waiver advisor (FA rankings w/ winrate impact), lineup optimizer (daily start/sit), trade analyzer (later phase). |
| `006_board` | Draft-day board — **first feature (M2)**: snake/keeper pick tracking + recommender (salvaged `003_board` + `004_engine` ValueGapScorer), bulk keeper entry (all 24, with per-keeper opt-out), pool-based value rankings. Gated behind a "draft mode" in the UI. |

## 5. Winrate engine (the core)

**Inputs:** my roster + opponent roster (003), player projections (001),
opponent schedule context.

1. **Category projection.** For each team and each category: projected
   per-week value = Σ over the *roster* (not just the active set) of per-game
   rate × games, scaled by games-per-week — with a roster-capacity/lineup-shape
   adjustment so projections reflect realistic daily usage, not "start
   everyone every day." Percentage categories (FG%, FT%) use the
   volume-weighted mean (salvaged AutoDraft Phase 4a fix — a 3889.3% bug is
   not coming back).
2. **Variance.** Per-category uncertainty per player from historical weekly
   variance where available (own-league box-score history once 002_yahoo can
   pull it; before that, a league-wide per-category relative-variance prior
   calibrated on the pool). TO projects inversely (win if *lower*).
3. **Matchup.** Weekly Monte-Carlo: sample both teams' 9 category values
   independently per category, count categories won (tie-break per Yahoo),
   aggregate → P(win vs. this opponent) over the remaining season or the next
   N weeks. Deterministic gap mode (point estimates only) for fast UI feedback;
   MC for the headline number.
4. **Outputs the UI shows:** headline win-prob vs. each opponent (and season
   winrate), a 9-category bar (projected gap per category, colored by
   advantage/disadvantage), and the *marginal* contribution of each rostered
   player to each category gap — this last table is what the advisors in §6
   optimize against.

## 6. The levers (MVP features)

### 6.1 Waiver advisor
Rank every waiver-wire candidate (from 002_yahoo) by **projected impact on
winrate**: simulate adding the player (with the forced drop the roster slots
imply), re-run the engine for the relevant window, ΔP(win) against the
schedule — recent opponents weighted more heavily than the full season.
Output: ranked list with the category(s) moved, the drop forced, and the net
Δ. A plain "value rank" (salvaged market-value/z logic) is the secondary
column.

### 6.2 Lineup optimizer (per day)
For each day of the week: choose the legal active lineup (slot constraints,
position eligibility) maximizing P(win) vs. that day's opponent, driven by
**opponent-specific category targeting** — categories where the engine shows
the tightest gaps get the players with the best projected edge in *that*
category (the 78% FT shooter when the game is decided at FT%, etc.). Solver:
greedy construction + local search (full enumeration is fine at 8–9 starters;
revisit if the league uses larger actives). Output: recommended active set per
day, with the 2–3 highest-leverage substitutions explained ("start X over Y:
+4.1% P(win), category: FT%"), and a **crucial-players flag** for bench
players whose absence swings the projection (injury awareness).

### 6.3 Trade analyzer (later phase)
Same engine, both sides: ΔP(win) for each team after the swap, the
category-by-category before/after, and a fairness flag. No MVP commitment.

## 7. Phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **M0** | Scaffold: `/init-docs` repo per doc-structure, `pyproject.toml`, PySide6 skeleton (main window + nav), PyInstaller onedir build producing a runnable exe, pytest/ruff green on the shell | exe runs; local verify commands documented in AGENTS.md |
| **M1** | 002_yahoo + 003_league + 001_data: OAuth login, sync league/teams/draft order/schedule, JSON snapshot persisted; pool import in-app (Hashtag salvage) | login→sync works against the real league; pool loaded with matched names; stale/offline fallback shows last snapshot |
| **M2** | **006_board draft mode (first feature, §1.2)**: snake draft board with keeper-aware forfeited picks, bulk keeper entry (24 keepers, per-keeper opt-out), pick-by-pick live tracking, pool-based value recommender (salvaged `003_board` + ValueGapScorer) | board correctly shows the 12-team snake with all forfeited keeper picks; keeper entry round-trips; recommender rankings sane on the real pool |
| **M3** | 004_engine: matchup view (headline P(win), 9-cat gap bars, player marginal table) | the matchup screen is correct by hand-check on one real week |
| **M4** | 005_advisor waiver ranking (§6.1) | ranked list with ΔP(win) per candidate |
| **M5** | 005_advisor lineup optimizer (§6.2), per-day | daily recommendations + explanations |
| **M6** | Trade analyzer (§6.3) | — |
| **M7** | Packaging polish: installer-grade exe folder, icon, settings reset, error UX | hand to a friend; it works |

M2 is the first thing the user opens (this draft). M3–M5 = "the app I open every week." M6–M7 are explicitly secondary.

## 8. Salvage from AutoDraft (`N:\LLM\projects\autodraft`, untouched)

Copied **verbatim as a starting point** (plus their tests, re-parented):

| From | To | Notes |
|---|---|---|
| `agents/info.md` | new `agents/info.md` | extend with weekly-matchup concepts |
| `autodraft/importer.py`, `scripts/convert_hashtag.py`, `tests/test_importer.py`, `tests/test_convert_hashtag.py`, `tests/fixtures/hashtag_sample.html` | 001_data | unchanged; pool is still Hashtag import-v4 |
| `autodraft/league.py`, `autodraft/config.py`, `tests/test_league.py` | 003_league base | draft-time model; 003_league extends it with lineups/schedule/standings |
| `autodraft/state.py` (+tests) | 000_app or 003_league | atomic versioned JSON persistence pattern |
| `autodraft/engine/scoring.py` z-pool model + TO-sign handling, `autodraft/needs.py` | 004_engine substrate | the ValueGapScorer itself moves with 006_board (draft mode) |
| `autodraft/board.py` (+tests) | 006_board | draft-day — first feature (M2) |

**Discarded:** the FastAPI backend, the entire `static/` frontend, the
`session.json` user-team concept (replaced by auth), the README quick-tour
(rewritten for desktop).

## 9. Risks

- **R1 — Yahoo endpoint breakage.** Unofficial JSON endpoints + no SLA.
  Mitigation: single adapter module (002_yahoo), pinned library version,
  persisted JSON snapshots keep the app useful offline, manual-entry fallback
  for the one number that matters (opponent lineup changes).
- **R2 — Auth lifecycle.** Yahoo OAuth tokens refresh silently; the app must
  detect expiry gracefully and re-prompt with the browser flow, never crash.
- **R3 — Name bridging.** Yahoo roster names vs. Hashtag pool names will not
  always match (surnames-only entries, typos, new players). The pool importer
  must surface *unmatched* roster players loudly (they project as zeros and
  silently break the engine). A small curated alias table (editable JSON) is
  the v1 fix.
- **R4 — Projection horizon.** Pool projections are season-long; weekly
  leverage is about *next week*. v1 accepts season averages + in-league
  recency adjustment from box scores (M2+); flagged as a known bias.
- **R5 — PyInstaller/Qt + Python 3.14.** Young runtime; pin exact PyInstaller +
  PySide6 versions in M0 and re-verify the build each major upgrade.

## 10. Open questions (resolve at the stated phase, not before)

1. Charts: pyqtgraph vs. native Qt vs. matplotlib-embedded — decide in M2
   when the gap bars need real geometry.
2. Lineup optimizer active-size: confirm the league's active count/lineup rules
   from the real league (003_league reads them from Yahoo anyway).
3. Box-score history depth available via `yffapi` for variance calibration —
   probe in M1; if thin, fall back to pool-relative-variance priors.
4. Matchup-level tie-break rule (Yahoo default vs. season head-to-head record) — confirm with commissioner (§1.1 open items); make configurable in 004_engine, default Yahoo.
5. Trade deadline date and exact transaction cutoff time — read from Yahoo league settings at M1 sync.
