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
| `scripts/roulette/profit-on-redblack.js` | Roulette | Profit on Red/Black v1.3 — 24 big/5 small/8 uncovered numbers, 3.5x IOL, adaptive divider after vault, stopAfterVaults walk-away |

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
