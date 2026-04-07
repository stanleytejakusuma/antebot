#!/usr/bin/env python3
"""PROVING GROUND — VIPER v4.0 Profit Optimizer.

Tests innovations from across the Snake Family applied to VIPER:
- PATIENCE (from BASILISK): delayed Martingale activation
- BET CAP (from TAIPAN): hard max bet as % of balance
- Capitalize tuning: streak/max Paroli configuration
- Divider/brake exploration: risk/reward dial
- Coil reduction: reduce house edge drag during coil grinding

Calibrated BJ model: -0.52% house edge (6-deck S17 basic strategy)
"""
import random, time
from multiprocessing import Pool, cpu_count

SEED = 42; BANK = 100; MAX_HANDS = 15000


def _viper(args):
    """Parametrized VIPER session.

    args = (s, bank, div, brake_at, cap_streak, cap_max, delay,
            bet_cap_pct, coil_mult, trail_act, trail_lock, sl_pct, stop_pct)
    """
    (s, bank, div, brake_at, cap_streak, cap_max, delay,
     bet_cap_pct, coil_mult, trail_act, trail_lock, sl_pct, stop_pct) = args

    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / div, 0.001)
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0
    mode = 0  # 0=strike, 1=coil, 2=capitalize
    ls = 0; ws = 0; consec_ls = 0; cap_count = 0
    coil_deficit = 0.0
    stop_t = bank * stop_pct / 100 if stop_pct > 0 else 0
    sl_t = bank * sl_pct / 100 if sl_pct > 0 else 0
    act_t = bank * trail_act / 100 if trail_act > 0 else 0

    for _ in range(MAX_HANDS):
        bal = bank + profit
        if bal <= 0: return (profit, True, hands)

        # Soft bust
        if bet > bal * 0.95:
            bet = unit; mode = 0; ls = 0; consec_ls = 0

        # Bet cap
        if bet_cap_pct > 0:
            max_allowed = bal * bet_cap_pct / 100
            if bet > max_allowed:
                bet = max_allowed

        if bet > bal: bet = bal
        if bet < 0.001: return (profit, True, hands)

        # Trail-aware cap
        if ta:
            floor = peak * trail_lock / 100
            mt = profit - floor
            if mt > 0 and bet > mt:
                bet = max(unit, mt)
            if bet < 0.001: return (profit, False, hands)

        hands += 1

        # === Resolve BJ hand (calibrated model, -0.52% edge) ===
        hand_type = rng.random()
        r = rng.random()
        if hand_type < 0.0475:
            pnl = bet * 1.5  # Blackjack
        elif hand_type < 0.0475 + 0.095:
            actual_bet = bet * 2  # Double
            if r < 0.56: pnl = actual_bet
            elif r < 0.56 + 0.36: pnl = -actual_bet
            else: pnl = 0
        elif hand_type < 0.0475 + 0.095 + 0.025:
            actual_bet = bet * 2.1  # Split
            if r < 0.48: pnl = actual_bet
            elif r < 0.48 + 0.44: pnl = -actual_bet
            else: pnl = 0
        else:
            if r < 0.387: pnl = bet  # Normal win
            elif r < 0.387 + 0.527: pnl = -bet  # Normal loss
            else: pnl = 0  # Push

        profit += pnl
        is_win = pnl > 0
        is_loss = pnl < 0

        if is_win:
            ws += 1; ls = 0; consec_ls = 0
        elif is_loss:
            ls += 1; ws = 0; consec_ls += 1

        if profit > peak: peak = profit

        # === Mode logic ===
        if mode == 0:  # STRIKE
            if is_win:
                bet = unit
                if ws >= cap_streak:
                    mode = 2; cap_count = 0  # → CAPITALIZE
            elif is_loss:
                if brake_at > 0 and ls >= brake_at:
                    # BRAKE → COIL
                    if coil_mult < 1.0:
                        bet = bet * coil_mult  # Reduce coil bet
                    coil_deficit = 0
                    mode = 1
                else:
                    # PATIENCE: only Martingale after `delay` consecutive losses
                    if delay > 0 and consec_ls <= delay:
                        pass  # Absorb at current bet (no doubling)
                    else:
                        bet = bet * 2

        elif mode == 1:  # COIL
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit  # Recovered
                if ws >= cap_streak:
                    mode = 2; cap_count = 0

        elif mode == 2:  # CAPITALIZE
            cap_count += 1
            if is_loss or cap_count >= cap_max:
                mode = 0; bet = unit; ws = 0
            elif is_win:
                bet = bet * 2

        if bet < unit: bet = unit

        # === Stops ===
        if bank + profit <= 0: return (profit, True, hands)
        if not ta and act_t > 0 and profit >= act_t: ta = True
        if ta and profit > peak: peak = profit
        if ta and profit <= peak * trail_lock / 100: return (profit, False, hands)
        if stop_t > 0 and profit >= stop_t and mode == 0 and ls == 0:
            return (profit, False, hands)
        if sl_t > 0 and profit <= -sl_t: return (profit, False, hands)

    return (profit, False, hands)


def stats(results):
    pnls = sorted([r[0] for r in results])
    busts = sum(1 for r in results if r[1])
    n = len(pnls)
    if n == 0: return {}
    return {
        'median': pnls[n//2], 'mean': sum(pnls)/n, 'bust_pct': busts/n*100,
        'win_pct': sum(1 for p in pnls if p > 0)/n*100,
        'p10': pnls[n//10], 'p90': pnls[9*n//10],
        'avg_hands': sum(r[2] for r in results) / n,
    }

def pr(tag, r):
    ra = r['median'] / abs(r['p10']) if r.get('p10', 0) != 0 and r.get('median', 0) > 0 else -1
    print("  {:<55} ${:>+7.2f} {:>5.1f}% {:>5.1f}% ${:>+7.2f} ${:>+7.2f} {:>6.3f} {:>5.0f}".format(
        tag, r['median'], r['bust_pct'], r['win_pct'], r['p10'], r['p90'], ra, r['avg_hands']))

H = "  {:<55} {:>8} {:>6} {:>6} {:>8} {:>8} {:>6} {:>5}".format(
    'Config', 'Median', 'Bust%', 'Win%', 'P10', 'P90', 'RA', 'Hands')
SEP = "  {} {} {} {} {} {} {} {}".format('-'*55, '-'*8, '-'*6, '-'*6, '-'*8, '-'*8, '-'*6, '-'*5)


def run_config(pool, label, num, bank, div, brake, cs, cm, delay, cap, coil,
               ta=10, tl=60, sl=15, stop=15):
    """Run a config and return (label, stats_dict)."""
    args = [(s, bank, div, brake, cs, cm, delay, cap, coil, ta, tl, sl, stop)
            for s in range(num)]
    r = stats(pool.map(_viper, args))
    r['tag'] = label
    return r


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = BANK
    N1 = 3000  # Phase 1-3 sessions
    N2 = 5000  # Phase 4 validation

    print()
    print("=" * 130)
    print("  VIPER v4.0 PROFIT OPTIMIZER")
    print("  Calibrated BJ model (-0.52% edge) | ${} bank | trail=10/60 | SL=15% | stop=15%".format(bank))
    print("=" * 130)

    all_results = []

    # ================================================================
    # PHASE 1: Divider × Brake (core risk dial)
    # ================================================================
    print("\n  === PHASE 1: Divider × Brake ({} sessions) ===".format(N1))
    print("  cap=2/2, delay=0, betCap=0, coil=1.0 (current defaults)")
    print(H); print(SEP)

    for div in [3000, 4000, 5000, 6000, 8000]:
        for brake in [6, 8, 10, 12]:
            label = "div={} brake={}".format(div, brake)
            r = run_config(pool, label, N1, bank, div, brake, 2, 2, 0, 0, 1.0)
            all_results.append(r)
            pr(label, r)

    # ================================================================
    # PHASE 2: Capitalize tuning (on promising div/brake combos)
    # ================================================================
    print("\n  === PHASE 2: Capitalize Tuning ({} sessions) ===".format(N1))
    print("  Testing on div=4000/5000, brake=10")
    print(H); print(SEP)

    for div in [4000, 5000]:
        for cs in [1, 2]:
            for cm in [1, 2, 3]:
                label = "div={} b=10 cap={}/{}".format(div, cs, cm)
                r = run_config(pool, label, N1, bank, div, 10, cs, cm, 0, 0, 1.0)
                all_results.append(r)
                pr(label, r)

    # ================================================================
    # PHASE 3: PATIENCE + BetCap + CoilReduction (innovation layer)
    # ================================================================
    print("\n  === PHASE 3: Innovations ({} sessions) ===".format(N1))
    print("  PATIENCE (delay), BET CAP, coil reduction")
    print(H); print(SEP)

    # PATIENCE exploration (on best div/brake)
    for div in [4000, 5000]:
        for delay in [1, 2]:
            label = "div={} b=10 PATIENCE={}".format(div, delay)
            r = run_config(pool, label, N1, bank, div, 10, 2, 2, delay, 0, 1.0)
            all_results.append(r)
            pr(label, r)

    # BetCap exploration
    for div in [4000, 5000]:
        for cap in [10, 15, 20]:
            label = "div={} b=10 betCap={}%".format(div, cap)
            r = run_config(pool, label, N1, bank, div, 10, 2, 2, 0, cap, 1.0)
            all_results.append(r)
            pr(label, r)

    # Coil reduction
    for div in [4000, 5000]:
        for coil in [0.5, 0.25]:
            label = "div={} b=10 coil={}x".format(div, coil)
            r = run_config(pool, label, N1, bank, div, 10, 2, 2, 0, 0, coil)
            all_results.append(r)
            pr(label, r)

    # Stacked innovations (best combinations)
    print("\n  === PHASE 3b: Stacked Innovations ===")
    print(H); print(SEP)

    combos = [
        ("div=4000 b=10 PAT=1 cap=15%",        4000, 10, 2, 2, 1, 15, 1.0),
        ("div=4000 b=10 PAT=1 cap=20%",        4000, 10, 2, 2, 1, 20, 1.0),
        ("div=4000 b=10 PAT=1 coil=0.5",       4000, 10, 2, 2, 1, 0,  0.5),
        ("div=4000 b=10 PAT=1 cap=15% coil=0.5", 4000, 10, 2, 2, 1, 15, 0.5),
        ("div=5000 b=10 PAT=1 cap=15%",        5000, 10, 2, 2, 1, 15, 1.0),
        ("div=5000 b=10 PAT=1 cap=20%",        5000, 10, 2, 2, 1, 20, 1.0),
        ("div=5000 b=10 PAT=1 coil=0.5",       5000, 10, 2, 2, 1, 0,  0.5),
        ("div=4000 b=12 PAT=1 cap=20%",        4000, 12, 2, 2, 1, 20, 1.0),
        ("div=4000 b=10 cap=1/3 PAT=1 cap=15%", 4000, 10, 1, 3, 1, 15, 1.0),
        ("div=4000 b=10 cap=2/3 PAT=1 cap=15%", 4000, 10, 2, 3, 1, 15, 1.0),
        ("div=5000 b=10 cap=2/3 PAT=1",        5000, 10, 2, 3, 1, 0,  1.0),
        ("div=4000 b=10 PAT=2 cap=15%",        4000, 10, 2, 2, 2, 15, 1.0),
    ]
    for label, div, brake, cs, cm, delay, cap, coil in combos:
        r = run_config(pool, label, N1, bank, div, brake, cs, cm, delay, cap, coil)
        all_results.append(r)
        pr(label, r)

    # ================================================================
    # GRAND RANKING
    # ================================================================
    print()
    print("=" * 130)
    print("  GRAND RANKING — by median profit (top 20)")
    print("=" * 130)
    print(H); print(SEP)

    # Add RA to all results
    for r in all_results:
        r['ra'] = r['median'] / abs(r['p10']) if r.get('p10', 0) != 0 and r.get('median', 0) > 0 else -1

    all_results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(all_results[:20]):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    print()
    print("=" * 130)
    print("  RISK-ADJUSTED RANKING — top 10 by median/|P10|")
    print("=" * 130)
    print(H); print(SEP)

    all_results.sort(key=lambda x: x['ra'], reverse=True)
    for i, r in enumerate(all_results[:10]):
        pr("#{:<2} {} (RA={:.3f})".format(i+1, r['tag'], r['ra']), r)

    # ================================================================
    # PHASE 4: Validate top 5 at 5000 sessions
    # ================================================================
    # Pick top 5 by median, deduplicate with top 3 RA
    top_median = sorted(all_results, key=lambda x: x['median'], reverse=True)[:5]
    top_ra = sorted(all_results, key=lambda x: x['ra'], reverse=True)[:3]
    seen = set()
    validate_configs = []
    for r in top_median + top_ra:
        if r['tag'] not in seen:
            seen.add(r['tag'])
            validate_configs.append(r['tag'])

    print()
    print("=" * 130)
    print("  PHASE 4: VALIDATION ({} sessions on top {} configs)".format(N2, len(validate_configs)))
    print("=" * 130)
    print(H); print(SEP)

    # Re-run top configs with more sessions — need to find their params
    # Store params in the tag for reconstruction
    current = run_config(pool, "CURRENT v3.0.1 div=6000 b=10 2/2 d=0",
                         N2, bank, 6000, 10, 2, 2, 0, 0, 1.0)
    pr("CURRENT v3.0.1 (baseline)", current)

    # Re-run specific promising configs at high session count
    val_configs = [
        ("div=4000 b=10",                 4000, 10, 2, 2, 0, 0, 1.0),
        ("div=4000 b=12",                 4000, 12, 2, 2, 0, 0, 1.0),
        ("div=5000 b=10",                 5000, 10, 2, 2, 0, 0, 1.0),
        ("div=4000 b=10 PAT=1",           4000, 10, 2, 2, 1, 0, 1.0),
        ("div=4000 b=10 PAT=1 cap=15%",   4000, 10, 2, 2, 1, 15, 1.0),
        ("div=4000 b=10 PAT=1 cap=20%",   4000, 10, 2, 2, 1, 20, 1.0),
        ("div=4000 b=10 cap=2/3",          4000, 10, 2, 3, 0, 0, 1.0),
        ("div=4000 b=10 cap=2/3 PAT=1",   4000, 10, 2, 3, 1, 0, 1.0),
        ("div=5000 b=10 PAT=1",           5000, 10, 2, 2, 1, 0, 1.0),
        ("div=5000 b=10 cap=2/3 PAT=1",   5000, 10, 2, 3, 1, 0, 1.0),
        ("div=4000 b=10 PAT=1 coil=0.5",  4000, 10, 2, 2, 1, 0, 0.5),
        ("div=4000 b=10 PAT=1 cap=15% coil=0.5", 4000, 10, 2, 2, 1, 15, 0.5),
    ]
    for label, div, brake, cs, cm, delay, cap, coil in val_configs:
        r = run_config(pool, label, N2, bank, div, brake, cs, cm, delay, cap, coil)
        pr(label, r)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 130)
