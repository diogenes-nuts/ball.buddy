# 007_webui — status

M8 migration: replace the PySide6 UI with an Electron + vanilla-TypeScript frontend,
keep the Python core unchanged behind a FastAPI sidecar. **Planned, not started.**
The Python core (`domain/`, `io/`, `services/`) is UI-agnostic and never changes
behavior in this migration; `ball_buddy/ui/` (~4,000 lines, all Qt) is replaced
wholesale and deleted at Phase 5.

Style is re-oriented around the `app-ui-design` skill: its `tokens.css` is the single
source of truth (light default, `data-theme` override + `prefers-color-scheme`). All
prior style decisions are discarded — QSS, `theme.py` palettes, tactile-cream-ui
tokens, stat-color QSS workarounds.

Decisions (2026-10-15, user): Electron over Tauri (one language, trivial sidecar
spawn, no Rust); Python core kept behind an API (no TS rewrite); vanilla TS + Vite
frontend (no framework); FastAPI + uvicorn sidecar; clipboard-paste OAuth fallback
dropped (loopback redirect via the existing `begin_sign_in` local https callback
server in `ball_buddy/io/yahoo/oauth.py`); pure feature port (same 6 views); packaging
shape unchanged (onedir exe in `dist\ball.buddy\`).

Files: none yet. The full phase plan (0 prep → 1 API server → 2 Electron shell →
3 frontend foundation → 4 six view ports → 5 parity + deletion → 6 packaging), with
exit criteria and risks, lives in `dev.md`. Parity reference: git tag `v1-pyside`
(created at Phase 0).
