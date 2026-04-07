# SIDEWINDER — HiLo Adaptive Chain Profit Strategy

> **For agentic workers:** Use superpowers:writing-plans to generate an implementation plan from this PRD, then superpowers:subagent-driven-development or superpowers:executing-plans to implement.

Generated on: 2026-04-07 13:45 UTC+8
Last updated: —

## Context
HiLo is the only Antebot game with **three independent control levers**: bet size (IOL), cashout target (chain length), and skip selectivity (which cards to bet on). Every other game only has bet size. SIDEWINDER exploits this by dynamically adjusting all three levers based on session state — enabling IOL recovery at just 2.0x (vs 3.0x for dice/roulette) because HiLo's chain payouts produce near-1:1 risk/reward ratios that over-recover losses.

## Success Criteria
- [ ] Monte Carlo optimizer produces a config that beats MAMBA's median at equal bank/divider ($100 bank)
- [ ] P10 tail risk (worst 10% of sessions) is <= 25% of bankroll
- [ ] Antebot script runs correctly in both sim and live on Shuffle
- [ ] Win rate >= 55% of sessions across 5,000 Monte Carlo runs
- [ ] Strategy uses at least 2 of 3 unique HiLo levers (cashout target + skip selectivity)

## Scope

**In Scope:**
- Monte Carlo simulator for HiLo chain mechanics (skip, bet, cashout decisions per card)
- Parameter sweep: skip range x cashout targets x IOL multiplier x mode thresholds
- Three-mode state machine: CRUISE / RECOVERY / CAPITALIZE
- Antebot script with `engine.onGameRound()` per-card decision logic
- Trailing stop + stop loss + stop profit (proven pattern from MAMBA/COBRA)
- Head-to-head comparison with MAMBA (dice) and COBRA (roulette) at $100 bank

**Out of Scope (Explicit):**
- Card counting — impossible with provably fair RNG (infinite deck, independent draws)
- `HILO_BET_EQUAL` — 7.7% win rate, too volatile for IOL recovery
- `HILO_BET_HIGH_EQUAL` / `HILO_BET_LOW_EQUAL` — guaranteed-loss 0.99x bets on A/K edges
- Async mode — not recommended per Antebot docs for loss-based strategies
- Vault-and-continue — defer to v2 after live validation

## Requirements

### Must Have (P0)

**Monte Carlo Optimizer:**
- Simulate HiLo hands: startCard -> sequence of (skip/bet/cashout) decisions -> hand result (win x multiplier or loss)
- Card draws: uniform random from 1-13 (provably fair infinite deck)
- Payout per correct prediction: `0.99 * 13 / count_winning_cards` (1% house edge)
- Accumulated multiplier: product of individual prediction payouts within a hand
- Skip logic: configurable set of card values to skip (e.g., skip 5-9)
- Cashout logic: cash out when accumulated multiplier >= target, configurable per mode
- IOL on hand loss: multiply betSize by IOL factor, soft bust at 95% of balance
- Three modes with configurable transitions: CRUISE (default), RECOVERY (deficit), CAPITALIZE (trail active)
- Each mode has independent cashout target
- Trail stop (act/lock), stop loss %, stop profit % — same proven logic as MAMBA
- Sweep parameters: skip range variants, cashout targets [1.2, 1.5, 2.0, 2.5, 3.0], IOL [1.5, 2.0, 2.5, 3.0], mode thresholds
- Output: median, mean, bust%, win%, P5, P10, P90, avg hands per session
- File: `scripts/tools/sidewinder-optimizer.py`

**Antebot Script:**
- `game = "hilo"`, `startCard = { rank: "A", suit: "C" }` (guaranteed 92% first prediction)
- `engine.onGameRound((currentBet) => { ... })` — per-card decision logic:
  - Read current card from `currentBet.state.rounds.at(-1).card.rank` (fallback to `currentBet.state.startCard.rank`)
  - Read accumulated multiplier from `currentBet.state.rounds.at(-1).payoutMultiplier`
  - If multiplier >= cashout target for current mode -> return `HILO_CASHOUT`
  - If card in skip range -> return `HILO_SKIP` (respect 52-skip limit)
  - If card value <= midpoint -> return `HILO_BET_HIGH`
  - If card value > midpoint -> return `HILO_BET_LOW`
- `engine.onBetPlaced(async (lastBet) => { ... })` — session-level logic:
  - Process hand result (win/loss), update IOL multiplier
  - Mode transitions based on profit state
  - Trail stop check, SL check, stop profit check
  - Build `betSize` for next hand
- Mode state machine:
  - CRUISE: profit > -X% -> cashout at low target, standard skip
  - RECOVERY: profit < -X% or IOL mult > 1.5 -> cashout at high target
  - CAPITALIZE: trail active -> cashout at very low target, maximize win rate
- Follow all Antebot conventions: `var` only, string concat, `Math.pow()`, `engine.stop()`
- File: `scripts/hilo/sidewinder.js`

### Should Have (P1)
- Comparison table in optimizer output: SIDEWINDER vs MAMBA vs COBRA at $100 bank
- Balance-tier presets in script header ($25, $100, $250, $1000)
- Per-hand logging: card sequence, mode, accumulated multiplier, action taken
- Skip counter display (N/52 skips used this hand)

### Won't Have (this iteration)
- Dynamic skip range per mode (adds complexity, test fixed skip first)
- `HILO_BET_EQUAL` as a "moon shot" capitalize option
- Multi-seed validation (use single sweep first, validate with multi-seed after)
- Vault-and-continue pattern

## Technical Spec

### Files to Modify/Create
| File | Change |
|------|--------|
| `scripts/tools/sidewinder-optimizer.py` | New — Monte Carlo optimizer with HiLo chain simulation |
| `scripts/hilo/sidewinder.js` | New — Antebot script with onGameRound decision logic |
| `CLAUDE.md` | Add SIDEWINDER to flagship scripts table |

### HiLo API Reference (extracted from community scripts)
| API | Type | Notes |
|-----|------|-------|
| `game = "hilo"` | string | Required |
| `betSize` | float | Bet amount per hand |
| `startCard` | object | `{ rank: "A"\|"2"...\|"K", suit: "C"\|"D"\|"H"\|"S" }` |
| `engine.onGameRound((currentBet) => action)` | callback | Returns action per card in hand |
| `currentBet.state.startCard.rank` | string | Starting card rank |
| `currentBet.state.rounds` | array | Array of round results within current hand |
| `currentBet.state.rounds[i].card.rank` | string | Card shown in round i |
| `currentBet.state.rounds[i].payoutMultiplier` | float | Accumulated multiplier after round i |
| `currentBet.state.rounds[i].action` | string | Action taken ("skip", "high", "low", etc.) |
| `HILO_BET_HIGH` | constant | Bet next card is higher |
| `HILO_BET_LOW` | constant | Bet next card is lower |
| `HILO_SKIP` | constant | Skip this card (max 52 per hand) |
| `HILO_CASHOUT` | constant | Cash out at current multiplier |

### HiLo Payout Math
- Card values: A=1, 2-10, J=11, Q=12, K=13
- BET_HIGH on card V: win prob = (13-V)/13, payout = 0.99 x 13/(13-V)
- BET_LOW on card V: win prob = (V-1)/13, payout = 0.99 x 13/(V-1)
- Chain payout = product of individual prediction payouts
- EV per prediction = 0.99 (1% house edge, same for all bets)
- EV per N-prediction chain = 0.99^N (compounds)

### Key Payout Table
| Card | BET_HIGH prob | BET_HIGH pay | BET_LOW prob | BET_LOW pay |
|------|-------------|-------------|-------------|-------------|
| A(1) | 92.3% | 1.074x | -- | -- |
| 2 | 84.6% | 1.170x | 7.7% | 12.87x |
| 3 | 76.9% | 1.287x | 15.4% | 6.44x |
| 7 | 46.2% | 2.145x | 46.2% | 2.145x |
| J(11)| 15.4% | 6.44x | 76.9% | 1.287x |
| Q(12)| 7.7% | 12.87x | 84.6% | 1.170x |
| K(13)| -- | -- | 92.3% | 1.074x |

### Suggested Sequence
1. **Build HiLo chain simulator** (core engine) — simulate a single hand with skip/bet/cashout logic, return (win, multiplier) or (loss). ~15 min
2. **Add session simulator** — wrap hand simulator in IOL + trailing stop + mode switching loop. ~15 min
3. **Parameter sweep** — skip range variants x cashout x IOL x modes. Output table. ~10 min
4. **Analyze results** — select optimal config, compare with MAMBA/COBRA baselines. ~10 min
5. **Build Antebot script** — `onGameRound` decision logic, `onBetPlaced` session logic, mode state machine. ~15 min
6. **Add logging** — scriptLog, logBanner, logSummary (reuse MAMBA/COBRA pattern). ~10 min
7. **Sim test** — run in Antebot sim mode, verify hand-by-hand behavior matches Monte Carlo. ~10 min
8. **Live test** — $25-50 test on Shuffle, verify API interactions. ~5 min

### Dependencies & Order
- Step 1-2 must complete before step 3 (need simulator for sweep)
- Step 4 must complete before step 5 (need optimal params for script)
- Step 5-6 can run in parallel
- Step 7 before step 8

## Evaluation Criteria
- [ ] Optimizer median > MAMBA median at $100 bank -> Expected: PASS
- [ ] P10 < 25% bankroll loss -> Expected: PASS
- [ ] Bust rate < 1% -> Expected: PASS
- [ ] Script places bets correctly in sim (onGameRound fires, skips/bets/cashouts observed) -> Expected: PASS
- [ ] Script places bets correctly on live Shuffle -> Expected: PASS
- [ ] Mode transitions fire (CRUISE->RECOVERY->CAPITALIZE logged) -> Expected: PASS

## Verification
- [ ] `python3 scripts/tools/sidewinder-optimizer.py` — produces ranked parameter table
- [ ] Run script in Antebot sim mode — observe 20+ hands, verify skip/bet/cashout logic
- [ ] Run script live with $25 — verify bets appear in bet history
- [ ] Manual check: trailing stop fires when profit drops below floor

## Notes
- Start card A guarantees 92% first prediction — always use `startCard = { rank: "A", suit: "C" }`
- HiLo draws from infinite deck (provably fair RNG) — each card independent, no counting
- The 52-skip-per-hand limit is generous — most hands will use <10 skips
- Community scripts use template literals and `const/let` — our script must use `var` and string concat per CLAUDE.md
- The `lastBet.win` field indicates whether the hand was profitable (cashed out for >= 1.0x)
- Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) / TAIPAN (Roulette v2) / **SIDEWINDER (HiLo)**
