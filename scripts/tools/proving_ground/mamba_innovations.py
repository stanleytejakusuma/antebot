#!/usr/bin/env python3
"""PROVING GROUND — MAMBA Innovation Shootout.

Tests 3 dice strategy innovations against current MAMBA baseline:
A. D'Alembert (linear IOL): +1 unit on loss, -1 unit on win
B. High-chance: 80% win at 5.0x IOL (vs 65% at 3.0x)
C. Hybrid: D'Alembert for first N losses, then Martingale for deep recovery

All strategies: $100 bank, trail 10/60, both trail-only and SL+stop modes.
"""
import random, time
from multiprocessing import Pool, cpu_count

SEED = 42; BANK = 100; MAX_HANDS = 15000


# ============================================================
# BASELINE: Current MAMBA — Dice 65%, IOL 3.0x
# ============================================================

def _mamba_baseline(args):
    s, bank, sl_pct, stop_pct = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < 0.65:
            profit += bet * (99.0 / 65 - 1); mult = 1.0
        else:
            profit -= bet; mult *= 3.0
            if bank + profit > 0 and base * mult > (bank + profit) * 0.95: mult = 1.0
        if bank + profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# A. D'ALEMBERT — Linear IOL: +N units on loss, -1 unit on win
# ============================================================

def _dalembert(args):
    s, bank, sl_pct, stop_pct, chance, add_units, sub_units, max_units = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    units = 1; profit = 0.0; peak = 0.0; ta = False; hands = 0
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * units
        if bet > bal * 0.95: units = 1; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < win_prob:
            profit += bet * payout
            units -= sub_units
            if units < 1: units = 1
        else:
            profit -= bet
            units += add_units
            if max_units > 0 and units > max_units: units = max_units
        if bank + profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and units <= 2: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# B. HIGH-CHANCE — 80% win, aggressive IOL
# ============================================================

def _highchance(args):
    s, bank, sl_pct, stop_pct, chance, iol = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    mult = 1.0; profit = 0.0; peak = 0.0; ta = False; hands = 0
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        bet = base * mult
        if bet > bal * 0.95: mult = 1.0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < win_prob:
            profit += bet * payout; mult = 1.0
        else:
            profit -= bet; mult *= iol
            if bank + profit > 0 and base * mult > (bank + profit) * 0.95: mult = 1.0
        if bank + profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mult <= 1.01: return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# C. HYBRID — D'Alembert first N losses, then Martingale
# ============================================================

def _hybrid(args):
    s, bank, sl_pct, stop_pct, chance, dalembert_cap, mart_iol = args
    rng = random.Random(SEED * 100000 + s)
    base = max(bank / 10000, 0.00101)
    units = 1; mult = 1.0; in_mart = False
    profit = 0.0; peak = 0.0; ta = False; hands = 0
    consec_losses = 0
    payout = 0.99 * 100.0 / chance - 1.0
    win_prob = chance / 100.0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * 10 / 100
    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)
        # Bet sizing: D'Alembert phase or Martingale phase
        if in_mart:
            bet = base * mult
        else:
            bet = base * units
        if bet > bal * 0.95:
            units = 1; mult = 1.0; in_mart = False; consec_losses = 0; bet = base
        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)
        if ta:
            floor = peak * 60 / 100
            mt = profit - floor
            if mt > 0 and bet > mt: bet = max(base, mt)
            if bet < 0.001: return (profit, False, hands)
        hands += 1
        if rng.random() < win_prob:
            profit += bet * payout
            # Reset everything on win
            units = 1; mult = 1.0; in_mart = False; consec_losses = 0
        else:
            profit -= bet
            consec_losses += 1
            if in_mart:
                # Martingale phase: keep doubling
                mult *= mart_iol
                if bank + profit > 0 and base * mult > (bank + profit) * 0.95:
                    mult = 1.0; units = 1; in_mart = False; consec_losses = 0
            else:
                # D'Alembert phase: linear +1
                units += 1
                # Switch to Martingale after dalembert_cap losses
                if consec_losses >= dalembert_cap:
                    in_mart = True
                    mult = units  # Start Mart from current unit level
        if bank + profit <= 0: return (profit, True, hands)
        if profit > peak: peak = profit
        if not ta and profit >= act_t: ta = True
        if ta and profit <= peak * 60 / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and units <= 2 and not in_mart:
            return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)
    return (profit, False, hands)


# ============================================================
# Stats + formatting
# ============================================================

def stats(results):
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    n = len(pnls)
    if n == 0: return {}
    return {
        'median': pnls[n // 2], 'mean': sum(pnls) / n,
        'bust_pct': busts / n * 100,
        'win_pct': sum(1 for p in pnls if p > 0) / n * 100,
        'p10': pnls[n // 10], 'p25': pnls[n // 4],
        'p75': pnls[3 * n // 4], 'p90': pnls[9 * n // 10],
        'avg_hands': sum(r[2] for r in results) / n,
    }

def pr(tag, r):
    ra = r['median'] / abs(r['p10']) if r.get('p10', 0) != 0 and r.get('median', 0) > 0 else -1
    print("  {:<55} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} {:>6.3f} {:>5.0f}".format(
        tag, r['median'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], ra, r['avg_hands']))

H = "  {:<55} {:>8} {:>6} {:>6} {:>8} {:>8} {:>6} {:>5}".format(
    'Config', 'Median', 'Bust%', 'Win%', 'P10', 'P90', 'RA', 'Hands')
SEP = "  {} {} {} {} {} {} {} {}".format('-' * 55, '-' * 8, '-' * 6, '-' * 6, '-' * 8, '-' * 8, '-' * 6, '-' * 5)


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = BANK
    N = 5000

    print()
    print("=" * 130)
    print("  MAMBA INNOVATION SHOOTOUT — D'Alembert vs High-Chance vs Hybrid vs Baseline")
    print("  {} sessions | ${} bank | trail=10/60".format(N, bank))
    print("=" * 130)

    # ================================================================
    # TRAIL ONLY (natural behavior, no safety nets)
    # ================================================================
    print("\n  === TRAIL ONLY (no SL, no stop) ===")
    print(H); print(SEP)

    # Baseline
    args = [(s, bank, 0, 0) for s in range(N)]
    r = stats(pool.map(_mamba_baseline, args)); pr("MAMBA 65% IOL=3.0x (baseline)", r)

    # --- A. D'Alembert variants ---
    print()
    print("  --- A. D'ALEMBERT (linear IOL) ---")
    print(H); print(SEP)
    # (s, bank, sl, stop, chance, add_units, sub_units, max_units)
    for chance in [50, 65, 80]:
        for add, sub in [(1, 1), (2, 1), (3, 1)]:
            for cap in [0, 50, 100]:
                label = "DAL {}% +{}-{} cap={}".format(chance, add, sub, cap if cap else "none")
                args = [(s, bank, 0, 0, chance, add, sub, cap) for s in range(N)]
                r = stats(pool.map(_dalembert, args)); pr(label, r)

    # --- B. High-chance variants ---
    print()
    print("  --- B. HIGH-CHANCE (high win%, aggressive IOL) ---")
    print(H); print(SEP)
    for chance in [75, 80, 85, 90, 95]:
        for iol in [3.0, 5.0, 7.0, 10.0]:
            label = "HICH {}% IOL={}x".format(chance, iol)
            args = [(s, bank, 0, 0, chance, iol) for s in range(N)]
            r = stats(pool.map(_highchance, args)); pr(label, r)

    # --- C. Hybrid variants ---
    print()
    print("  --- C. HYBRID (D'Alembert → Martingale) ---")
    print(H); print(SEP)
    for chance in [50, 65, 80]:
        for dal_cap in [3, 5, 7, 10]:
            for mart_iol in [2.0, 3.0]:
                label = "HYB {}% dal={} mart={}x".format(chance, dal_cap, mart_iol)
                args = [(s, bank, 0, 0, chance, dal_cap, mart_iol) for s in range(N)]
                r = stats(pool.map(_hybrid, args)); pr(label, r)

    # ================================================================
    # GRAND RANKING — all configs
    # ================================================================
    print()
    print("=" * 130)
    print("  Collecting top configs for ranking...")

    # Re-run everything and collect
    all_results = []

    # Baseline
    args = [(s, bank, 0, 0) for s in range(N)]
    r = stats(pool.map(_mamba_baseline, args)); r['tag'] = "MAMBA 65% IOL=3.0x (baseline)"; all_results.append(r)

    # Best D'Alembert configs
    for chance in [50, 65, 80]:
        for add, sub in [(1, 1), (2, 1), (3, 1)]:
            for cap in [0, 50, 100]:
                label = "DAL {}% +{}-{} cap={}".format(chance, add, sub, cap if cap else "none")
                args = [(s, bank, 0, 0, chance, add, sub, cap) for s in range(N)]
                r = stats(pool.map(_dalembert, args)); r['tag'] = label; all_results.append(r)

    for chance in [75, 80, 85, 90, 95]:
        for iol in [3.0, 5.0, 7.0, 10.0]:
            label = "HICH {}% IOL={}x".format(chance, iol)
            args = [(s, bank, 0, 0, chance, iol) for s in range(N)]
            r = stats(pool.map(_highchance, args)); r['tag'] = label; all_results.append(r)

    for chance in [50, 65, 80]:
        for dal_cap in [3, 5, 7, 10]:
            for mart_iol in [2.0, 3.0]:
                label = "HYB {}% dal={} mart={}x".format(chance, dal_cap, mart_iol)
                args = [(s, bank, 0, 0, chance, dal_cap, mart_iol) for s in range(N)]
                r = stats(pool.map(_hybrid, args)); r['tag'] = label; all_results.append(r)

    for r in all_results:
        r['ra'] = r['median'] / abs(r['p10']) if r.get('p10', 0) != 0 and r.get('median', 0) > 0 else -1

    print()
    print("=" * 130)
    print("  TOP 15 BY MEDIAN PROFIT")
    print("=" * 130)
    print(H); print(SEP)
    all_results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(all_results[:15]):
        pr("#{:<2} {}".format(i + 1, r['tag']), r)

    print()
    print("=" * 130)
    print("  TOP 15 BY RISK-ADJUSTED (median / |P10|)")
    print("=" * 130)
    print(H); print(SEP)
    all_results.sort(key=lambda x: x['ra'], reverse=True)
    for i, r in enumerate(all_results[:15]):
        pr("#{:<2} {}".format(i + 1, r['tag']), r)

    print()
    print("=" * 130)
    print("  TOP 10 BY SAFETY (lowest bust%)")
    print("=" * 130)
    print(H); print(SEP)
    safe = [r for r in all_results if r['median'] > 0]
    safe.sort(key=lambda x: (x['bust_pct'], -x['median']))
    for i, r in enumerate(safe[:10]):
        pr("#{:<2} {}".format(i + 1, r['tag']), r)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 130)
