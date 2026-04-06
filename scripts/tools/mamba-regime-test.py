#!/usr/bin/env python3
"""
MAMBA Regime Test — CRUISE/STRIKE/SURGE multi-objective dice strategy
Tests adding Capitalize (SURGE) and flat wager (CRUISE) phases to MAMBA's IOL.

Compares:
  1. MAMBA pure IOL (baseline)
  2. MAMBA + Capitalize (SURGE on win streaks)
  3. Full regime: CRUISE/STRIKE/SURGE
  4. Various capitalize params (streak threshold, max chain, bet multiplier)

Usage:
  python3 mamba-regime-test.py          # Full (5k sessions)
  python3 mamba-regime-test.py --quick  # Quick (2k sessions)
"""

import random
import sys
import time
from itertools import product

CHANCE = 65
WIN_PROB = CHANCE / 100.0
WIN_PAYOUT = 99.0 / CHANCE - 1.0  # +0.523x


# ============================================================
# STRATEGIES
# ============================================================

class MambaBase:
    """Pure MAMBA: IOL on loss, reset on win."""
    name = "MAMBA Pure IOL"

    def __init__(self, base, iol=3.0):
        self.base = base
        self.iol = iol
        self.bet = base
        self.ws = 0
        self.ls = 0

    def update(self, won):
        if won:
            self.ws += 1
            self.ls = 0
            self.bet = self.base
        else:
            self.ls += 1
            self.ws = 0
            self.bet *= self.iol


class MambaCapitalize:
    """MAMBA + Capitalize: IOL base + Paroli on win streaks."""
    name = "MAMBA+Cap"

    def __init__(self, base, iol=3.0, cap_streak=3, cap_max=2, cap_mult=2.0):
        self.base = base
        self.iol = iol
        self.cap_streak = cap_streak  # wins needed to trigger capitalize
        self.cap_max = cap_max        # max capitalize bets
        self.cap_mult = cap_mult      # bet multiplier during capitalize
        self.bet = base
        self.ws = 0
        self.ls = 0
        self.mode = 'strike'  # strike or cap
        self.cap_count = 0
        # Counters
        self.strike_bets = 0
        self.cap_bets = 0
        self.cap_wins = 0
        self.cap_losses = 0
        self.cap_activations = 0

    def update(self, won):
        if won:
            self.ws += 1
            self.ls = 0
        else:
            self.ws = 0
            self.ls += 1

        if self.mode == 'strike':
            self.strike_bets += 1
            if won:
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'cap'
                    self.cap_count = 0
                    self.cap_activations += 1
                    self.bet = self.base * self.cap_mult
            else:
                self.bet *= self.iol

        elif self.mode == 'cap':
            self.cap_bets += 1
            self.cap_count += 1
            if won:
                self.cap_wins += 1
                if self.cap_count >= self.cap_max:
                    self.mode = 'strike'
                    self.ws = 0
                    self.bet = self.base
                else:
                    self.bet = min(self.bet * self.cap_mult, self.base * 50)
            else:
                self.cap_losses += 1
                self.mode = 'strike'
                self.ws = 0
                # Loss during cap — go to IOL recovery
                self.bet *= self.iol

        self.bet = max(self.base, self.bet)


class RegimeStrategy:
    """
    Full 3-regime: CRUISE / STRIKE / SURGE
    CRUISE: flat bet (wager accumulation, minimal risk)
    STRIKE: IOL on loss (profit recovery)
    SURGE: Paroli on win streaks (capitalize)
    """
    name = "Regime"

    def __init__(self, base, iol=3.0, cap_streak=3, cap_max=2, cap_mult=2.0):
        self.base = base
        self.iol = iol
        self.cap_streak = cap_streak
        self.cap_max = cap_max
        self.cap_mult = cap_mult
        self.bet = base
        self.ws = 0
        self.ls = 0
        self.mode = 'cruise'
        self.cap_count = 0
        # Counters
        self.cruise_bets = 0
        self.strike_bets = 0
        self.surge_bets = 0
        self.surge_activations = 0
        self.surge_wins = 0
        self.surge_losses = 0

    def update(self, won):
        if won:
            self.ws += 1
            self.ls = 0
        else:
            self.ws = 0
            self.ls += 1

        if self.mode == 'cruise':
            self.cruise_bets += 1
            if won:
                self.bet = self.base
                if self.ws >= self.cap_streak:
                    self.mode = 'surge'
                    self.cap_count = 0
                    self.surge_activations += 1
                    self.bet = self.base * self.cap_mult
            else:
                # Enter STRIKE (IOL recovery)
                self.mode = 'strike'
                self.bet *= self.iol

        elif self.mode == 'strike':
            self.strike_bets += 1
            if won:
                # Recovered — back to CRUISE
                self.mode = 'cruise'
                self.bet = self.base
                # Check if this win completes a streak for surge
                if self.ws >= self.cap_streak:
                    self.mode = 'surge'
                    self.cap_count = 0
                    self.surge_activations += 1
                    self.bet = self.base * self.cap_mult
            else:
                self.bet *= self.iol

        elif self.mode == 'surge':
            self.surge_bets += 1
            self.cap_count += 1
            if won:
                self.surge_wins += 1
                if self.cap_count >= self.cap_max:
                    self.mode = 'cruise'
                    self.ws = 0
                    self.bet = self.base
                else:
                    self.bet = min(self.bet * self.cap_mult, self.base * 50)
            else:
                self.surge_losses += 1
                # Loss during surge — IOL recovery from the surge bet
                self.mode = 'strike'
                self.ws = 0
                self.bet *= self.iol

        self.bet = max(self.base, self.bet)


# ============================================================
# SIMULATOR
# ============================================================

def sim(strat_fn, bank=1000, num=5000, max_bets=10000, seed=42,
        stop_total_pct=8):
    results = []
    busts = 0

    for s in range(num):
        random.seed(seed * 100000 + s)
        st = strat_fn()
        profit = 0.0
        wagered = 0.0
        bets = 0

        stop_thresh = bank * stop_total_pct / 100

        for _ in range(max_bets):
            bal = bank + profit
            if bal <= 0:
                busts += 1
                break

            bet = st.bet
            if bet > bal * 0.95:
                st.bet = st.base
                bet = st.base
            if bet > bal:
                bet = bal
            if bet < 0.001:
                busts += 1
                break

            wagered += bet
            bets += 1

            won = random.random() < WIN_PROB
            if won:
                profit += bet * WIN_PAYOUT
            else:
                profit -= bet

            if bank + profit <= 0:
                busts += 1
                break

            st.update(won)

            if stop_thresh > 0 and profit >= stop_thresh and st.bet <= st.base * 1.5:
                break

        results.append({
            'pnl': profit,
            'wagered': wagered,
            'bets': bets,
            'strat': st,
        })

    pnls = sorted([r['pnl'] for r in results])
    n = len(pnls)
    avg_wager = sum(r['wagered'] for r in results) / n
    avg_bets = sum(r['bets'] for r in results) / n

    return {
        'median': pnls[n // 2],
        'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10],
        'p90': pnls[9 * n // 10],
        'avg_wager': avg_wager,
        'avg_bets': avg_bets,
        'strats': [r['strat'] for r in results],
    }


def print_row(tag, r, baseline=None):
    marker = ""
    if baseline is not None and r['median'] > baseline:
        marker = " **"
    elif r['median'] > 0:
        marker = " *"
    wgr = r['avg_wager'] / 1000
    mins = r['avg_bets'] / 10 / 60
    print(f"  {tag:<48} ${r['median']:>+8.2f} ${r['mean']:>+8.2f} "
          f"{r['bust_pct']:>5.1f}% {r['win_pct']:>5.1f}% "
          f"${r['p10']:>+8.2f} ${r['p90']:>+8.2f} "
          f"{wgr:>5.1f}x {mins:>5.1f}m{marker}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    num = 2000 if quick else 5000
    bank = 1000
    seed = 42
    base = bank / 10000  # div=10000

    hdr = (f"  {'Config':<48} {'Median':>9} {'Mean':>9} "
           f"{'Bust%':>6} {'Win%':>6} {'P10':>9} {'P90':>9} "
           f"{'Wgr':>6} {'Time':>6}")
    sep = (f"  {'─' * 48} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6} {'─' * 9} {'─' * 9} "
           f"{'─' * 6} {'─' * 6}")

    print()
    print("=" * 120)
    print("  MAMBA REGIME TEST — CRUISE/STRIKE/SURGE")
    print(f"  {num:,} sessions | D65 IOL3.0x div10000 | ${bank:,}")
    print("=" * 120)

    # ============================================================
    # BASELINES at various stop%
    # ============================================================
    for stop in [8, 10, 15, 20, 30]:
        print(f"\n  --- STOP={stop}% ---")
        print(hdr); print(sep)

        # Pure MAMBA baseline
        r_base = sim(lambda: MambaBase(base, 3.0), bank, num, seed=seed, stop_total_pct=stop)
        print_row(f"MAMBA Pure IOL (baseline)", r_base)
        baseline_med = r_base['median']

        # Capitalize sweep
        for cs, cm, cmult in [
            (2, 1, 2.0), (2, 2, 2.0), (3, 1, 2.0), (3, 2, 2.0), (3, 3, 2.0),
            (4, 2, 2.0), (3, 2, 3.0), (3, 2, 1.5), (2, 2, 3.0), (3, 3, 3.0),
        ]:
            tag = f"MAMBA+Cap s{cs}/c{cm}/x{cmult}"
            r = sim(lambda s=cs, m=cm, x=cmult: MambaCapitalize(base, 3.0, s, m, x),
                    bank, num, seed=seed, stop_total_pct=stop)
            print_row(tag, r, baseline_med)

        # Regime sweep
        for cs, cm, cmult in [(3, 2, 2.0), (3, 2, 3.0), (2, 2, 2.0), (3, 3, 2.0)]:
            tag = f"Regime CRUISE/STRIKE/SURGE s{cs}/c{cm}/x{cmult}"
            r = sim(lambda s=cs, m=cm, x=cmult: RegimeStrategy(base, 3.0, s, m, x),
                    bank, num, seed=seed, stop_total_pct=stop)
            print_row(tag, r, baseline_med)

    # ============================================================
    # DETAILED CAPITALIZE ANALYSIS at stop=15%
    # ============================================================
    print(f"\n  === DETAILED CAPITALIZE ANALYSIS (stop=15%) ===")
    print(hdr); print(sep)

    r_base = sim(lambda: MambaBase(base, 3.0), bank, num, seed=seed, stop_total_pct=15)
    print_row("MAMBA Pure IOL", r_base)
    baseline_med = r_base['median']

    all_cap = []
    for cs, cm, cmult in product([2, 3, 4, 5], [1, 2, 3, 4], [1.5, 2.0, 2.5, 3.0]):
        if cm > cs:
            continue  # cap_max can't exceed streak
        tag = f"Cap s{cs}/c{cm}/x{cmult}"
        r = sim(lambda s=cs, m=cm, x=cmult: MambaCapitalize(base, 3.0, s, m, x),
                bank, num, seed=seed, stop_total_pct=15)
        r['tag'] = tag
        r['cfg'] = (cs, cm, cmult)
        all_cap.append(r)

    by_med = sorted(all_cap, key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 15 CAPITALIZE CONFIGS:")
    print(hdr); print(sep)
    for r in by_med[:15]:
        print_row(r['tag'], r, baseline_med)

    safe = [r for r in all_cap if r['bust_pct'] < 20]
    safe.sort(key=lambda r: r['median'], reverse=True)
    print(f"\n  TOP 10 SAFE (<20% bust):")
    print(hdr); print(sep)
    for r in safe[:10]:
        print_row(r['tag'], r, baseline_med)

    # Mode distribution for best configs
    print(f"\n  === MODE DISTRIBUTION (best configs at stop=15%) ===")
    for r in by_med[:5]:
        strats = r['strats']
        cap_strats = [s for s in strats if hasattr(s, 'cap_bets')]
        if cap_strats:
            avg_strike = sum(s.strike_bets for s in cap_strats) / len(cap_strats)
            avg_cap = sum(s.cap_bets for s in cap_strats) / len(cap_strats)
            avg_activations = sum(s.cap_activations for s in cap_strats) / len(cap_strats)
            avg_cap_wins = sum(s.cap_wins for s in cap_strats) / len(cap_strats)
            avg_cap_losses = sum(s.cap_losses for s in cap_strats) / len(cap_strats)
            cap_wr = avg_cap_wins / max(avg_cap_wins + avg_cap_losses, 1) * 100
            total = avg_strike + avg_cap
            print(f"  {r['tag']:<40} Strike: {avg_strike:.0f} ({avg_strike/total*100:.0f}%) | "
                  f"Cap: {avg_cap:.0f} ({avg_cap/total*100:.0f}%) | "
                  f"Activations: {avg_activations:.1f} | Cap W/L: {cap_wr:.0f}%")

    # ============================================================
    # WAGER COMPARISON
    # ============================================================
    print(f"\n  === WAGER GENERATION COMPARISON (stop=20%) ===")
    print(f"  {'Config':<48} {'Median':>9} {'Wager':>10} {'Wager/hr':>10} {'Bust%':>6}")
    print(f"  {'─' * 48} {'─' * 9} {'─' * 10} {'─' * 10} {'─' * 6}")

    for tag, fn in [
        ("MAMBA Pure IOL", lambda: MambaBase(base, 3.0)),
        ("MAMBA+Cap s3/c2/x2", lambda: MambaCapitalize(base, 3.0, 3, 2, 2.0)),
        ("MAMBA+Cap s2/c2/x2", lambda: MambaCapitalize(base, 3.0, 2, 2, 2.0)),
        ("Regime s3/c2/x2", lambda: RegimeStrategy(base, 3.0, 3, 2, 2.0)),
        ("MAMBA+Cap s3/c2/x3", lambda: MambaCapitalize(base, 3.0, 3, 2, 3.0)),
    ]:
        r = sim(fn, bank, num, seed=seed, stop_total_pct=20)
        wgr_total = r['avg_wager']
        session_hrs = r['avg_bets'] / 10 / 3600
        wgr_per_hr = wgr_total / session_hrs if session_hrs > 0 else 0
        print(f"  {tag:<48} ${r['median']:>+8.2f} ${wgr_total:>8.2f} ${wgr_per_hr:>8.0f}/hr {r['bust_pct']:>5.1f}%")

    # ============================================================
    # SUMMARY
    # ============================================================
    print()
    print("=" * 120)
    print("  SUMMARY")
    print("=" * 120)

    # Best capitalize config
    if by_med:
        best = by_med[0]
        print(f"\n  Best capitalize (stop=15%): {best['tag']} — median ${best['median']:+.2f} | bust {best['bust_pct']:.1f}%")
        print(f"  MAMBA baseline (stop=15%):  median ${baseline_med:+.2f}")
        delta = best['median'] - baseline_med
        print(f"  Delta: ${delta:+.2f} ({'BETTER' if delta > 0 else 'WORSE'})")

    if safe:
        best_safe = safe[0]
        print(f"  Best safe capitalize:       {best_safe['tag']} — median ${best_safe['median']:+.2f} | bust {best_safe['bust_pct']:.1f}%")
    print("=" * 120)
