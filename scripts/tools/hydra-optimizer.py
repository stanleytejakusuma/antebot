#!/usr/bin/env python3
"""
HYDRA Strategy Optimizer — Four-mode aggressive profit strategy
Modes: SENTINEL (flat) → GRIND (Oscar's) → SURGE (profit-scaled Paroli) → FORTRESS (half-bet)

Usage:
  python3 hydra-optimizer.py              # Full sweep
  python3 hydra-optimizer.py --quick      # Quick 1000-session test
"""

import random
import sys
import time
from itertools import product

# ============================================================
# BJ OUTCOME MODEL
# ============================================================

BJ_OUTCOMES = [
    (0.0475, +1.5, 1), (0.3318, +1.0, 1), (0.4292, -1.0, 1), (0.0848, 0.0, 1),
    (0.0532, +2.0, 2), (0.0418, -2.0, 2), (0.0048, +2.0, 2), (0.0056, -2.0, 2),
    (0.0005, 0.0, 2), (0.0004, +4.0, 4), (0.0004, -4.0, 4),
]
_CUM = []
_c = 0
for p, _, _ in BJ_OUTCOMES:
    _c += p
    _CUM.append(_c)

def rng():
    r = random.random()
    for i, cp in enumerate(_CUM):
        if r < cp:
            return BJ_OUTCOMES[i][1], BJ_OUTCOMES[i][2]
    return BJ_OUTCOMES[-1][1], BJ_OUTCOMES[-1][2]


# ============================================================
# STRATEGIES
# ============================================================

class Hydra:
    def __init__(self, unit, max_mult,
                 grind_thresh=5, fortress_thresh=20,
                 surge_streak=3, surge_max_chain=2, surge_profit_gate=3,
                 surge_profit_scale=0.1, fortress_cooldown=10):
        self.unit = unit
        self.max_bet = unit * max_mult
        self.bet = unit
        # Params
        self.grind_thresh = grind_thresh
        self.fortress_thresh = fortress_thresh
        self.surge_streak = surge_streak
        self.surge_max_chain = surge_max_chain
        self.surge_profit_gate = surge_profit_gate
        self.surge_profit_scale = surge_profit_scale
        self.fortress_cooldown = fortress_cooldown
        # State
        self.mode = 'sentinel'
        self.deficit = 0.0
        self.win_streak = 0
        self.cycle_profit = 0.0  # Oscar's cycle tracker
        self.surge_count = 0
        self.fortress_count = 0
        self.session_profit = 0.0
        # Counters
        self.sentinel_hands = 0
        self.grind_hands = 0
        self.surge_hands = 0
        self.fortress_hands = 0

    def update(self, payout, is_win, is_loss, balance):
        hand_pnl = self.bet * payout
        self.session_profit += hand_pnl

        # Track streaks
        if is_win:
            self.win_streak += 1
            self.deficit = max(0, self.deficit - abs(hand_pnl))
        elif is_loss:
            self.win_streak = 0
            self.deficit += abs(hand_pnl)

        # --- Mode-specific logic ---

        if self.mode == 'sentinel':
            self.sentinel_hands += 1
            # Transitions
            if self.deficit > self.grind_thresh * self.unit:
                self.mode = 'grind'
                self.cycle_profit = -self.deficit  # Start cycle in deficit
            elif (self.win_streak >= self.surge_streak and
                  self.session_profit > self.surge_profit_gate * self.unit):
                self.mode = 'surge'
                self.surge_count = 0
                # Profit-scaled surge starting bet
                surge_base = max(self.unit, self.session_profit * self.surge_profit_scale)
                self.bet = min(surge_base, self.max_bet)
                return self._clamp()

        elif self.mode == 'grind':
            self.grind_hands += 1
            # Oscar's Grind logic
            self.cycle_profit += hand_pnl
            if is_win:
                if self.cycle_profit >= self.unit:
                    # Cycle complete
                    self.cycle_profit = 0.0
                    self.bet = self.unit
                    if self.deficit < 2 * self.unit:
                        self.mode = 'sentinel'
                    return self._clamp()
                else:
                    # Raise by 1u, cap to not overshoot +1u goal
                    needed = self.unit - self.cycle_profit
                    self.bet = min(self.bet + self.unit, needed, self.max_bet)
                    self.bet = max(self.bet, self.unit)
                    return self._clamp()
            # loss/push: keep same bet in grind
            # Check fortress transition
            if self.deficit > self.fortress_thresh * self.unit:
                self.mode = 'fortress'
                self.fortress_count = 0
            return self._clamp()

        elif self.mode == 'surge':
            self.surge_hands += 1
            self.surge_count += 1
            if is_loss or self.surge_count >= self.surge_max_chain:
                # Exit surge
                self.mode = 'sentinel'
                self.win_streak = 0
                self.bet = self.unit
                return self._clamp()
            elif is_win:
                self.bet = min(self.bet * 2, self.max_bet)
                return self._clamp()

        elif self.mode == 'fortress':
            self.fortress_hands += 1
            self.fortress_count += 1
            # Exit on first win or cooldown
            if is_win or self.fortress_count >= self.fortress_cooldown:
                self.mode = 'grind'
                self.cycle_profit = -self.deficit
                self.bet = self.unit
                return self._clamp()

        # Default bet for sentinel
        self.bet = self.unit
        return self._clamp()

    def _clamp(self):
        half = self.unit * 0.5
        if self.mode == 'fortress':
            self.bet = max(half, min(self.bet, self.max_bet))
        else:
            self.bet = max(self.unit, min(self.bet, self.max_bet))


class OscarsParoli:
    """Baseline: Oscar's Grind + Paroli (current best)."""
    def __init__(self, unit, max_mult, cap_streak=2, cap_max=2):
        self.unit = unit
        self.max_bet = unit * max_mult
        self.bet = unit
        self.cycle_profit = 0.0
        self.mode = 'grind'
        self.win_streak = 0
        self.cap_count = 0
        self.cap_streak = cap_streak
        self.cap_max = cap_max

    def update(self, payout, is_win, is_loss, balance):
        if is_win:
            self.win_streak += 1
        elif is_loss:
            self.win_streak = 0

        if self.mode == 'grind':
            self.cycle_profit += self.bet * payout
            if is_win:
                if self.cycle_profit >= self.unit:
                    self.cycle_profit = 0.0
                    self.bet = self.unit
                else:
                    needed = self.unit - self.cycle_profit
                    self.bet = min(self.bet + self.unit, needed, self.max_bet)
                    self.bet = max(self.bet, self.unit)
            if self.win_streak >= self.cap_streak and self.cycle_profit >= 0:
                self.mode = 'capitalize'
                self.cap_count = 0
        elif self.mode == 'capitalize':
            self.cap_count += 1
            if is_loss or self.cap_count >= self.cap_max:
                self.mode = 'grind'
                self.win_streak = 0
                self.bet = self.unit
                self.cycle_profit = 0.0
            elif is_win:
                self.bet = min(self.bet * 2, self.max_bet)

        self.bet = max(self.unit, min(self.bet, self.max_bet))


class OscarsGrind:
    """Baseline: pure Oscar's Grind."""
    def __init__(self, unit, max_mult):
        self.unit = unit
        self.max_bet = unit * max_mult
        self.bet = unit
        self.cycle_profit = 0.0

    def update(self, payout, is_win, is_loss, balance):
        self.cycle_profit += self.bet * payout
        if is_win:
            if self.cycle_profit >= self.unit:
                self.cycle_profit = 0.0
                self.bet = self.unit
            else:
                needed = self.unit - self.cycle_profit
                self.bet = min(self.bet + self.unit, needed, self.max_bet)
                self.bet = max(self.bet, self.unit)
        self.bet = max(self.unit, min(self.bet, self.max_bet))


# ============================================================
# SIMULATOR
# ============================================================

def simulate(strat_fn, num_sessions, max_hands, bankroll, stop_loss, seed):
    profits, wagers, busts = [], [], 0
    for s in range(num_sessions):
        random.seed(seed * 100000 + s)
        strat = strat_fn()
        profit, wagered = 0.0, 0.0
        for _ in range(max_hands):
            bal = bankroll + profit
            if bal <= 0:
                break
            bet = min(strat.bet, bal)
            if bet <= 0:
                break
            payout, wmult = rng()
            wagered += bet * wmult
            profit += bet * payout
            if stop_loss > 0 and profit <= -stop_loss:
                busts += 1
                break
            is_win = payout > 0
            is_loss = payout < 0
            strat.update(payout, is_win, is_loss, bankroll + profit)
        profits.append(profit)
        wagers.append(wagered)

    profits.sort()
    n = len(profits)
    aw = sum(wagers) / n
    return {
        'median': profits[n // 2],
        'mean': sum(profits) / n,
        'p10': profits[n // 10],
        'p90': profits[9 * n // 10],
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in profits if p > 0) / n * 100,
        'avg_wager': aw,
        'wager_ratio': aw / bankroll,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num_sessions = 1000 if quick else 3000
    max_hands = 2000
    bankroll = 1000
    stop_loss = 300
    seed = 42
    unit = bankroll / 2000

    print()
    print("=" * 115)
    print("  HYDRA STRATEGY OPTIMIZER")
    print(f"  {num_sessions:,} sessions x {max_hands:,} hands | Bankroll: ${bankroll:,} | Stop: -${stop_loss}")
    print("=" * 115)

    # ── BASELINES ──
    print("\n  --- BASELINES ---")
    hdr = f"  {'Config':<45} {'Median':>9} {'Mean':>9} {'Bust%':>6} {'Win%':>6} {'Wager':>8} {'W/Bk':>6}"
    sep = f"  {'─'*45} {'─'*9} {'─'*9} {'─'*6} {'─'*6} {'─'*8} {'─'*6}"
    print(hdr)
    print(sep)

    baselines = [
        ("Oscar's Grind x20", lambda: OscarsGrind(unit, 20)),
        ("Oscar+Paroli x20 s2/c2", lambda: OscarsParoli(unit, 20, 2, 2)),
        ("Oscar+Paroli x20 s3/c2", lambda: OscarsParoli(unit, 20, 3, 2)),
    ]

    baseline_results = {}
    for label, fn in baselines:
        r = simulate(fn, num_sessions, max_hands, bankroll, stop_loss, seed)
        baseline_results[label] = r
        print(f"  {label:<45} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} {r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% ${r['avg_wager']:>7.0f} {r['wager_ratio']:>5.1f}x")

    # ── HYDRA PARAMETER SWEEP ──
    print(f"\n  --- HYDRA PARAMETER SWEEP ---")

    configs = []
    for gt, ft, ss, smc, spg, sps, fc, mm in product(
        [3, 5, 8],            # grind_thresh
        [15, 20, 30],         # fortress_thresh
        [2, 3],               # surge_streak
        [2, 3, 4],            # surge_max_chain
        [3, 5, 10],           # surge_profit_gate
        [0.05, 0.1, 0.2],    # surge_profit_scale
        [5, 10],              # fortress_cooldown
        [15, 20, 25, 30],     # max_mult
    ):
        if ft <= gt:
            continue
        configs.append({
            'gt': gt, 'ft': ft, 'ss': ss, 'smc': smc,
            'spg': spg, 'sps': sps, 'fc': fc, 'mm': mm,
        })

    print(f"  Sweeping {len(configs)} configurations...")

    results = []
    t0 = time.time()
    for idx, cfg in enumerate(configs):
        if idx % 100 == 0 and idx > 0:
            elapsed = time.time() - t0
            rate = idx / elapsed
            eta = (len(configs) - idx) / rate
            print(f"\r  Config {idx}/{len(configs)} ({elapsed:.0f}s, ~{eta:.0f}s left)   ", end='', flush=True)

        fn = lambda c=cfg: Hydra(
            unit, c['mm'],
            grind_thresh=c['gt'], fortress_thresh=c['ft'],
            surge_streak=c['ss'], surge_max_chain=c['smc'],
            surge_profit_gate=c['spg'], surge_profit_scale=c['sps'],
            fortress_cooldown=c['fc'],
        )
        r = simulate(fn, num_sessions, max_hands, bankroll, stop_loss, seed)
        tag = f"H g{cfg['gt']} f{cfg['ft']} s{cfg['ss']}/{cfg['smc']} pg{cfg['spg']} ps{cfg['sps']} fc{cfg['fc']} x{cfg['mm']}"
        r['tag'] = tag
        r['cfg'] = cfg
        results.append(r)

    elapsed = time.time() - t0
    print(f"\r  Done: {len(configs)} configs in {elapsed:.0f}s" + " " * 40)

    # ── TOP 25 BY MEDIAN PROFIT ──
    by_profit = sorted(results, key=lambda r: r['median'], reverse=True)

    print()
    print("=" * 115)
    print("  TOP 25: PROFIT (ranked by median)")
    print("=" * 115)
    print(hdr)
    print(sep)

    for i, r in enumerate(by_profit[:25]):
        marker = " **" if r['median'] > baseline_results['Oscar+Paroli x20 s2/c2']['median'] else " *" if r['median'] > 0 else ""
        print(f"  {r['tag']:<45} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} {r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% ${r['avg_wager']:>7.0f} {r['wager_ratio']:>5.1f}x{marker}")

    print(f"\n  ** = beats Oscar+Paroli x20 (${baseline_results['Oscar+Paroli x20 s2/c2']['median']:+.2f})")

    # ── TOP 25 BY MEDIAN WITH BUST < 35% ──
    safe_profit = [r for r in results if r['bust_pct'] < 35]
    safe_profit.sort(key=lambda r: r['median'], reverse=True)

    print()
    print("=" * 115)
    print("  TOP 25: PROFIT WITH BUST < 35%")
    print("=" * 115)
    print(hdr)
    print(sep)

    for i, r in enumerate(safe_profit[:25]):
        marker = " **" if r['median'] > baseline_results['Oscar+Paroli x20 s2/c2']['median'] else " *" if r['median'] > 0 else ""
        print(f"  {r['tag']:<45} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} {r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% ${r['avg_wager']:>7.0f} {r['wager_ratio']:>5.1f}x{marker}")

    # ── FORTRESS IMPACT ANALYSIS ──
    print()
    print("=" * 115)
    print("  FORTRESS IMPACT: Does half-bet mode reduce bust?")
    print("=" * 115)

    # Compare best configs at different fortress thresholds
    for mm in [20, 25]:
        print(f"\n  max_mult = x{mm}:")
        print(f"  {'Fortress Thresh':<20} {'Best Median':>10} {'Bust%':>7} {'Win%':>7}")
        print(f"  {'─'*20} {'─'*10} {'─'*7} {'─'*7}")
        for ft in [15, 20, 30, 999]:
            label = f"ft={ft}" if ft < 999 else "NO fortress"
            subset = [r for r in results if r['cfg']['ft'] == ft and r['cfg']['mm'] == mm] if ft < 999 else [r for r in results if r['cfg']['ft'] >= 100 and r['cfg']['mm'] == mm]
            # For "no fortress", use ft=30 with high threshold (effectively never triggers)
            if ft == 999:
                subset = [r for r in results if r['cfg']['ft'] == 30 and r['cfg']['mm'] == mm]
            if subset:
                best = max(subset, key=lambda r: r['median'])
                print(f"  {label:<20} ${best['median']:>+9.2f} {best['bust_pct']:>6.1f}% {best['win_pct']:>6.1f}%")

    # ── SURGE SCALING IMPACT ──
    print()
    print("=" * 115)
    print("  SURGE SCALING: Does profit-proportional Surge help?")
    print("=" * 115)
    print(f"\n  {'Scale':<10} {'Best Median':>10} {'Bust%':>7} {'Win%':>7} {'Wager':>8}")
    print(f"  {'─'*10} {'─'*10} {'─'*7} {'─'*7} {'─'*8}")
    for sps in [0.05, 0.1, 0.2]:
        subset = [r for r in results if r['cfg']['sps'] == sps and r['cfg']['mm'] == 20]
        if subset:
            best = max(subset, key=lambda r: r['median'])
            print(f"  {sps:<10} ${best['median']:>+9.2f} {best['bust_pct']:>6.1f}% {best['win_pct']:>6.1f}% ${best['avg_wager']:>7.0f}")

    # ── SUMMARY ──
    overall_best = by_profit[0]
    safe_best = safe_profit[0] if safe_profit else by_profit[0]
    op_baseline = baseline_results['Oscar+Paroli x20 s2/c2']

    print()
    print("=" * 115)
    print("  SUMMARY")
    print("=" * 115)
    print(f"\n  Oscar+Paroli x20 (baseline):  median ${op_baseline['median']:+.2f} | bust {op_baseline['bust_pct']:.1f}% | win {op_baseline['win_pct']:.1f}%")
    print(f"  HYDRA best (any bust):        median ${overall_best['median']:+.2f} | bust {overall_best['bust_pct']:.1f}% | win {overall_best['win_pct']:.1f}%")
    print(f"    Config: {overall_best['tag']}")
    print(f"  HYDRA best (bust < 35%):      median ${safe_best['median']:+.2f} | bust {safe_best['bust_pct']:.1f}% | win {safe_best['win_pct']:.1f}%")
    print(f"    Config: {safe_best['tag']}")

    beats = overall_best['median'] > op_baseline['median']
    print(f"\n  VERDICT: HYDRA {'BEATS' if beats else 'does NOT beat'} Oscar+Paroli")
    if beats:
        diff = overall_best['median'] - op_baseline['median']
        print(f"  Improvement: +${diff:.2f} median ({diff/abs(op_baseline['median'])*100:.1f}%)")
    print("=" * 115)
