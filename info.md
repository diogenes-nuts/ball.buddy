# Agent Brief: Fantasy Basketball for a Yahoo 9-Cat Snake Draft Tool

**Agent reading this:** You are assisting with the design, build, or operation of a tool for a Yahoo Fantasy Basketball league. The league uses **standard 9-category scoring**, **2 keepers per team**, and a **snake draft**. Treat this document as your domain model. When actual Yahoo league settings differ, defer to the league settings and ask the user.

---

## 1. What Fantasy Basketball Is

Fantasy basketball is a virtual general-manager game. Participants draft real NBA players onto fantasy teams. Each real NBA player's on-court statistics are converted into fantasy points or categories. Fantasy teams compete against each other based on those statistics.

A Yahoo fantasy basketball league typically includes:

- A commissioner who configures league settings.
- 8–20 fantasy teams, commonly 10–14.
- A draft before the NBA season.
- Weekly head-to-head matchups or season-long roto standings.
- Daily or weekly lineup setting.
- Add/drop, waivers, trades, and playoffs.

The goal is to build a roster that performs well across the league's scoring categories and win matchups or accumulate the best season-long rank.

---

## 2. League Profile Assumed Here

| Setting | Value |
|---|---|
| Platform | Yahoo Fantasy Basketball |
| Scoring | Standard 9-category |
| Format | Head-to-Head: Each Category |
| Draft | Snake draft |
| Keepers | 2 per team, with round cost |
| Lineups | Daily |
| Roster | Yahoo default (see Section 4) |
| FAAB Budget | $100 |
| Transaction Processing | Nightly |
| Pick Timer | 60 seconds |
| Draft Rounds | 13 |

**Important:** This is a Head-to-Head Categories league. Each week, two fantasy teams are compared across nine categories, and the team that wins more categories wins the matchup.

---

## 3. Standard 9 Categories

Each week, two fantasy teams are compared across nine categories. The team that wins more categories wins the matchup. Each category is a separate win, loss, or tie.

| Category | Abbrev. | What It Measures | Better Direction |
|---|---|---|---|
| Field Goal Percentage | FG% | Made field goals ÷ attempted field goals | Higher |
| Free Throw Percentage | FT% | Made free throws ÷ attempted free throws | Higher |
| Three-Pointers Made | 3PTM / 3PM | Total made three-point shots | Higher |
| Points | PTS | Total points scored | Higher |
| Rebounds | REB | Total rebounds | Higher |
| Assists | AST | Total assists | Higher |
| Steals | STL | Total steals | Higher |
| Blocks | BLK | Total blocks | Higher |
| Turnovers | TO | Total turnovers | **Lower** |

### Critical Agent Notes

- **TO is a negative category.** Lower is better. Never treat turnovers as a positive stat.
- **FG% and FT% are percentages, not totals.** A player who makes 1/1 free throws has 100% FT% but very low volume. Volume matters.
- **3PTM is makes, not attempts or percentage.** Do not confuse it with 3PT%.
- Category scarcity matters: elite blocks and steals are rare; points and rebounds are more abundant.
- Punting is a common strategy: intentionally sacrificing one or two categories to dominate the others. TO and FT% are common punt categories.

---

## 4. Yahoo Default Roster and Lineup

This league uses the **Yahoo default basketball roster**, which is:

| Slot | Count | Eligibility |
|---|---|---|
| PG | 1 | Point Guard |
| SG | 1 | Shooting Guard |
| G | 1 | PG or SG |
| SF | 1 | Small Forward |
| PF | 1 | Power Forward |
| F | 1 | SF or PF |
| C | 1 | Center |
| Util | 3 | Any position |
| BN | 3 | Bench |

**Total active slots:** 10 (7 position-specific + 3 Util).  
**Total roster size:** 13 (10 active + 3 bench).

Players can have multi-position eligibility, such as `PG,SG` or `SF,PF`. Yahoo updates eligibility during the season. Multi-position players are valuable because they fit more lineup slots.

### Transaction Settings

| Setting | Value |
|---|---|
| FAAB Budget | $100 per team for the season |
| Transaction Processing | Nightly |
| Waiver Mode | FAAB (Free Agent Acquisition Budget) |

**Agent note:** With nightly processing, adds/drops and waiver claims are not immediate. The tool should be aware that roster moves submitted during the day resolve overnight. FAAB bids are blind, so competing managers do not see each other's bids until processing.

---

## 5. How Head-to-Head Categories Work

Example weekly matchup:

| Category | Team A | Team B | Winner |
|---|---:|---:|---|
| FG% | .487 | .462 | Team A |
| FT% | .810 | .790 | Team A |
| 3PTM | 42 | 55 | Team B |
| PTS | 520 | 498 | Team A |
| REB | 180 | 210 | Team B |
| AST | 130 | 115 | Team A |
| STL | 35 | 40 | Team B |
| BLK | 22 | 18 | Team A |
| TO | 70 | 65 | Team B |

Result: Team A wins 5 categories, Team B wins 4. Team A wins the matchup 5–4.

Standings are usually based on total category wins, not just matchup wins. This makes every category matter, even in a losing week.

---

## 6. Snake Draft Mechanics

In a snake draft, the draft order reverses each round.

Example for a 12-team league:

| Round | Pick Order |
|---|---|
| Round 1 | Team 1 → Team 12 |
| Round 2 | Team 12 → Team 1 |
| Round 3 | Team 1 → Team 12 |
| Round 4 | Team 12 → Team 1 |

So Team 1 picks at overall picks 1, 24, 25, 48, 49, etc. Team 12 picks at 12, 13, 36, 37, etc.

### Key Draft Concepts

- **Draft order:** Set by Yahoo randomizer, commissioner, or previous season standings.
- **Rounds:** 13 rounds, matching total roster size.
- **Pick timer:** 60 seconds per pick.
- **Autopick:** If a manager misses a pick, Yahoo can auto-select from pre-ranked players.
- **Draft board:** The tool should track every pick, team, round, and overall pick number.

---

## 7. Keepers in a 2-Keeper League

Each team may keep **2 players** from the previous season. Keepers are removed from the draft-eligible player pool. **In this league, keepers have a round cost**, meaning each kept player consumes a specific draft round/pick.

### How Round-Cost Keepers Work

Each keeper is assigned to a draft round, typically based on one of these models:

| Model | Description |
|---|---|
| Previous draft round | Player costs the round he was drafted in last season. |
| Round + penalty | Player costs his previous round plus 1 or more rounds. |
| Fixed round | Commissioner assigns a fixed round to each keeper. |
| Undrafted free agent rule | Undrafted keepers cost a default late round. |

When a keeper is declared, that team's pick in the corresponding round is forfeited. The player is removed from the draft pool.

### Agent Directives for Keepers

- **Do not assume keeper cost.** Confirm the exact round assigned to each keeper.
- Track which team keeps which player and in which round.
- Remove kept players from the available pool.
- Mark forfeited picks on the snake draft board so the tool does not assign them to a player.
- If a team forfeits a pick, the snake order still advances; only that specific pick is consumed.
- Yahoo may display keepers before or during the draft. If the API does not provide them in real time, allow manual entry.
- Keeper decisions affect draft strategy: a keeper in an early round reduces that team's access to elite talent in that round.

---

## 9. Draft Strategy Concepts the Agent Should Know

| Concept | Meaning |
|---|---|
| VBD / VORP | Value over replacement. Compares a player to the best freely available replacement at his position. |
| Z-score | Converts each category into a standardized value so categories can be compared. |
| Punt | Intentionally ignoring a category to build a stronger team in the other eight. |
| Scarcity | Some stats are concentrated in few players. Blocks and steals are often scarce. |
| Positional run | When many players at one position are drafted in a short span. |
| Sleeper | A player drafted later than his expected value. |
| Bust | A player drafted earlier than his actual production. |
| Streaming | Adding/dropping players to maximize games played in a week. |
| Schedule | Teams with more games in a week can provide more counting stats. |
| ADP | Average Draft Position. See below. |
| Pre-Draft Rankings | Analyst or site-specific ordered lists. See below. |

### ADP (Average Draft Position)

**ADP** is the average overall pick at which a player is selected across many drafts. If a player has an ADP of 24.5, he is typically taken around pick 24 or 25 in a 12-team league. ADP is a market signal: it reflects where the broader fantasy community values a player.

**Key properties of ADP:**

- ADP is **descriptive, not prescriptive**. It tells you where players *have been* drafted, not where they *should* be drafted.
- ADP varies by source. Yahoo ADP reflects Yahoo drafts only. FantasyPros aggregates across many platforms. ESPN ADP reflects ESPN drafts. Each has a different user base and therefore different biases.
- ADP is **format-dependent**. A 9-cat H2H league with 2 keepers will produce different ADP than a points league or a roto league. Punt-heavy builds and category scarcity shift player values.
- ADP is **time-sensitive**. Early-offseason ADP is heavily influenced by last season's stats. As news, injuries, trades, and training camp reports emerge, ADP shifts.
- **ADP is not a ranking.** A player can have a high ADP because he is a popular name, not because he is the best value at that pick. Conversely, a low-ADP player may be a strong value if your build needs his category profile.
- **Reach vs. value:** Drafting a player earlier than his ADP is a reach; drafting him later is a value. Reaches are not inherently bad if the player fits your build and would not survive until your next pick.
- **ADP arbitrage:** Identifying players whose ADP is much lower than their projected value is a core draft edge. So is identifying players whose ADP is inflated by hype or name recognition.

### Pre-Draft Rankings from Different Sources

**Pre-draft rankings** are ordered lists published by analysts, sites, or platforms before the draft. Unlike ADP, rankings are **opinionated**: they reflect what the ranker believes player values *should* be.

Common sources:

| Source | Notes |
|---|---|
| Yahoo | Default rankings used for autopick if a manager does not pre-rank. Reflects Yahoo's analysts and default settings. |
| ESPN | ESPN analysts; different biases and category weights than Yahoo. |
| FantasyPros | Aggregates expert rankings into consensus ranks; also offers ADP and tiered rankings. |
| Hashtag Basketball | Strong for category-league rankings and z-score-based values. |
| Basketball Monster | Category-league focused; provides projection-based rankings and punt builds. |
| Rotowire / Rotoworld | News-driven rankings, often updated quickly for injuries and role changes. |

**Key properties of pre-draft rankings:**

- Rankings are **format-specific**. A ranking built for points leagues is not directly transferable to 9-cat H2H.
- Rankings reflect **the ranker's assumptions** about minutes, roles, health, and team context. When those assumptions break, rankings break.
- Rankings differ from ADP because rankings are prescriptive and ADP is descriptive. A large gap between a player's ranking and ADP is a signal worth investigating.
- **Consensus rankings** (e.g., FantasyPros) smooth out individual analyst bias but can lag on fast-moving news.
- **Tiered rankings** group players by projected value, which is often more useful for drafting than a strict 1-through-200 list, because the drop-off between tiers is where value is won or lost.
- For a **keeper league with round costs**, rankings and ADP must be adjusted: a player kept at a discount is more valuable than his raw ranking suggests, and a player kept at a premium is less valuable.

### Agent Directives for Recommendations

- State your assumptions clearly.
- Separate facts from projections.
- Never recommend a player without considering team build, category needs, and keeper rules.
- For 9-cat, always treat TO as negative.
- For FG% and FT%, consider both percentage and volume.
- Prefer current-season data, injury reports, and depth-chart news.
- If the user is punting a category, adjust rankings accordingly.
- Warn when a recommendation conflicts with a keeper decision.
- When citing ADP, specify the source (Yahoo, ESPN, FantasyPros, etc.) and the date, since ADP shifts.
- When citing rankings, specify the source and whether they are category-league specific.
- Flag large ADP-vs-ranking gaps as potential value or trap.

---

## 10. Example: 12 Teams, 13 Rounds, 2 Keepers, Round Cost

Assume 12 teams and 13 roster spots per team, matching this league's Yahoo default roster.

### Roster Math

- Total roster spots: 12 teams × 13 spots = **156 players**.
- Each team keeps **2 players**: 12 × 2 = **24 keepers**.
- Available players for the draft: 156 − 24 = **132**, assuming no other roster changes.
- Because keepers cost rounds, each team forfeits **2 draft picks** — one in each round corresponding to a keeper's cost.
- Each team still drafts **11 players** across the 13 rounds; the other 2 rounds are consumed by keepers.

### Draft Board Implications

- The snake order still runs for all 13 rounds.
- Picks forfeited to keepers are marked as **used** and are not assigned to a new player.
- If a keeper costs Round 1, that team does not pick in Round 1. The snake order still advances; the next team picks.
- If a team's two keepers cost, say, Round 3 and Round 7, that team has no pick in Round 3 or Round 7 but picks normally in all other rounds.
- The tool must display, for each team, which rounds are forfeited and which remain.

### Example Keeper Cost Table

| Team | Keeper 1 | Cost Round | Keeper 2 | Cost Round | Forfeited Picks |
|---|---|---|---|---|---|
| Team 1 | Player A | 2 | Player B | 9 | R2, R9 |
| Team 2 | Player C | 1 | Player D | 5 | R1, R5 |
| Team 3 | Player E | 4 | Player F | 11 | R4, R11 |
| ... | ... | ... | ... | ... | ... |

The tool should derive this table from commissioner input or Yahoo league data, then apply it to the live draft board.

### Strategy Implications

- A team that keeps an elite player at a late-round cost gains a large surplus of value.
- A team that keeps a player at an early-round cost gives up access to elite talent in that round.
- **Keeper cost changes ADP math.** A player's ADP may be Round 2, but if you can keep him at Round 8, his effective value is far higher than his ADP suggests.
- **Pre-draft rankings should be adjusted for keeper surplus.** Rankings built for redraft leagues do not account for the round-cost discount.
- With 13 rounds and 2 keepers costing rounds, the draft effectively has 11 live picks per team. Plan tiers accordingly: the drop-off between your Round 6 and Round 7 picks matters more when you have fewer total picks.

---

## 11. Data Sources and Integration Notes

| Source | Use |
|---|---|
| Yahoo Fantasy Sports API | League settings, teams, rosters, players, draft results |
| NBA Stats API | Official NBA statistics |
| Basketball Reference | Historical stats, advanced stats |
| FantasyPros | Consensus rankings, ADP, projections |
| Hashtag Basketball | Category-league rankings, z-score values |
| Basketball Monster | Category-league projections, punt builds |
| Rotowire / ESPN / Yahoo | Injury news, depth charts, ADP by platform |
| Yahoo OAuth 2.0 | Authentication for private league data |

**Agent note:** Yahoo API access is OAuth-based. Live draft data may not be fully available through the API. The tool should support manual draft entry or a browser-assisted sync if needed. Always comply with Yahoo's terms of service. When citing ADP or rankings, always specify the source and date, since both shift throughout the offseason and preseason.

---

## 12. Glossary

- **ADP:** Average Draft Position. The average pick at which a player is drafted across many drafts; descriptive, not prescriptive.
- **BN:** Bench.
- **Category:** A statistical scoring area, such as REB or AST.
- **FAAB:** Free Agent Acquisition Budget. Blind bidding system for free agents; this league uses $100 per team with nightly processing.
- **FG%:** Field Goal Percentage.
- **FT%:** Free Throw Percentage.
- **H2H:** Head-to-Head.
- **IR:** Injured Reserve.
- **Keeper:** A player retained from the previous season, often at a round cost.
- **Pre-Draft Rankings:** Analyst- or site-published ordered lists reflecting opinionated player values; prescriptive, not descriptive.
- **Punt:** Intentionally ignoring a category.
- **Roto:** Rotisserie; season-long category ranking.
- **Snake Draft:** Draft order reverses each round.
- **TO:** Turnovers; lower is better.
- **Util:** Utility slot; any position.
- **VORP / VBD:** Value Over Replacement Player / Value-Based Drafting.
- **Z-score:** Standardized category value.

---

## 14. Final Agent Summary

You are supporting a Yahoo fantasy basketball draft tool for a **standard 9-category, head-to-head, 2-keeper, snake draft** league with **round-cost keepers**.

League specifics to remember:

- **Format:** Head-to-Head Categories.
- **Roster:** 1 PG, 1 SG, 1 G, 1 SF, 1 PF, 1 F, 1 C, 3 Util, 3 BN — 13 total.
- **Draft:** 13 rounds, snake, 60-second pick timer.
- **Keepers:** 2 per team, each with a round cost that forfeits the corresponding pick.
- **FAAB:** $100 budget, transactions processed nightly.
- **Scoring:** Standard 9-cat, with TO as a negative category.

Your core responsibilities are:

1. Understand the 9 categories and their directions.
2. Respect Yahoo roster and position eligibility.
3. Track keepers, their round costs, and forfeited picks.
4. Maintain an accurate snake draft board across 13 rounds.
5. Recommend players using value, scarcity, category needs, and punting strategy.
6. Distinguish ADP (descriptive, source-specific) from rankings (prescriptive, opinionated), and adjust both for keeper round-cost surplus.
7. Ask for missing league settings instead of assuming.
8. Distinguish data from projections.
9. Comply with Yahoo API terms and user privacy.

When in doubt, ask the user for the exact Yahoo league settings.