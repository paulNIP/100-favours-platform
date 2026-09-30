# betPawa CM soccer markets

Markets that betPawa CM (`betpawa.cm`) offers for soccer (`sportId 10`), taken from the
OddsPapi export on 2026-09-30: 147 fixtures with odds across 27 tournaments,
73 distinct markets. Top European leagues had no fixtures that day, so they are
not represented.

Regenerate the data with `uv run odds-export --sport-id 10 --bookmaker betpawa.cm` (from the repo root)
(see `src/odds_service/scripts/export_odds.py`); files land in `data/odds/betpawa.cm/soccer/`.

"Fixtures" is how many of the 147 fixtures carry the market. "Lines" lists the
handicap / total values offered.

## Summary

| Group | Markets |
|---|---|
| Main (on nearly every fixture) | Full Time Result (1X2), Double Chance, Draw No Bet, Over/Under (0.5 to 8.5), Asian Handicap (-5.5 to +5.5), Odd/Even, Both Teams To Score, Team 1/2 Over/Under (0.5 to 5.5) |
| Half (about 120 fixtures) | First and second half: Result, Double Chance, Draw No Bet, Over/Under (0.5 to 3.5), Odd/Even, BTTS, Correct Score. Asian Handicap and Team Over/Under per half are rarer (about 52 and 31) |
| Team (Team 1 and Team 2) | Odd/Even, Win To Nil, Clean Sheet (full time and per half), Exact Score, To Score in Both Halves, To Win Both Halves, To Win Either Half, Highest Scoring Half |
| Specials | Half Time / Full Time, Winning Margin, Highest Scoring Half, First Goal, Last Goal, 2Up Full Time Result |
| Players (few fixtures) | Anytime Goal Scorer, Last Goal Scorer, Player To Be Carded |
| Corners (about 13 fixtures) | 1X2, Over/Under, Handicap, Odd/Even, each for full match and first half |
| Bookings (5 fixtures) | 1X2 and Over/Under, each for full match and first half |

No combo markets (such as 1X2 & Over/Under, or Double Chance & BTTS) are offered.
OddsPapi does not define any soccer combo markets, so this is a limit of the data
source, not of betPawa CM.

## All markets

| Market | Type | Fixtures | Lines |
|---|---|---|---|
| Full Time Result | `1x2` | 147 |  |
| Double Chance Full Time | `doublechance` | 145 |  |
| Draw No Bet | `drawnobet` | 144 |  |
| Asian Handicap | `spreads` | 143 | -5.5 to 5.5 (12 lines) |
| Over Under Full Time | `totals` | 143 | 0.5 to 8.5 (9 lines) |
| Odd Even Full Time | `oddeven` | 141 |  |
| Both Teams To Score | `bothteamsscore` | 140 |  |
| Over Under Team 1 | `teamtotals-team1` | 140 | 0.5 to 5.5 (6 lines) |
| Over Under Team 2 | `teamtotals-team2` | 140 | 0.5 to 5.5 (6 lines) |
| Team 1 Odd Even | `oddeven-team1` | 134 |  |
| Team 2 Odd Even | `oddeven-team2` | 134 |  |
| Team 1 Win To Nil | `wintonil-team1` | 133 |  |
| Team 2 Win To Nil | `wintonil-team2` | 129 |  |
| Team 1 Clean Sheet | `cleansheet-team1` | 126 |  |
| Team 2 Clean Sheet | `cleansheet-team2` | 125 |  |
| Winning Margin Full Time | `winningmargin` | 124 |  |
| Double Chance Second Half | `doublechance` | 123 |  |
| First Half Result | `1x2` | 123 |  |
| Half Time / Full Time | `halftime-fulltime` | 123 |  |
| Highest Scoring Half | `highestscoringh` | 123 |  |
| Odd Even First Half | `oddeven` | 123 |  |
| Odd Even Second Half | `oddeven` | 123 |  |
| Over Under First Half | `totals` | 123 | 0.5 to 3.5 (4 lines) |
| Over Under Second Half | `totals` | 123 | 0.5 to 3.5 (4 lines) |
| Second Half Result | `1x2` | 123 |  |
| Team 1 Exact Score Full Time | `exactscore-team1` | 123 |  |
| Team 2 Exact Score Full Time | `exactscore-team2` | 123 |  |
| Both Teams To Score First Half | `bothteamsscore` | 122 |  |
| Both Teams To Score Second Half | `bothteamsscore` | 122 |  |
| Double Chance First Half | `doublechance` | 122 |  |
| Team 2 To Score in Both Halves | `toscoreinbh-team2` | 122 |  |
| Draw No Bet First Half | `drawnobet` | 121 |  |
| Team 1 To Score in Both Halves | `toscoreinbh-team1` | 121 |  |
| Draw No Bet Second Half | `drawnobet` | 120 |  |
| Correct Score First Half | `correctscore` | 117 |  |
| Correct Score Second Half | `correctscore` | 117 |  |
| Team 1 To Win Both Halves | `winbothh-team1` | 112 |  |
| Team 1 Highest Scoring Half | `highestscoringh-team1` | 110 |  |
| Team 2 Highest Scoring Half | `highestscoringh-team2` | 110 |  |
| First Goal Full Time | `firstgoal` | 90 |  |
| Last Goal Full Time | `lastgoal` | 89 |  |
| Team 2 To Win Both Halves | `winbothh-team2` | 88 |  |
| 2Up - Full Time Result | `2up` | 83 |  |
| Team 1 To Win Either Halves | `wineitherh-team1` | 73 |  |
| Team 2 To Win Either Halves | `wineitherh-team2` | 73 |  |
| Asian Handicap First Half | `spreads` | 52 | -2.5 to 2.5 (6 lines) |
| Asian Handicap Second Half | `spreads` | 52 | -2.5 to 2.5 (6 lines) |
| Team 1 Clean Sheet First Half | `cleansheet-team1` | 51 |  |
| Team 1 Clean Sheet Second Half | `cleansheet-team1` | 51 |  |
| Team 2 Clean Sheet First Half | `cleansheet-team2` | 51 |  |
| Team 2 Clean Sheet Second Half | `cleansheet-team2` | 51 |  |
| Over Under Team 1 First Half | `teamtotals-team1` | 31 | 0.5 to 2.5 (3 lines) |
| Over Under Team 1 Second Half | `teamtotals-team1` | 31 | 0.5 to 2.5 (3 lines) |
| Over Under Team 2 First Half | `teamtotals-team2` | 31 | 0.5 to 2.5 (3 lines) |
| Over Under Team 2 Second Half | `teamtotals-team2` | 31 | 0.5 to 2.5 (3 lines) |
| Team 1 Win To Nil First Half | `wintonil-team1` | 29 |  |
| Team 1 Win To Nil Second Half | `wintonil-team1` | 27 |  |
| Team 2 Win To Nil First Half | `wintonil-team2` | 27 |  |
| Anytime Goal Scorer | `players-anytimegoalscorer` | 24 |  |
| Last Goal Scorer | `players-lastgoalscorer` | 24 |  |
| Player To Be Carded (incl. overtime) | `players-cards` | 18 |  |
| Corners - 1X2 | `1x2-corners` | 13 |  |
| Corners - 1X2 First Half | `1x2-corners` | 13 |  |
| Corners - Odd Even | `oddeven-corners` | 13 |  |
| Corners - Over Under First Half | `totals-corners` | 13 | 2.5 to 5.5 (4 lines) |
| Corners - Over Under Full Time | `totals-corners` | 13 | 6.5 to 11.5 (6 lines) |
| Corners - Handicap | `spread-corners` | 11 | -5.5 to 2.5 (9 lines) |
| Corners - Handicap First Half | `spread-corners` | 11 | -2.5 to 1.5 (5 lines) |
| Corners - Odd Even First Half | `oddeven-corners` | 11 |  |
| Bookings - 1X2 | `1x2-bookings` | 5 |  |
| Bookings - 1X2 First Half | `1x2-bookings` | 5 |  |
| Bookings - Over Under First Half | `totals-bookings` | 5 | 0.5 to 3.5 (4 lines) |
| Bookings - Over Under Full Time | `totals-bookings` | 5 | 1.5 to 6.5 (6 lines) |
