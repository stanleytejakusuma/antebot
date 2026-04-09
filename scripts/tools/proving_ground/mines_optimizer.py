#!/usr/bin/env python3
"""PROVING GROUND — Mines strategy optimizer.

Sweeps mines/fields configurations, IOL multipliers, and recovery modes
to find optimal mines setups for session-level profitability.

Mines math (5x5 grid, 1% house edge):
  win_prob = product((25-mines-i)/(25-i)) for i in range(fields)
  net_payout = 0.99 / win_prob - 1.0
  EV per bet = win_prob * net_payout - (1-win_prob) = -0.01 (always -1%)
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proving_ground.monte_carlo import run_mc
from proving_ground.strategy import FlatStrategy, IOLStrategy
from proving_ground.engines import MinesEngine


def pr(tag, r):
    print("  {:<58} ${:>+7.2f} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f}".format(
        tag, r['median'], r['mean'], r['bust_pct'], r['win_pct'], r['p10'], r['p90']))


H = "  {:<58} {:>8} {:>8} {:>6} {:>6} {:>8} {:>8}".format(
    'Strategy', 'Med', 'Mean', 'Bust%', 'Win%', 'P10', 'P90')
S = "  {} {} {} {} {} {} {}".format('-'*58, '-'*8, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8)


def mines_stats(mines, fields):
    """Return (win_prob, net_payout) for a mines config."""
    safe = 25 - mines
    prob = 1.0
    for i in range(fields):
        prob *= (safe - i) / (25.0 - i)
    net = 0.99 / prob - 1.0
    return prob, net


def main():
    num = 5000
    bank = 100
    base_params = dict(bank=bank, divider=10000, stop_pct=15, sl_pct=15,
                       trail_act=8, trail_lock=60, seed=42)

    print()
    print("=" * 110)
    print("  PROVING GROUND — MINES OPTIMIZER")
    print("  {} sessions | ${} bank | trail=8/60 SL=15% stop=15%".format(num, bank))
    print("=" * 110)

    # ===================================================================
    # PART 1: Configuration landscape — what mines/fields combos exist?
    # ===================================================================
    print("\n  === MINES CONFIGURATION LANDSCAPE ===")
    print("  {:<8} {:<8} {:>8} {:>10} {:>12}".format(
        'Mines', 'Fields', 'WinProb%', 'NetPayout', 'IOL check'))
    print("  {} {} {} {} {}".format('-'*8, '-'*8, '-'*8, '-'*10, '-'*12))

    viable_configs = []
    for m in [1, 2, 3, 4, 5, 8, 10]:
        for f in [1, 2, 3, 4, 5, 6, 8]:
            if f > 25 - m:
                continue  # can't pick more fields than safe tiles
            wp, np_ = mines_stats(m, f)
            if wp < 0.30 or wp > 0.96:
                continue  # outside IOL-viable range
            # IOL viability: need iol * net_payout > 1.0 for recovery
            iol3_check = 3.0 * np_
            viable = "OK" if iol3_check > 1.0 else "weak" if iol3_check > 0.5 else "NO"
            print("  {:<8} {:<8} {:>7.1f}% {:>9.4f}x {:>8} ({:.2f})".format(
                m, f, wp*100, np_, viable, iol3_check))
            viable_configs.append((m, f, wp, np_))

    # ===================================================================
    # PART 2: Flat baseline for all viable configs
    # ===================================================================
    print("\n  === FLAT BASELINE (no IOL) ===")
    print(H); print(S)

    flat_results = []
    for m, f, wp, np_ in viable_configs:
        if wp < 0.50 or wp > 0.92:
            continue  # narrow to most interesting range for readability
        s = FlatStrategy("mines")
        e = MinesEngine(mines=m, fields=f)
        r = run_mc(s, e, base_params, num=num)
        tag = 'Flat m={} f={} (win={:.0f}% pay={:.3f}x)'.format(m, f, wp*100, np_)
        r['tag'] = tag
        r['mines'] = m; r['fields'] = f; r['wp'] = wp; r['np'] = np_
        flat_results.append(r)
        pr(tag, r)

    # ===================================================================
    # PART 3: IOL sweep on promising configs
    # ===================================================================
    print("\n  === IOL SWEEP (best configs) ===")
    print(H); print(S)

    # Pick configs where IOL 3x recovery math works: 3.0 * net_payout > 1.0
    iol_configs = [(m, f, wp, np_) for m, f, wp, np_ in viable_configs
                   if 3.0 * np_ > 1.0 and 0.50 <= wp <= 0.92]

    iol_results = []
    for m, f, wp, np_ in iol_configs:
        for iol in [2.0, 2.5, 3.0, 3.5]:
            if iol * np_ < 0.8:
                continue  # skip combos where recovery is too weak
            s = IOLStrategy(iol=iol, game="mines")
            e = MinesEngine(mines=m, fields=f)
            r = run_mc(s, e, base_params, num=num)
            tag = 'm={} f={} IOL={:.1f}x (win={:.0f}% pay={:.3f}x)'.format(
                m, f, iol, wp*100, np_)
            r['tag'] = tag
            r['mines'] = m; r['fields'] = f; r['iol'] = iol
            r['wp'] = wp; r['np'] = np_
            iol_results.append(r)
            pr(tag, r)

    # ===================================================================
    # PART 4: Yoanium-style field shift (use different engine during recovery)
    # Not possible with current session runner (single engine per session),
    # so we test the recovery config directly to understand its properties.
    # ===================================================================
    print("\n  === YOANIUM REFERENCE: m=5 f=1 base / m=5 f=2 recovery ===")
    print(H); print(S)

    # Yoanium base mode: m=5, f=1, 80% win, +0.2375x net
    s = IOLStrategy(iol=3.0, game="mines")
    e = MinesEngine(mines=5, fields=1)
    r = run_mc(s, e, base_params, num=num)
    r['tag'] = 'Yoanium base: m=5 f=1 IOL=3.0x (80% +0.24x)'
    pr(r['tag'], r)
    iol_results.append(r)

    # Yoanium recovery mode: m=5, f=2, 63% win, +0.56x net
    s = IOLStrategy(iol=3.0, game="mines")
    e = MinesEngine(mines=5, fields=2)
    r = run_mc(s, e, base_params, num=num)
    r['tag'] = 'Yoanium recov: m=5 f=2 IOL=3.0x (63% +0.56x)'
    pr(r['tag'], r)
    iol_results.append(r)

    # What if Yoanium used f=2 all the time?
    s = FlatStrategy("mines")
    e = MinesEngine(mines=5, fields=2)
    r = run_mc(s, e, base_params, num=num)
    r['tag'] = 'Flat m=5 f=2 (63% +0.56x) — no IOL baseline'
    pr(r['tag'], r)

    # ===================================================================
    # PART 5: Cross-game comparison (best mines vs snake family)
    # ===================================================================
    print("\n  === CROSS-GAME: BEST MINES vs SNAKE FAMILY ===")
    print(H); print(S)

    from proving_ground.engines import DiceEngine, RouletteEngine

    # Top mines configs (manually select from sweep)
    top_mines = sorted(iol_results, key=lambda x: x['median'], reverse=True)[:5]
    for r in top_mines:
        pr(r['tag'], r)

    # MAMBA reference
    s = IOLStrategy(iol=3.0, game="dice")
    e = DiceEngine(65)
    r = run_mc(s, e, base_params, num=num)
    r['tag'] = 'MAMBA dice 65% IOL=3.0x'
    pr(r['tag'], r)

    # COBRA reference
    s = IOLStrategy(iol=3.0, game="roulette")
    e = RouletteEngine(23)
    r = run_mc(s, e, base_params, num=num)
    r['tag'] = 'COBRA roulette 23num IOL=3.0x'
    pr(r['tag'], r)

    # ===================================================================
    # GRAND RANKING
    # ===================================================================
    all_results = flat_results + iol_results
    all_results.sort(key=lambda x: x['median'], reverse=True)

    print()
    print("=" * 110)
    print("  GRAND RANKING — All mines strategies by median profit")
    print("=" * 110)
    print(H); print(S)
    for i, r in enumerate(all_results[:20]):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    elapsed = time.time() - t0
    print("\n  Runtime: {:.1f}s".format(elapsed))
    print("=" * 110)


t0 = time.time()
if __name__ == "__main__":
    main()
