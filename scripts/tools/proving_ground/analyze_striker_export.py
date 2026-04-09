#!/usr/bin/env python3
"""Analyze STRIKER live session from bets_export JSON.

Reconstructs IOL chains, identifies why recovery is poor.
"""
import json, sys
from collections import defaultdict

FILE = sys.argv[1] if len(sys.argv) > 1 else "/Users/stanz/Downloads/bets_export_2026-04-08.json"

with open(FILE) as f:
    raw = json.load(f)

# Sort chronologically (data is newest-first)
bets = sorted(raw, key=lambda b: (b["createdAt"], b["id"]))

print(f"Total bets in export: {len(bets)}")
print(f"Date range: {bets[0]['createdAt']} → {bets[-1]['createdAt']}")
print()

# Separate sessions by multiplier pattern
# STRIKER = 50% chance → winning multiplier is 1.98
# MAMBA = 65% chance → winning multiplier ~1.5228
# We need to identify STRIKER bets

# Group by approximate session (time gaps > 30s = new session)
from datetime import datetime

def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

sessions = []
current_session = [bets[0]]
for i in range(1, len(bets)):
    t_prev = parse_ts(bets[i-1]["createdAt"])
    t_curr = parse_ts(bets[i]["createdAt"])
    gap = (t_curr - t_prev).total_seconds()
    if gap > 60:  # 60 second gap = new session
        sessions.append(current_session)
        current_session = [bets[i]]
    else:
        current_session.append(bets[i])
if current_session:
    sessions.append(current_session)

print(f"Detected {len(sessions)} sessions (>60s gap)")
print("=" * 100)

for si, sess in enumerate(sessions):
    # Determine strategy by winning multiplier
    win_mults = [b["multiplier"] for b in sess if b["multiplier"] > 0]
    if not win_mults:
        strat = "ALL_LOSS"
        avg_mult = 0
    else:
        avg_mult = sum(win_mults) / len(win_mults)
        if abs(avg_mult - 1.98) < 0.05:
            strat = "STRIKER (50%)"
        elif abs(avg_mult - 1.5228) < 0.1:
            strat = "MAMBA (65%)"
        else:
            strat = f"UNKNOWN (mult={avg_mult:.4f})"

    total_bet = sum(b["betSize"] for b in sess)
    total_payout = sum(b["payout"] for b in sess)
    pnl = total_payout - total_bet
    wins = sum(1 for b in sess if b["multiplier"] > 0)
    losses = sum(1 for b in sess if b["multiplier"] == 0)

    print(f"\nSession {si+1}: {strat} | {len(sess)} bets | "
          f"{sess[0]['createdAt'][:19]} → {sess[-1]['createdAt'][:19]}")
    print(f"  W/L: {wins}/{losses} ({wins/(wins+losses)*100:.1f}% win) | "
          f"Wagered: ${total_bet:.2f} | P&L: ${pnl:+.2f}")

    if "STRIKER" not in strat:
        continue

    # === DEEP STRIKER ANALYSIS ===
    print(f"\n  --- STRIKER CHAIN ANALYSIS ---")

    # Reconstruct balance curve and IOL chains
    # A chain starts at first loss, ends at first win after losses
    chains = []
    current_chain = {"losses": [], "recovery_bet": None, "recovered": False}
    in_chain = False
    balance_curve = []
    running_pnl = 0

    for b in sess:
        is_win = b["multiplier"] > 0
        bet_amt = b["betSize"]
        profit = b["payout"] - bet_amt

        if is_win:
            if in_chain:
                current_chain["recovery_bet"] = b
                current_chain["recovered"] = True
                # Check if recovery covers chain cost
                chain_cost = sum(l["betSize"] for l in current_chain["losses"])
                recovery_profit = b["payout"] - b["betSize"]
                current_chain["chain_cost"] = chain_cost
                current_chain["recovery_profit"] = recovery_profit
                current_chain["net"] = recovery_profit - chain_cost
                current_chain["depth"] = len(current_chain["losses"])
                chains.append(current_chain)
                current_chain = {"losses": [], "recovery_bet": None, "recovered": False}
                in_chain = False
        else:
            in_chain = True
            current_chain["losses"].append(b)

        running_pnl += profit
        balance_curve.append(running_pnl)

    # If session ended mid-chain
    if in_chain and current_chain["losses"]:
        chain_cost = sum(l["betSize"] for l in current_chain["losses"])
        current_chain["chain_cost"] = chain_cost
        current_chain["recovery_profit"] = 0
        current_chain["net"] = -chain_cost
        current_chain["depth"] = len(current_chain["losses"])
        current_chain["recovered"] = False
        chains.append(current_chain)

    if not chains:
        print("  No loss chains found.")
        continue

    # Chain statistics
    recovered = [c for c in chains if c["recovered"]]
    unrecovered = [c for c in chains if not c["recovered"]]
    full_recoveries = [c for c in recovered if c["net"] >= 0]
    partial_recoveries = [c for c in recovered if c["net"] < 0]

    print(f"  Total chains: {len(chains)} | Recovered: {len(recovered)} | "
          f"Unrecovered: {len(unrecovered)}")
    print(f"  Full recovery (net >= 0): {len(full_recoveries)} | "
          f"Partial (win but net < 0): {len(partial_recoveries)}")

    # Chain depth distribution
    depths = [c["depth"] for c in chains]
    print(f"\n  Chain depth distribution:")
    depth_counts = defaultdict(int)
    for d in depths:
        depth_counts[d] += 1
    for d in sorted(depth_counts):
        pct = depth_counts[d] / len(chains) * 100
        print(f"    LS={d}: {depth_counts[d]} chains ({pct:.1f}%)")

    # The critical question: why is recovery bad?
    print(f"\n  === RECOVERY DIAGNOSIS ===")

    # 1. Check bet sizes in chains — are they being capped?
    print(f"\n  1. BET CAP ANALYSIS:")
    for i, c in enumerate(chains):
        if c["depth"] >= 2:
            loss_bets = [l["betSize"] for l in c["losses"]]
            escalation = [loss_bets[j+1]/loss_bets[j] if loss_bets[j] > 0 else 0
                         for j in range(len(loss_bets)-1)]
            recovery_bet = c["recovery_bet"]["betSize"] if c["recovered"] else 0
            chain_cost = c["chain_cost"]

            # Expected: DAL phase (+1 unit), then MART phase (*3x)
            # Check if escalation matches expected pattern
            print(f"    Chain {i+1} (LS={c['depth']}): "
                  f"bets={[f'${b:.2f}' for b in loss_bets]}")
            if c["recovered"]:
                needed = chain_cost / 0.98  # Need to cover chain cost with 0.98x payout
                print(f"      Recovery bet: ${recovery_bet:.2f} | "
                      f"Chain cost: ${chain_cost:.2f} | "
                      f"Needed: ${needed:.2f} | "
                      f"Net: ${c['net']:+.2f} "
                      f"{'✓ FULL' if c['net'] >= 0 else '✗ PARTIAL'}")
                if recovery_bet < needed:
                    shortfall = needed - recovery_bet
                    print(f"      ⚠ Recovery bet ${recovery_bet:.2f} < needed ${needed:.2f} "
                          f"(shortfall: ${shortfall:.2f}) — BET CAP or TRAIL CAP hit")
            else:
                print(f"      ✗ UNRECOVERED — session ended during chain")

            if len(escalation) > 0:
                print(f"      Escalation ratios: {[f'{e:.2f}x' for e in escalation]}")

    # 2. Trail cap analysis — was profit near floor?
    print(f"\n  2. P&L CURVE:")
    peak = max(balance_curve)
    trough = min(balance_curve)
    final = balance_curve[-1]
    print(f"    Peak: ${peak:+.2f} | Trough: ${trough:+.2f} | Final: ${final:+.2f}")

    # Identify where trail would fire (peak - 5% of starting balance)
    # We don't know starting balance exactly, but can estimate from base bet
    # base = startBalance / 2500, first bet should be close to base
    first_bet = sess[0]["betSize"]
    est_bank = first_bet * 2500
    trail_range = est_bank * 0.05
    print(f"    Estimated bank: ${est_bank:.2f} | Trail range: ${trail_range:.2f}")
    print(f"    Trail floor at peak: ${peak - trail_range:+.2f}")

    # 3. Check if trail-aware cap was reducing bets
    print(f"\n  3. TRAIL-AWARE BET CAP IMPACT:")
    trail_capped_chains = 0
    for c in chains:
        if c["recovered"] and c["net"] < 0:
            # This chain won but didn't fully recover — trail cap likely culprit
            recovery_bet = c["recovery_bet"]["betSize"]
            chain_cost = c["chain_cost"]
            needed = chain_cost / 0.98
            if recovery_bet < needed * 0.9:  # More than 10% short
                trail_capped_chains += 1

    print(f"    Chains where recovery bet was significantly below needed: "
          f"{trail_capped_chains}/{len(recovered)} recovered chains")

    # 4. Summary: total P&L from full vs partial recoveries
    full_pnl = sum(c["net"] for c in full_recoveries)
    partial_pnl = sum(c["net"] for c in partial_recoveries)
    unrec_pnl = sum(c["net"] for c in unrecovered)
    flat_wins_pnl = 0
    # Count flat wins (single wins not part of recovery)
    in_chain = False
    for b in sess:
        if b["multiplier"] > 0 and not in_chain:
            flat_wins_pnl += b["payout"] - b["betSize"]
        elif b["multiplier"] > 0:
            in_chain = False
        else:
            in_chain = True

    print(f"\n  4. P&L BREAKDOWN:")
    print(f"    Flat wins (no chain): ${flat_wins_pnl:+.2f}")
    print(f"    Full recoveries ({len(full_recoveries)}): ${full_pnl:+.2f}")
    print(f"    Partial recoveries ({len(partial_recoveries)}): ${partial_pnl:+.2f}")
    print(f"    Unrecovered ({len(unrecovered)}): ${unrec_pnl:+.2f}")
    print(f"    TOTAL: ${flat_wins_pnl + full_pnl + partial_pnl + unrec_pnl:+.2f}")

    # 5. Worst chains
    print(f"\n  5. WORST CHAINS (by net P&L):")
    worst = sorted(chains, key=lambda c: c["net"])[:5]
    for i, c in enumerate(worst):
        loss_bets = [l["betSize"] for l in c["losses"]]
        print(f"    #{i+1}: LS={c['depth']} | Cost: ${c['chain_cost']:.2f} | "
              f"Net: ${c['net']:+.2f} | "
              f"{'Recovered' if c['recovered'] else 'UNRECOVERED'}")
        print(f"         Bets: {[f'${b:.2f}' for b in loss_bets[:8]]}{'...' if len(loss_bets) > 8 else ''}")
        if c["recovered"]:
            print(f"         Recovery: ${c['recovery_bet']['betSize']:.2f} → "
                  f"payout ${c['recovery_bet']['payout']:.2f}")

print("\n" + "=" * 100)
