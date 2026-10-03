# 005_advisor — status

- **M4.1 (done, headless):** `ball_buddy/domain/waiver.py` ranks waiver candidates by ΔP(win) via `domain/engine.py` reuse (baseline + per-candidate exact best-drop counterfactuals, deterministic `mc=False` cat_delta, rationale, FAAB over-budget flag, loud `ValueError` on any unresolved pool name).
- No wire data: candidates/roster/opponent are pool names bridged upstream (e.g. via `domain/naming.py`); `PlayerPool` is fixture- or manual-constructed.
- No Qt, no new deps; tests in `tests/domain/test_waiver.py` (trials=50, pinned seed).
- Not yet surfaced in the UI; board wiring is a later milestone.
