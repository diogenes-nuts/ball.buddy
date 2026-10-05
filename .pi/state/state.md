# State — ball.buddy: M1 live check — crash fixed+tested, 403 wall reported; awaiting user decision (apply vs offline)
(Rewrite this whole file at every checkpoint. Never append. If a fact
no longer matters, delete it — git history keeps the trail.)

"Told" = user has heard this from you in plain words. Reading it in a log
does not count.

## Status
- Position: ROADMAP done + on GitHub (public, diogenes-nuts/ball.buddy, main; last commit 46db628). **All fixes this iteration shipped: 272 passed + 1 skipped, ruff clean, exe REBUILT, docs updated.** User told: crash root cause + fix, 403 wall (yfpy #84 legacy-app read-access removal), options (apply at sports.yahoo.com/developer / offline mode / wait). **Awaiting user response**: they may (a) try the fixed exe's Sync (now shows clean "Sync failed: Yahoo has blocked this app's fantasy access (403...)" banner — NOT a crash, NOT a false re-sign-in prompt); (b) go apply to the gated program; (c) pick offline mode; (d) report fresh errors.
- **Done this turn (all committed? NO — uncommitted since 46db628):** 1) sync crash fix (league.py: store-first `_store_sync_result` + `thread.finished -> _on_sync_thread_done`; old code `thread.wait()` in queued slot = deadlock; proven: reintroduced bug -> regression test hangs, fixed -> passes in 0.3s); 2) regression test `tests/ui/test_league_view.py::test_sync_now_thread_round_trip` + `_spin_until` pump helper; 3) client.py `_call`: 403 "application is not authorized" -> distinct `YahooError` app-ban message (was mis-mapped to "sign in again") + test `test_403_app_ban_maps_to_yahoo_error_not_relogin`; 4) docs: 002_yahoo/status.md (403 mapping, JWT token fact, yfpy #84 wall, sync-thread pattern note).
- **If user applies to gated program and gets approval/creds:** new client may need re-sign-in (new client id/secret); flow already supports confidential clients (Basic auth) so nothing else to build. If offline mode: M1 items 3-4 (pool import from N:\LLM\projects\autodraft\data\hashtag_import.html, manual order, offline banner) work with zero Yahoo data — M1 "12 real teams" item is impossible until API access returns; note that in any M1 sign-off.
- **LEFT:** nothing code-side. On user's next message: diagnose accordingly. Before any exit/commit: verify data/ (tokens) never lands in git (it's gitignored; dist/data also outside repo tree). Do NOT git commit manually.
- User env note (told no): harness bash `timeout` unreliable (150s cap ran 14 min) — self-limit via in-process watchdog (threading.Timer->os._exit) <=30s.

## What's in the tree (uncommitted since 46db628)
- **oauth.py (NEW)**: in-app OAuth 2.0. https loopback https://localhost:8480/callback (console requires https) + http fallback; ensure_loopback_cert (RSA-2048 SHA256 10y, data/oauth_{cert,key}.pem); _ThreadingHTTPServer (ssl BEFORE super().__init__); LocalCallbackServer ONE-SHOT (2nd GET->400) + code_verifier + wait(0); new_pkce (S256); build_authorize_url (client_id required + PKCE challenge); begin_sign_in(data_dir,key,secret=""); complete_exchange/exchange_code(+verifier); refresh_access_token (redirect https://www.yahoo.com); _token_request (secret->Basic else body client_id); extract_guid (JWT sub); new_token_dict (guid best-effort); parse_paste.
- **client.py**: from_tokens key-required/secret-optional; yfpy placeholder "public"; _TOKEN_FIELDS excludes consumer_secret+guid; _call: 403-ban -> YahooError, token words -> LoginRequiredError, else YahooError.
- **sync.py**: _live_tokens fresh<3240s else refresh; sign_in_ready KEY-ONLY; save_sign_in; run() maps errors to SyncResult (needs_login vs error banner).
- **league.py**: SignInDialog + SyncWorker both store-first/thread.finished (no wait() in queued slots).
- tests: 272 passed + 1 skipped. docs: README (public client/blank secret/PKCE/https callback), 002_yahoo/status.md current.
- **dist/data (gitignored):** settings.json (league_id 847, long consumer_key, secret ""); yahoo_tokens.json (JWT token, guid "", bearer); oauth_{cert,key}.pem.
- Repro scripts deleted. /tmp/league_fixed.py leftover (harmless).

## Verification
- 272 passed + 1 skipped + ruff clean + exe rebuilt (this turn, final).
- Regression test PROVEN meaningful: with wait() bug reintroduced -> test hangs >60s (main loop blocked, even its own deadline can't fire); with fix -> 0.3s pass.
- Live probes: refresh 200 (fresh 1036-char JWT); fantasy metadata 403 app-not-authorized (fresh token) / 401 token_expired (stale).
- Minimal PySide6 pattern test: PASS (deleted).

## Findings
- Sign-in end-to-end works incl. persistence (told yes). Flashing dialog = sign-in dialog closing (told yes, benign).
- Sync crash = wait()-in-queued-slot deadlock (frozen exe = hard crash, no app.log); fixed + proven (told yes).
- **Yahoo 403 wall = platform-wide legacy-app read-access removal (yfpy #84, since ~2026-07-22); create-app form no longer offers Fantasy Sports permission; gated program at sports.yahoo.com/developer; our probes confirm (fresh JWT token still 403s)** (told yes — reported this turn).
- Fresh token = real ~1KB JWT (1h); refresh grant works public-client style (client_id body, redirect https://www.yahoo.com) (told in report).
- (carried) Public/PKCE (told yes); MhNtBgeJ=App ID (told yes); client_id param (told yes); https callback (told yes); harness timeout unreliable (told NO).
- League facts: 14=10+3BN+1IR; 24 keepers; FAAB $100 3 adds/wk; daily lineups; top-4 playoffs 2 byes SE; pure 9-cat. Open: 4-4 tie-break, trade deadline.
- Stack: Py 3.14.7, PySide6 6.11.2, yfpy 17.0.0, cryptography 50.0.2, requests 2.32.5, pytest 9.1.1, ruff 0.16.10, pyinstaller 6.22.3 (FORWARD slashes, -y).

## U-turns
- (carried) Confidential->Public/PKCE; data dir above exe; in-app OAuth; https callback; two-phase begin/complete; SPEC lib->yfpy.
- "crash = unexplained hard abort" -> wait()-in-slot deadlock (told yes). "need JWT fix on our side" -> tokens already JWT; 403 upstream (told yes). "403 = dead token" -> app ban, distinct error (told yes).

## Dead ends
- (carried) yahoo_oauth browser flow in --windowed; contextlib.redirect_stdout; user data in onedir; edit() non-ASCII oldText; pyinstaller backslashes; MainWindow() w/o QApplication; plain-http callback; ssl after init; modal in __init__.
- Bash `timeout` (14-min overrun) — in-process watchdog (told NO).
- GUI-level monkeypatched instance-slot repros (self-contradictory) — minimal standalone (told NO).
- scope/PKCE/refresh tweaks to cure 403 — upstream policy (told yes).

## Goal (latest user requests, verbatim)
"Sign-in appears to have worked. An app dialog popped up but disappeared before I could read it. Clicking \"Sync now\" crashes the app." / "Timeout 150s but it ran for 14 min"
