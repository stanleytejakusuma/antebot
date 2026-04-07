"""Unified report — combines all three validation pillars."""

import json
import time


def prove(strategy, engine, params, num_sessions=5000, seeds_path=None, pillars="all"):
    """
    Run all validation pillars and produce unified report.

    Args:
        strategy: Strategy instance
        engine: GameEngine instance
        params: session params dict
        num_sessions: MC session count
        seeds_path: path to seeds.json for PF replay
        pillars: "all", "mc", "markov", "pf" — or comma-separated
    """
    active = set(pillars.split(",")) if pillars != "all" else {"mc", "markov", "pf"}
    report = {"strategy": strategy.name, "game": strategy.game, "params": params}

    if "mc" in active:
        from proving_ground.monte_carlo import run_mc
        t0 = time.time()
        report["mc"] = run_mc(strategy, engine, params, num=num_sessions)
        report["mc"]["runtime_s"] = round(time.time() - t0, 1)

    if "markov" in active:
        from proving_ground.markov import run_markov
        t0 = time.time()
        report["markov"] = run_markov(strategy, engine, params)
        report["markov"]["runtime_s"] = round(time.time() - t0, 1)

    if "pf" in active:
        from proving_ground.provably_fair import run_pf
        t0 = time.time()
        report["pf"] = run_pf(strategy, engine, params, seeds_path=seeds_path,
                               game=strategy.game)
        report["pf"]["runtime_s"] = round(time.time() - t0, 1)

    report["agreement"] = _compute_agreement(report)
    return report


def _compute_agreement(report):
    """Compare pillar results for consistency."""
    ag = {}
    mc = report.get("mc", {})
    markov = report.get("markov", {})
    pf = report.get("pf", {})

    mc_med = mc.get("median")
    pf_med = pf.get("median")
    markov_target = markov.get("target_prob")

    if mc_med is not None and pf_med is not None:
        delta = abs(mc_med - pf_med)
        ag["mc_vs_pf_delta"] = round(delta, 2)
        if mc_med != 0:
            ag["mc_vs_pf_pct"] = round(delta / abs(mc_med) * 100, 1)
        ag["mc_vs_pf_warning"] = delta > abs(mc_med) * 0.20 if mc_med else False

    if mc.get("win_pct") is not None and markov_target is not None:
        ag["mc_win_pct"] = round(mc["win_pct"], 1)
        ag["markov_target_pct"] = round(markov_target, 1)
        delta = abs(mc["win_pct"] - markov_target)
        ag["mc_vs_markov_delta"] = round(delta, 1)
        ag["mc_vs_markov_warning"] = delta > 20

    return ag


def print_report(report):
    """Pretty-print the unified report."""
    print()
    print("=" * 90)
    print("  PROVING GROUND — " + report["strategy"].upper() + " (" + report["game"] + ")")
    print("=" * 90)

    params = report["params"]
    print("  Bank: $" + str(params.get("bank", 100)) +
          " | Div: " + str(params.get("divider", 10000)) +
          " | Trail: " + str(params.get("trail_act", 8)) + "/" + str(params.get("trail_lock", 60)) +
          " | SL: " + str(params.get("sl_pct", 15)) + "%" +
          " | SP: " + str(params.get("stop_pct", 15)) + "%")

    mc = report.get("mc")
    if mc:
        print("\n  --- Pillar 1: Monte Carlo (" + str(mc.get("count", "?")) + " sessions, " + str(mc.get("runtime_s", "?")) + "s) ---")
        print("  Median: $" + format(mc["median"], "+.2f") +
              " | Mean: $" + format(mc["mean"], "+.2f"))
        print("  Bust: " + format(mc["bust_pct"], ".1f") + "%" +
              " | Win: " + format(mc["win_pct"], ".1f") + "%")
        print("  P5: $" + format(mc["p5"], "+.2f") +
              " | P10: $" + format(mc["p10"], "+.2f") +
              " | P90: $" + format(mc["p90"], "+.2f") +
              " | P95: $" + format(mc["p95"], "+.2f"))

    markov = report.get("markov")
    if markov:
        print("\n  --- Pillar 2: Markov Chain (" + str(markov.get("runtime_s", "?")) + "s) ---")
        if markov.get("supported"):
            print("  Ruin prob: " + format(markov["ruin_prob"], ".1f") + "%" +
                  " | Target prob: " + format(markov["target_prob"], ".1f") + "%")
            print("  States: " + str(markov["states"]) +
                  " | Max IOL level: " + str(markov["max_iol_level"]) +
                  " | Converged: " + str(markov["iterations"]) + " iters")
        else:
            print("  " + markov.get("error", "Not supported"))

    pf = report.get("pf")
    if pf:
        print("\n  --- Pillar 3: Provably Fair Replay (" + str(pf.get("runtime_s", "?")) + "s) ---")
        if pf.get("count", 0) > 0:
            print("  Median: $" + format(pf["median"], "+.2f") +
                  " | Mean: $" + format(pf["mean"], "+.2f"))
            print("  Bust: " + format(pf["bust_pct"], ".1f") + "%" +
                  " | Win: " + format(pf["win_pct"], ".1f") + "%")
            print("  Seed pairs: " + str(pf.get("seed_pairs", "?")) +
                  " | Total nonces: " + str(pf.get("total_nonces", "?")))
        else:
            print("  No results (check seeds file)")

    ag = report.get("agreement", {})
    if ag:
        print("\n  --- Agreement ---")
        if "mc_vs_pf_delta" in ag:
            warn = " WARNING" if ag.get("mc_vs_pf_warning") else " OK"
            print("  MC vs PF: delta=$" + format(ag["mc_vs_pf_delta"], ".2f") +
                  " (" + str(ag.get("mc_vs_pf_pct", "?")) + "%)" + warn)
        if "mc_vs_markov_delta" in ag:
            warn = " WARNING" if ag.get("mc_vs_markov_warning") else " OK"
            print("  MC win% vs Markov target%: " + str(ag["mc_win_pct"]) + "% vs " +
                  str(ag["markov_target_pct"]) + "% (delta=" + str(ag["mc_vs_markov_delta"]) + "%)" + warn)

    print("=" * 90)


def save_report(report, path):
    """Save report to JSON."""
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
