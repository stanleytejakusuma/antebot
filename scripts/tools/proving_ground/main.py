#!/usr/bin/env python3
"""PROVING GROUND CLI — Antebot Strategy Testing Harness.

Usage:
    cd scripts/tools
    python3 -m proving_ground.main --strategy mamba --bank 100 --sessions 5000
    python3 -m proving_ground.main --strategy mamba --bank 100 --pillar pf
    python3 -m proving_ground.main --strategy flat --bank 100 --pillar markov
    python3 -m proving_ground.main --strategy mamba --strategy2 sidewinder --compare
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proving_ground.strategy import STRATEGIES, MambaStrategy, SidewinderStrategy, FlatStrategy, IOLStrategy
from proving_ground.engines import DiceEngine, RouletteEngine, HiLoEngine
from proving_ground.report import prove, print_report, save_report


def build_strategy(name):
    if name == "mamba":
        return MambaStrategy(iol=3.0)
    elif name == "sidewinder":
        return SidewinderStrategy(iol=3.0)
    elif name == "flat":
        return FlatStrategy("dice")
    elif name == "iol":
        return IOLStrategy(iol=3.0, game="dice")
    elif name in STRATEGIES:
        return STRATEGIES[name]()
    else:
        print("Unknown strategy: " + name)
        print("Available: " + ", ".join(STRATEGIES.keys()))
        sys.exit(1)


def build_engine(strategy):
    if strategy.game == "dice":
        return DiceEngine(chance=65)
    elif strategy.game == "roulette":
        return RouletteEngine(covered_count=23)
    elif strategy.game == "hilo":
        return HiLoEngine(skip_set=frozenset({6, 7, 8}), cashout_target=1.5)
    else:
        print("Unknown game: " + strategy.game)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="PROVING GROUND — Strategy Testing Harness")
    parser.add_argument("--strategy", "-s", default="mamba", help="Strategy name")
    parser.add_argument("--bank", "-b", type=float, default=100, help="Starting balance")
    parser.add_argument("--divider", "-d", type=int, default=10000, help="Bet divider")
    parser.add_argument("--sessions", "-n", type=int, default=5000, help="MC session count")
    parser.add_argument("--pillar", "-p", default="all", help="mc, markov, pf, or all")
    parser.add_argument("--seeds", default=None, help="Path to seeds.json")
    parser.add_argument("--stop", type=float, default=15, help="Stop profit %")
    parser.add_argument("--sl", type=float, default=15, help="Stop loss %")
    parser.add_argument("--trail-act", type=float, default=8, help="Trail activate %")
    parser.add_argument("--trail-lock", type=float, default=60, help="Trail lock %")
    parser.add_argument("--output", "-o", default=None, help="Save report JSON")
    args = parser.parse_args()

    strategy = build_strategy(args.strategy)
    engine = build_engine(strategy)
    params = {
        "bank": args.bank,
        "divider": args.divider,
        "stop_pct": args.stop,
        "sl_pct": args.sl,
        "trail_act": args.trail_act,
        "trail_lock": args.trail_lock,
    }

    seeds_path = args.seeds
    if seeds_path is None and ("pf" in args.pillar or args.pillar == "all"):
        default_seeds = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seeds.json")
        if os.path.exists(default_seeds):
            seeds_path = default_seeds

    report = prove(strategy, engine, params,
                   num_sessions=args.sessions,
                   seeds_path=seeds_path,
                   pillars=args.pillar)
    print_report(report)

    if args.output:
        save_report(report, args.output)
        print("\n  Report saved to " + args.output)


if __name__ == "__main__":
    main()
