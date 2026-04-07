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
            bet_cap_pct, coil_mult, coil_max_hands, vault_pct,
            trail_act, trail_lock, sl_pct, stop_pct)
    """
    (s, bank, div, brake_at, cap_streak, cap_max, delay,
     bet_cap_pct, coil_mult, coil_max_hands, vault_pct,
     trail_act, trail_lock, sl_pct, stop_pct) = args

    rng = random.Random(SEED * 100000 + s)
    unit = max(bank / div, 0.001)
    start_bank = bank
    bet = unit; profit = 0.0; peak = 0.0; ta = False; hands = 0
    mode = 0  # 0=strike, 1=coil, 2=capitalize
    ls = 0; ws = 0; consec_ls = 0; cap_count = 0
    coil_deficit = 0.0; coil_hands = 0
    vault_thresh = start_bank * vault_pct / 100 if vault_pct > 0 else 0
    total_vaulted = 0.0; profit_at_vault = 0.0
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
                    coil_deficit = 0; coil_hands = 0
                    mode = 1
                else:
                    # PATIENCE: only Martingale after `delay` consecutive losses
                    if delay > 0 and consec_ls <= delay:
                        pass  # Absorb at current bet (no doubling)
                    else:
                        bet = bet * 2

        elif mode == 1:  # COIL
            coil_hands += 1
            coil_deficit += pnl
            if is_win and coil_deficit >= 0:
                mode = 0; bet = unit; consec_ls = 0  # Recovered
                if ws >= cap_streak:
                    mode = 2; cap_count = 0
            # Coil escape: abandon chain after N hands
            elif coil_max_hands > 0 and coil_hands >= coil_max_hands:
                mode = 0; bet = unit; consec_ls = 0

        elif mode == 2:  # CAPITALIZE
            cap_count += 1
            if is_loss or cap_count >= cap_max:
                mode = 0; bet = unit; ws = 0
            elif is_win:
                bet = bet * 2

        if bet < unit: bet = unit

        # === Vault ===
        if vault_thresh > 0 and mode == 0 and bet <= unit * 1.01:
            current_profit = profit - profit_at_vault
            if current_profit >= vault_thresh:
                total_vaulted += current_profit
                profit_at_vault = profit
                unit = max((start_bank + profit - total_vaulted) / div, 0.001)
                bet = unit

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
               coil_max=0, vault=0, ta=10, tl=60, sl=15, stop=15):
    """Run a config and return (label, stats_dict)."""
    args = [(s, bank, div, brake, cs, cm, delay, cap, coil, coil_max, vault,
             ta, tl, sl, stop)
            for s in range(num)]
    r = stats(pool.map(_viper, args))
    r['tag'] = label
    return r


if __name__ == "__main__":
    t0 = time.time()
    pool = Pool(cpu_count())
    bank = BANK
    N = 5000

    print()
    print("=" * 130)
    print("  VIPER v4.1 WEAKNESS FIX OPTIMIZER — Coil Escape + Vault")
    print("  Calibrated BJ model (-0.52% edge) | ${} bank | trail=10/60".format(bank))
    print("=" * 130)

    all_results = []

    # ================================================================
    # BASELINE: v4.0 (no coil escape, no vault)
    # ================================================================
    print("\n  === BASELINE (trail only, no SL/stop) ===")
    print(H); print(SEP)

    base = run_config(pool, "v4.0 BASELINE (no fixes)", N, bank,
                      4000, 12, 2, 3, 1, 0, 1.0, coil_max=0, vault=0,
                      ta=10, tl=60, sl=0, stop=0)
    all_results.append(base); pr(base['tag'], base)

    # Also with SL+stop for reference
    base_safe = run_config(pool, "v4.0 BASELINE (SL+stop)", N, bank,
                           4000, 12, 2, 3, 1, 0, 1.0, coil_max=0, vault=0,
                           ta=10, tl=60, sl=15, stop=15)
    all_results.append(base_safe); pr(base_safe['tag'], base_safe)

    # ================================================================
    # COIL ESCAPE SWEEP (trail only)
    # ================================================================
    print("\n  === COIL ESCAPE SWEEP (trail only) ===")
    print(H); print(SEP)

    for cm in [5, 10, 15, 20, 30, 50]:
        label = "coilMax={}".format(cm)
        r = run_config(pool, label, N, bank,
                       4000, 12, 2, 3, 1, 0, 1.0, coil_max=cm, vault=0,
                       ta=10, tl=60, sl=0, stop=0)
        all_results.append(r); pr(label, r)

    # ================================================================
    # VAULT SWEEP (trail only)
    # ================================================================
    print("\n  === VAULT SWEEP (trail only) ===")
    print(H); print(SEP)

    for vp in [3, 5, 8, 10]:
        label = "vault={}%".format(vp)
        r = run_config(pool, label, N, bank,
                       4000, 12, 2, 3, 1, 0, 1.0, coil_max=0, vault=vp,
                       ta=10, tl=60, sl=0, stop=0)
        all_results.append(r); pr(label, r)

    # ================================================================
    # COMBINED: Coil Escape × Vault (trail only)
    # ================================================================
    print("\n  === COMBINED: Coil Escape x Vault (trail only) ===")
    print(H); print(SEP)

    for cm in [10, 15, 20, 30]:
        for vp in [0, 5, 8]:
            label = "coilMax={} vault={}%".format(cm, vp)
            r = run_config(pool, label, N, bank,
                           4000, 12, 2, 3, 1, 0, 1.0, coil_max=cm, vault=vp,
                           ta=10, tl=60, sl=0, stop=0)
            all_results.append(r); pr(label, r)

    # ================================================================
    # COMBINED with SL+stop (production config)
    # ================================================================
    print("\n  === BEST CONFIGS with SL=15% + stop=15% ===")
    print(H); print(SEP)

    prod_configs = [
        ("v4.0 (no fixes, SL+stop)",       0, 0),
        ("coilMax=15 (SL+stop)",           15, 0),
        ("coilMax=20 (SL+stop)",           20, 0),
        ("vault=8% (SL+stop)",              0, 8),
        ("coilMax=15 vault=8% (SL+stop)",  15, 8),
        ("coilMax=20 vault=8% (SL+stop)",  20, 8),
        ("coilMax=20 vault=5% (SL+stop)",  20, 5),
        ("coilMax=30 vault=8% (SL+stop)",  30, 8),
    ]
    for label, cm, vp in prod_configs:
        r = run_config(pool, label, N, bank,
                       4000, 12, 2, 3, 1, 0, 1.0, coil_max=cm, vault=vp,
                       ta=10, tl=60, sl=15, stop=15)
        all_results.append(r); pr(label, r)

    # ================================================================
    # GRAND RANKING
    # ================================================================
    print()
    print("=" * 130)
    print("  GRAND RANKING — by median profit (all configs)")
    print("=" * 130)
    print(H); print(SEP)

    for r in all_results:
        r['ra'] = r['median'] / abs(r['p10']) if r.get('p10', 0) != 0 and r.get('median', 0) > 0 else -1

    all_results.sort(key=lambda x: x['median'], reverse=True)
    for i, r in enumerate(all_results):
        pr("#{:<2} {}".format(i+1, r['tag']), r)

    pool.close(); pool.join()
    print("\n  Runtime: {:.1f}s".format(time.time() - t0))
    print("=" * 130)
