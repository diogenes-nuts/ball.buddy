# ball.buddy

A FantasyNBA 9-category assistant for your Yahoo league.

It gives you one window for the whole season: a draft-day board, weekly
matchups, waiver rankings, lineup start/sit recommendations, and a trade
analyzer — all driven by a live sync with your Yahoo league.

## Run it

**No Python needed.** Double-click:

```
dist\ball.buddy\ball.buddy.exe
```

(Developers: create a venv, install the pins from `pyproject.toml`, then run
`python -m ball_buddy.main` — see `AGENTS.md` for exact commands.)

All app data lives in `data/` one level above the app folder (next to the
`ball.buddy` folder, e.g. `dist\data`): settings, your Yahoo login tokens,
the imported player pool, the last league snapshot, keepers, and entered
draft picks. Deleting the app folder never touches your data; delete `data/`
to start completely fresh.

## First run (5 minutes)

1. **League → Settings** — enter your Yahoo **client id** (the long
   "Client ID (Consumer Key)" string; create a free app at
   https://developer.yahoo.com/apps/) and your league id (the number in your
   Yahoo league URL, `.../nba/default/league/<id>`). Save.
   **Secret:** if the app was created as a **Public** client ("OAuth Client
   type: Public" — the new console's default), there is no secret — leave the
   secret field **empty** (the app signs in with PKCE). Confidential clients
   paste their client secret in.
   **One-time setup:** in the Yahoo developer app, set the callback URI to
   `https://localhost:8480/callback` (your app → Yahoo settings; https is
   required).
2. **Sign in to Yahoo** — a browser window opens; complete the sign-in.
   If a **"Your connection is not private"** page appears, that's expected —
   the callback is served by this app on your own machine: click
   **Advanced → Proceed to localhost (unsafe)**. The app captures the code
   automatically afterwards. If the browser tab shows an error instead,
   click **Enter code manually** in the dialog and paste the URL from the
   browser's address bar (or just the code).
3. **Sync now** — your 12 teams, managers, draft order, and schedule appear.
   Before the draft the live order/schedule may be empty: that's normal. Use
   the up/down buttons in the Draft order pane + **Save order** to set a
   manual start order until Yahoo publishes one.
4. **Import pool** — pick a saved Hashtag "import v4" HTML file. Players
   that can't be matched are listed; add nicknames to `data/aliases.json`
   and import again if needed.

## Everyday notes

- **Offline banner?** Without network access (or after a token expires) the
  League page shows "Offline — showing last snapshot (synced <age>)". That is
  expected, not an error; reconnect and press **Sync now**.
- **Reset all data** is in League → Settings. It wipes *everything*,
  including your Yahoo login and the player pool — you'll sign in and import
  again.
- **Draft board** — enter your keepers, then enter picks as they're called;
  entered picks persist in `data/draft_picks.json`.
- **Lineups / Waivers / Trades** — these work best after at least one sync,
  so the engine has rosters to work with.

## If it crashes

You'll be told a log was written. Send **`data/app.log`** to the developer —
it contains the full error plus Qt warnings.
