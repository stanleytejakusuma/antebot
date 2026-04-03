# HYDRA — Aggressive Profit Blackjack Strategy

> **For agentic workers:** Use superpowers:writing-plans to generate an implementation plan from this PRD, then superpowers:subagent-driven-development or superpowers:executing-plans to implement.

Generated on: 2026-04-03 11:00 UTC
Last updated: —

## Context

Existing BJ betting strategies either optimize for profit (Oscar's Grind) or wager volume (Momentum Shift), but none combine the best-proven recovery mechanism (Oscar's cycle) with adaptive aggression scaling and a defensive damage-control mode. HYDRA is a four-mode state machine that uses Oscar's Grind for recovery, profit-scaled Paroli for streak exploitation, a novel half-bet Fortress mode for cold-streak damage control, and flat Sentinel as the safe default. The goal is to beat Oscar+Paroli's +$112 median at x20 by reducing bust rate through Fortress, allowing higher effective bet utilization.

## Success Criteria

- [ ] Monte Carlo median profit > +$112 at comparable bust rate (<35%) on 5,000+ sessions
- [ ] Bust rate lower than Oscar+Paroli x20 (32.2% baseline) at same or higher median
- [ ] Antebot script runs cleanly for 500+ hands with no errors
- [ ] All four modes fire during live testing (verified by mode counters)
- [ ] Profit-scaled Surge correctly adjusts starting bet based on session profit

## Scope

**In Scope:**
- Monte Carlo Python simulator for HYDRA parameter optimization
- Antebot BJ script with four-mode state machine
- Manual bet matrix (Vrafasky/ConnorMcLeod community standard)
- Enhanced logging with mode counters, transitions, profit tracking
- Parameter sweep: grind/fortress thresholds, surge config, max_mult
- Head-to-head comparison vs Oscar+Paroli, Oscar x20, Momentum Shift

**Out of Scope (Explicit):**
- Card counting (impossible on Shuffle Originals infinite deck)
- Bet matrix changes (verified negligible impact in matrix-comparison.py)
- Baccarat/roulette/dice adaptations (BJ only this iteration)
- Vault-and-continue tuning (already proven neutral by Monte Carlo)

## Requirements

### Must Have (P0)

- Four-mode state machine: SENTINEL, GRIND, SURGE, FORTRESS → `scripts/blackjack/hydra.js`
- **SENTINEL mode**: flat bet at 1 unit, default starting mode. Transitions to GRIND on deficit > `grindThreshold`, to SURGE on win streak >= `surgeStreak` AND profit > `surgeProfitGate`
- **GRIND mode**: Oscar's Grind cycle logic (+1u after win only when in deficit, cycle goal = +1u profit, never raise on loss). Transitions to SENTINEL on cycle complete when deficit < 2u. Transitions to FORTRESS on deficit > `fortressThreshold`
- **SURGE mode**: Paroli doubling with profit-scaled starting bet. Surge base = `max(unit, profit * surgeProfitScale)`. 2x on each consecutive win, max chain = `surgeMaxChain`. Only activates when session `profit > surgeProfitGate * unit`. Transitions back to SENTINEL on loss or chain complete
- **FORTRESS mode**: bet = `max(0.5 * unit, minBet)`. Half-unit defensive betting during severe cold streaks. Transitions to SENTINEL after `fortressCooldown` hands OR on first win
- Monte Carlo simulator class in Python → `scripts/tools/hydra-optimizer.py`
- Parameter sweep across: grindThreshold [3,5,8], fortressThreshold [15,20,30], surgeStreak [2,3], surgeMaxChain [2,3,4], surgeProfitGate [3,5,10], surgeProfitScale [0.05,0.1,0.2], fortressCooldown [5,10,15], maxBetMultiple [15,20,25,30]
- Head-to-head comparison table vs Oscar+Paroli, Oscar x20, MS best configs
- Manual bet matrix (reuse from `scripts/blackjack/oscars-grind.js`)
- Side bets unconditionally disabled (`sideBetPerfectPairs = 0; sideBet213 = 0;`)

### Should Have (P1)

- Enhanced console logging: mode counters (SENTINEL/GRIND/SURGE/FORTRESS hand counts), mode switch count, Surge win/loss record, peak profit, Fortress time spent
- Session summary with mode split percentages
- Configurable preset profiles (conservative, default, aggressive) as comment blocks
- `logSummary()` pattern with `onBettingStopped` duplicate prevention (as in momentum-shift.js)

### Won't Have (this iteration)

- Adaptive divider recalculation mid-session (only on vault)
- Continuous momentum scoring (discrete modes proven more effective)
- Multi-session memory (each session is independent)
- Auto-switching between profit/wager presets

## Technical Spec

### Files to Modify/Create

| File | Change |
|------|--------|
| `scripts/blackjack/hydra.js` | New file — full Antebot BJ script with 4-mode state machine |
| `scripts/tools/hydra-optimizer.py` | New file — Monte Carlo parameter sweep + comparison |
| `CLAUDE.md` | Add HYDRA to flagship scripts table |

### Suggested Sequence

1. **Build Python Hydra class** (10 min) — implement the 4-mode state machine in `hydra-optimizer.py` with all transitions and bet sizing logic
2. **Run parameter sweep** (15 min) — sweep all parameter combinations, rank by median profit, identify Pareto frontier vs bust rate
3. **Analyze results** (5 min) — compare best Hydra config against Oscar+Paroli x20 (+$112) and Oscar x20 (+$105). Validate Fortress reduces bust. Validate profit-scaled Surge improves median
4. **Build Antebot script** (15 min) — write `hydra.js` using optimal parameters from step 3, reuse bet matrix from `oscars-grind.js`, add enhanced logging
5. **Code review** (5 min) — verify API usage (isSimulationMode, engine.stop(), lastBet fields), push check, side bet disabling
6. **Live test** (10 min) — 50 hands dev test, then 500 hands extended test. Verify all 4 modes fire

### Dependencies & Order

- Step 1 before step 2 (need simulator before sweep)
- Step 3 before step 4 (need optimal params before Antebot script)
- Step 5 before step 6 (review before live)
- Bet matrix can be copy-pasted from `scripts/blackjack/oscars-grind.js` (identical)

### Antebot Engine API (reference)

- `game = "blackjack"`, `betSize` (float), `sideBetPerfectPairs`, `sideBet213`
- `engine.onGameRound(function(currentBet, playerHandIndex) { ... })` — return `BLACKJACK_HIT/STAND/DOUBLE/SPLIT`
- `engine.onBetPlaced(async function() { ... })` — main strategy logic
- `engine.onBettingStopped(function() { ... })` — session end
- `engine.stop()`, `isSimulationMode`, `balance`, `profit`, `lastBet.win`, `lastBet.payout`, `lastBet.amount`, `lastBet.payoutMultiplier`
- `lastBet.state.player[i].actions` — array of actions per hand (check for "double")
- `depositToVault(amount)`, `resetSeed()`, `playHitSound()`

## Evaluation Criteria

- [ ] Hydra median profit > +$112 (Oscar+Paroli x20 baseline) on 5,000 sessions → Expected: PASS
- [ ] Hydra bust rate < 32% at optimal config → Expected: PASS
- [ ] Fortress mode activates during Monte Carlo (fortress_hands > 0 on average) → Expected: PASS
- [ ] Surge profit-scaling produces larger bets in high-profit sessions vs low-profit → Expected: PASS
- [ ] Antebot script runs 500 hands without errors → Expected: PASS
- [ ] All four modes fire in live testing → Expected: PASS
- [ ] Regression: bet matrix decisions match oscars-grind.js exactly → Expected: PASS

## Verification

- [ ] `python3 scripts/tools/hydra-optimizer.py` — runs parameter sweep, outputs comparison table
- [ ] `python3 scripts/tools/hydra-optimizer.py --quick` — quick validation (1000 sessions)
- [ ] Manual check: paste `hydra.js` into Antebot Code Mode, run 50 hands at $50 balance
- [ ] Manual check: verify console shows all 4 mode labels during extended run
- [ ] Manual check: verify Surge starting bet increases in sessions with higher profit

## Notes

- HYDRA name = multi-headed, each mode specializes in a different condition
- The key innovation over Oscar+Paroli is FORTRESS (half-bet defensive mode) and profit-scaled SURGE
- Fortress hypothesis: reducing bust rate by ~3-5% allows pushing max_mult from x20 to x25-30, which should increase median by ~$15-30
- If Fortress doesn't improve results, fallback to Oscar+Paroli is already implemented and proven
- All strategies are -EV. HYDRA optimizes variance distribution, not edge
