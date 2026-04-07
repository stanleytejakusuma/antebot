# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Antebot automated betting scripts for casino games. Scripts run in **Antebot Code Mode** — a JavaScript editor embedded in the Antebot desktop app. Each script is a standalone `.js` file pasted into the editor; there are no imports, no build step, no test runner.

**Target casino:** Shuffle (USDT). Scripts also work on Stake, Goated, etc.

## Code Conventions (Mandatory)

- **`var` only** — no `let` or `const`
- **String concatenation** — no template literals
- **`Math.pow()`** — no `**` operator
- **`engine.stop()`** — never bare `stop()`
- **`isSimulationMode`** — engine API boolean (read-only). NOT `isSimulatedMode`.
- Arrow functions and async are OK for engine callbacks
- **Version bumps** — increment `version` on EVERY code change (semver: patch for config/param, minor for behavior, major for thesis). Update both the variable and header comments.

## Script Architecture

Every script follows this structure:

```
1. Sim mode setup (if isSimulationMode)
2. game = '<game-name>'
3. Config constants
4. Dynamic bankroll calculation from balance
5. State variables
6. Initial bet setup
7. engine.onBetPlaced(async (lastBet) => { ... })   — main loop
8. engine.onGameRound(...)                            — sub-rounds (blackjack, hilo)
9. engine.onBettingStopped(...)                       — summary on exit
```

### Vault-and-Continue Pattern

Our primary strategy pattern: instead of walking away at a profit target, vault the profits via `depositToVault(amount)`, reset the seed with `resetSeed()`, reset cycle state, and keep grinding. Only stop on loss.

### lastBet Fields

Use documented field names: `.win`, `.amount`, `.payout`, `.payoutMultiplier`, `.state`
NOT underscore-prefixed: `._win`, `._amount`, `._payout` (seen in some community scripts but undocumented).

## Directory Structure

```
scripts/
  dice/           — Dice strategies (SIEGE is flagship)
  blackjack/      — Blackjack strategies (RAMPART is flagship)
  roulette/       — Roulette strategies (Profit on Red/Black)
  community/      — Third-party scripts from forum (reference only)
  <game>/_archive — Superseded scripts
docs/
  games/          — Code Mode API docs per game (fetched from forum)
  plans/          — Implementation plans
```

## Flagship Scripts

| Script | Game | Strategy |
|--------|------|----------|
| `scripts/dice/siege.js` | Dice | SIEGE v1.3 — Two-tier (session + meta walk-away), 10%/9.9x, streak escalation, trailing stops, cumulative vault |
| `scripts/blackjack/rampart.js` | Blackjack | RAMPART v3.0 — 6 betting systems (flat/dalembert/martingale/paroli/oscar/fibonacci), advanced perfect strategy, vault-and-continue |
| `scripts/roulette/profit-on-redblack.js` | Roulette | Profit on Red/Black v1.4 — 24 big/5 small/8 uncovered numbers, 3.5x IOL, adaptive divider after vault, stopAfterVaults walk-away |
| `scripts/roulette/cobra.js` | Roulette | COBRA v4.2 — Pure 23-number IOL 3.0x, +$412 median (div=10k), vault-and-grind, soft bust protection |
| `scripts/dice/mamba.js` | Dice | MAMBA v2.0 — Dice 65% IOL 3.0x + trailing stop, same median but 3x lower bust (3.5% vs 9.6% at stop=15%) |
| `scripts/dice/mamba-turbo.js` | Dice | MAMBA TURBO v1.0 — MAMBA + Capitalize (3x bet on 3-streaks), 2.6x faster sessions, +81% wager/hr, same median |
| `scripts/roulette/taipan.js` | Roulette | TAIPAN v2.0 — Adaptive coverage + tamed IOL (PATIENCE delay=3, cap=15%), IOL 5.0x, +$5.38 median ($100), -$19.51 P10, 0% bust |
| `scripts/hilo/sidewinder.js` | HiLo | SIDEWINDER v1.0 — Adaptive chain skip={6-8} IOL 3.0x, 3-mode cashout (cruise 1.5x/recovery 2.5x/capitalize 1.1x), +$7.75 median ($100), trail 8/60 |
| `scripts/blackjack/dalembert-aw.js` | Blackjack | D'Alembert AW v1.1 — Action-weighted units (1/2/4 for normal/double/split), manual bet matrix, 10x cap, peak profit reset |
| `scripts/blackjack/momentum-shift.js` | Blackjack | Momentum Shift v1.0 — Three-mode regime (cruise/recovery/capitalize), rec=8/3 optimized median +$29, 8.2% bust, vault-and-continue |
| `scripts/blackjack/oscars-grind.js` | Blackjack | Oscar's Grind v1.0 — +1u after win only in deficit, cycle goal +1u, #1 median (+$28), 19.8% bust |
| `scripts/blackjack/oscars-paroli.js` | Blackjack | Oscar's Paroli v1.0 — Oscar's Grind + Paroli capitalize, +$112 median (x20), 32% bust, 60% win rate |
| `scripts/blackjack/martingale-paroli.js` | Blackjack | Mart+Paroli v1.0 — Martingale 2x + Paroli capitalize, +$163 median (div=6k), beats roulette R/B, 31.5% bust |
| `scripts/blackjack/viper.js` | Blackjack | VIPER v5.0 — Hybrid D'Alembert→Martingale strike, div=8000, dalCap=5, mart=2x, brake=12. G=-56.5%, +$7.46 median ($100), 7.4% bust. Scored by Growth Rate. |
| `scripts/baccarat/basilisk.js` | Baccarat | BASILISK v1.0 — Delayed IOL (PATIENCE): only escalate after 3+ consecutive losses, IOL 2.1x, tie shield, +$5.59 median ($100), 0% bust |
| `scripts/tools/proving_ground/` | Python | PROVING GROUND — 3-pillar strategy testing harness (Monte Carlo + Markov Chain + Provably Fair Replay) |
| `scripts/tools/dalembert-simulator.py` | Python | Monte Carlo simulator for BJ/baccarat D'Alembert parameter optimization |

## Antebot Engine API Quick Reference

Full docs in `docs/games/general.md`. Key globals available in all games:

| API | Type | Notes |
|-----|------|-------|
| `isSimulationMode` | boolean (read-only) | true in sim, false in live |
| `balance` | float (read-only) | Current balance |
| `currentStreak` | integer (read-only) | Positive = wins, negative = losses |
| `vaulted` | float (read-only) | Total vaulted amount |
| `engine.stop()` | function | Stop betting |
| `depositToVault(amount)` | function | Deposit to vault widget |
| `resetSeed()` | function | New server/client seed pair |
| `log(...)` | function | Print to console tab |
| `playHitSound()` | function | Audio alert |
| `chanceToMultiplier(chance)` | function | Dice-specific converter |

### Game-Specific APIs

- **Blackjack**: `blackJackPerfectNextAction(currentBet, playerHandIndex, strategy, double)` — strategies: `easy`, `simple`, `advanced`, `exactComposition`, `bjc-supereasy`, `bjc-simple`, `bjc-great`. Double: `none`, `10or11`, `9or10or11`, `any`. Return constants: `BLACKJACK_DOUBLE`, `BLACKJACK_HIT`, `BLACKJACK_SPLIT`, `BLACKJACK_STAND`. Must `betSize *= 2` before returning `BLACKJACK_DOUBLE`.
- **Roulette**: `selection` object with bet amounts per position. `rouletteNumberColor(number)` returns `'red'`, `'black'`, or `'green'`.
- **Per-game docs**: See `docs/games/<game>.md` for variables, lastBet shape, and code examples.

## House Edge Context

All Antebot scripts are **negative expected value** (-EV). Provably fair RNG = independent hands, no card counting. Strategies are variance management — catch favorable runs, vault profits, limit losses. Blackjack has the lowest edge (0.52%), dice/limbo/keno at 1%, roulette worst at 2.7%.

## Forum Access

Antebot forum docs require authentication. Access via Discourse JSON API:
```
curl -s -b "COOKIES" -H "Accept: application/json" "https://forum.antebot.com/t/<slug>/<id>.json"
```
Cookie values stored in SYMIR auto-memory (`MEMORY.md`).
