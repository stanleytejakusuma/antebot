# COBRA — Roulette Profit Strategy

> **For agentic workers:** Use superpowers:writing-plans to generate an implementation plan from this PRD, then superpowers:subagent-driven-development or superpowers:executing-plans to implement.

Generated on: 2026-04-05 01:00 UTC
Last updated: —

## Context

Profit R/B (darthvador05) is the best roulette profit strategy at +$161 median, but it has two weaknesses: (1) no brake mechanic — IOL 3.5x escalates to $700+ bets at LS 8, causing 12.7% bust rate, (2) no capitalize — every win resets to base, leaving streak profit on the table. COBRA applies VIPER's proven three-phase architecture (Strike/Coil/Capitalize) to roulette, using Profit R/B's optimized number coverage as the base engine.

## Success Criteria

- [ ] Monte Carlo median profit ≥ Profit R/B (+$161) at comparable or lower bust rate
- [ ] Brake reduces bust rate from 12.7% baseline while maintaining median > +$100
- [ ] Capitalize adds measurable profit above IOL-only baseline
- [ ] Antebot script runs cleanly for 1000+ spins with no errors
- [ ] All three modes fire during live testing

## Scope

**In Scope:**
- Monte Carlo optimizer: sweep brake threshold, capitalize params, IOL multiplier
- Antebot roulette script with three-phase state machine
- Profit R/B number coverage (24 big / 5 small / 8 uncovered) as base
- Enhanced logging with mode counters, recovery stats, capitalize tracking
- Vault-and-continue with percentage-based thresholds
- Head-to-head comparison with baseline Profit R/B

**Out of Scope:**
- Alternative number coverage patterns (R/B's 24/5/8 is proven optimal)
- Blackjack integration (separate strategy — VIPER)
- Card counting or seed prediction (impossible on provably fair RNG)
- Other roulette bet types (columns, dozens) — number bets only this iteration

## Requirements

### Must Have (P0)

- Three-phase state machine: STRIKE, COIL, CAPITALIZE → `scripts/roulette/cobra.js`
- **STRIKE mode**: IOL on miss — multiply total bet by `iolMultiplier` (default 3.5x). Reset to base on any win. Identical to Profit R/B's current behavior.
- **COIL mode**: Flat bet at brake level when consecutive misses exceed `brakeAt`. Holds bet steady instead of escalating. Exits to STRIKE when a win occurs (recovery, reset to base).
- **CAPITALIZE mode**: After `capStreak` consecutive wins (default 3), multiply base bet by 2x for `capMaxBets` spins (default 2). Any miss exits to STRIKE at base bet.
- Number coverage from Profit R/B: 24 big numbers, 5 small numbers, 8 uncovered. `bigToSmallRatio = 5`. Uncovered: [0, 4, 9, 12, 13, 21, 25, 36]. Small: [1, 16, 24, 31, 33].
- Bet calculation: `totalBet = balance / divider`, big bet = `totalBet / (bigCount * ratio + smallCount) * ratio`, small bet = big / ratio
- IOL on miss: `totalBet *= iolMultiplier` (applies to both big and small proportionally)
- Monte Carlo optimizer → `scripts/tools/cobra-optimizer.py`
- Parameter sweep: brakeAt [4,5,6,7,OFF], capStreak [2,3,4], capMaxBets [1,2,3], iolMultiplier [2.5,3.0,3.5,4.0], divider [2574,9008,31526]
- Vault: percentage-based (vaultPct, stopTotalPct) with profitAtLastVault offset tracking (same pattern as VIPER v2)

### Should Have (P1)

- Enhanced console logging: mode counters (STRIKE/COIL/CAP hands + %), mode switches, capitalize W/L + net, coil activations, runway indicator during IOL streak, chain cost, drawdown from peak, RTP, wagered total
- `logSummary()` with `summaryPrinted` dedup flag
- Risk presets in comments (conservative/balanced/aggressive with brake levels)
- Configurable `seedChangeAfterLossStreak` (default 0 — proven useless but kept for user preference)

### Won't Have (this iteration)

- Alternative coverage patterns (24/5/8 is validated)
- Adaptive divider mid-session (only on vault)
- Multi-game support (roulette only)

## Technical Spec

### Files to Create/Modify

| File | Change |
|------|--------|
| `scripts/roulette/cobra.js` | New file — full Antebot roulette script with 3-phase state machine |
| `scripts/tools/cobra-optimizer.py` | New file — Monte Carlo parameter sweep + comparison vs Profit R/B |
| `CLAUDE.md` | Add COBRA to flagship scripts table |

### Roulette Engine API (reference)

- `game = 'roulette'`
- `selection` object: keys `number0`-`number36` with bet amounts as values
- No `betSize` variable needed — bet amounts set per number in selection
- `lastBet.state.result` — integer 0-36 (number that hit)
- `lastBet.win` — true when payoutMultiplier >= 1.0
- `lastBet.payoutMultiplier` — payout / total bet
- `rouletteNumberColor(number)` → 'red', 'black', 'green'
- Standard globals: `engine.onBetPlaced()`, `engine.stop()`, `balance`, `profit`, `isSimulationMode`, `depositToVault()`

### Bet Construction

```javascript
// Build selection object each spin
selection = {};
for (i = 0; i < bigBetNumbers.length; i++) {
  selection["number" + bigBetNumbers[i]] = bigBet * currentMultiplier;
}
for (i = 0; i < smallBetNumbers.length; i++) {
  selection["number" + smallBetNumbers[i]] = smallBet * currentMultiplier;
}
```

### Suggested Sequence

1. **Build Monte Carlo optimizer** (15 min) — implement COBRA strategy class, Profit R/B baseline, parameter sweep
2. **Run optimizer** (10 min) — find optimal brake + capitalize + IOL config
3. **Analyze results** (5 min) — compare vs Profit R/B, validate brake reduces bust, capitalize adds profit
4. **Build Antebot script** (15 min) — port optimal config to `cobra.js`, add enhanced logging
5. **Code review** (5 min) — verify roulette API usage, selection object, mode transitions
6. **Live test** (10 min) — 100 spins dev test, then 500+ extended

### Dependencies & Order

- Step 1 before step 2 (need optimizer before sweep)
- Step 3 before step 4 (need optimal params before script)
- Reuse: bet construction pattern from `scripts/roulette/profit-on-redblack.js`
- Reuse: vault/stop/logging patterns from `scripts/blackjack/viper.js`

## Evaluation Criteria

- [ ] COBRA median ≥ +$161 (Profit R/B baseline) at bust ≤ 12.7% → Expected: PASS if capitalize adds enough
- [ ] COBRA median ≥ +$100 at bust ≤ 7% (brake benefit) → Expected: PASS
- [ ] Brake reduces max bet exposure by ≥ 50% vs uncapped IOL → Expected: PASS
- [ ] Capitalize fires ≥ 10% of spins → Expected: PASS (78% win rate → 47% chance of 3-streak after win)
- [ ] Script runs 500+ spins without errors → Expected: PASS
- [ ] Regression: number coverage matches Profit R/B exactly → Expected: PASS

## Verification

- [ ] `python3 scripts/tools/cobra-optimizer.py` — runs sweep, outputs comparison table
- [ ] `python3 scripts/tools/cobra-optimizer.py --quick` — quick validation
- [ ] Manual: paste `cobra.js` into Antebot Code Mode, run 100 spins at $100 balance
- [ ] Manual: verify all 3 mode labels appear in console during extended run
- [ ] Manual: verify vault triggers at configured % and stop at total %

## Notes

- COBRA = VIPER's roulette sibling. Same architecture (Strike/Coil/Capitalize), different game engine.
- Roulette's 78% win rate (vs BJ's 48%) means IOL recovery is much faster — the brake threshold can be lower.
- Capitalize on roulette is stronger than BJ because win streaks of 3+ are more frequent (78%^3 = 47% vs 48%^3 = 11%).
- The house edge is always 2.7% — COBRA optimizes variance distribution, not edge.
- Profit R/B's number coverage (24/5/8 split) was community-optimized and verified. Don't change it.
