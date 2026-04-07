# PROVING GROUND — Antebot Strategy Testing Harness

> **For agentic workers:** Use superpowers:writing-plans to generate an implementation plan from this PRD, then superpowers:subagent-driven-development or superpowers:executing-plans to implement.

Generated on: 2026-04-07 15:15 UTC+8
Last updated: —

## Context
We have 22 one-off Python optimizer scripts (`scripts/tools/*.py`), each reimplementing the same session simulation loop (IOL, trailing stop, stop loss/profit). Every new strategy requires copy-pasting ~100 lines of boilerplate. More critically, we only validate strategies via Monte Carlo — we have no analytical verification (Markov) or real-world replay (Provably Fair). PROVING GROUND unifies strategy testing into a single reusable system with three validation pillars: Monte Carlo, Markov Chain exact analysis, and Provably Fair Replay against actual Shuffle seeds.

## Success Criteria
- [ ] Define a strategy as a Python dict/object and test it across all 3 pillars with a single function call
- [ ] Reproduce MAMBA's Monte Carlo results (within 5% of existing optimizer) using the generic system
- [ ] Markov chain analysis produces exact ruin probability for a simple IOL strategy (dice flat + IOL 3.0x)
- [ ] PF Replay produces a sequence of outcomes from a real Shuffle seed pair that matches Shuffle's verification page
- [ ] Unified report shows MC median, Markov exact median, PF Replay median — with delta/agreement metrics
- [ ] `multiprocessing.Pool` achieves >5x speedup over sequential MC on 10-core machine
- [ ] System supports all 4 game types: dice, roulette, HiLo, blackjack

## Scope

**In Scope:**
- Strategy definition schema (game, states, transitions, bet sizing, stop conditions)
- Pillar 1: Monte Carlo simulator with `multiprocessing.Pool` — generic session loop
- Pillar 2: Markov Chain exact analysis — state transition matrix, steady-state distribution, ruin probability
- Pillar 3: Provably Fair Replay — HMAC-SHA256 outcome generation from real Shuffle seed pairs
- Game engines: dice, roulette, HiLo outcome generators (per-spin/per-hand result from RNG)
- Unified comparison report with agreement metrics
- CLI interface: `python3 proving-ground.py --strategy mamba --bank 100 --sessions 5000`

**Out of Scope (Explicit):**
- Blackjack engine — requires perfect strategy lookup table (complex, defer to v2)
- Live seed recording — only replay from revealed seed pairs
- GUI or web dashboard
- Automatic strategy optimization/parameter sweep (users compose their own sweeps using the API)
- Replacing existing per-strategy optimizer scripts (they continue to work, PROVING GROUND is additive)

## Requirements

### Must Have (P0)

**Strategy Definition Schema:**
- Strategy is a Python class with these methods:
  - `on_round(outcome, profit, state) -> (bet_size_multiplier, new_state)` — core decision logic
  - `get_hand_config(state) -> dict` — for multi-round games (HiLo: skip set, cashout target)
  - `initial_state() -> dict` — starting state (mode, counters, etc.)
- Session wrapper handles: IOL escalation, soft bust, trailing stop, stop loss, stop profit — configured via params, NOT reimplemented per strategy
- Built-in strategies: `FlatBet`, `IOL(multiplier)`, `Paroli(mult, max_chain)`, `Cascade(targets)` as composable bet sizing classes
- Game type declared in strategy: `"dice"`, `"roulette"`, `"hilo"`

**Pillar 1 — Monte Carlo:**
- Generic session loop: takes strategy + game engine + params (bank, divider, stops, trail)
- `multiprocessing.Pool` for parallel session execution
- Output: median, mean, bust%, win%, P5, P10, P25, P75, P90, P95, avg_hands
- Multi-seed validation: run across N seeds, report cross-seed consistency (std dev of medians)
- File: `scripts/tools/proving_ground/monte_carlo.py`

**Pillar 2 — Markov Chain:**
- Accept strategy state space + transition probabilities
- Build transition matrix
- Compute: absorbing state probabilities (ruin, target), expected hands to absorption, steady-state profit distribution
- Works for strategies with finite, enumerable states (IOL with max multiplier cap, cascade with level cap)
- For strategies with infinite states (unbounded IOL): approximate by truncating at soft bust threshold
- File: `scripts/tools/proving_ground/markov.py`

**Pillar 3 — Provably Fair Replay:**
- `HMAC-SHA256(serverSeed, "clientSeed:nonce:0")` → first 4 bytes as uint32 → / 2^32 → float
- Game-specific outcome from float:
  - Dice: `floor(float * 10001) / 100` → compare to target
  - Roulette: `floor(float * 37)` → number 0-36
  - HiLo: `floor(float * 13) + 1` → card value 1-13 (needs verification)
- Accept list of seed pairs: `[(client_seed, server_seed, nonce_count), ...]`
- Generate outcome sequence for each pair (nonce 0 to N-1)
- Replay strategy against the real outcome sequence
- Output: same stats as MC, plus per-seed breakdown
- File: `scripts/tools/proving_ground/provably_fair.py`

**Game Engines:**
- `DiceEngine(chance)` — binary outcome from float, win probability = chance/100
- `RouletteEngine(coverage)` — map number to payout tier based on coverage definition
- `HiLoEngine(skip_set, cashout_target)` — simulate hand with per-card decisions from float sequence
- Each engine: `resolve(float) -> (won: bool, payout_multiplier: float)`
- File: `scripts/tools/proving_ground/engines.py`

**Unified Report:**
- `prove(strategy, bank, sessions, seeds)` — runs all 3 pillars, returns combined report
- Agreement check: MC median vs Markov exact → delta and % difference
- Agreement check: MC median vs PF Replay median → delta
- Flag disagreements > 20% as warnings
- Pretty-print table + save to JSON
- File: `scripts/tools/proving_ground/report.py`

**CLI Entry Point:**
- `python3 scripts/tools/proving_ground/main.py --strategy mamba --bank 100 --sessions 5000`
- `--strategy`: name of built-in strategy or path to custom strategy file
- `--bank`: starting balance
- `--sessions`: MC session count
- `--seeds`: path to seeds file (JSON) for PF Replay
- `--pillar`: run specific pillar only (`mc`, `markov`, `pf`, `all`)
- Built-in strategies: `mamba`, `cobra`, `sidewinder`, `taipan`, `flat`
- File: `scripts/tools/proving_ground/main.py`

### Should Have (P1)
- Sensitivity analysis: sweep one parameter +/-20% and report stability
- Export results to CSV for plotting
- `--compare` flag: run two strategies and produce head-to-head table
- HiLo card formula verification against Shuffle's verification page
- Seed pair import from Shuffle's settings page (parse the table format)

### Won't Have (this iteration)
- Blackjack engine (needs perfect strategy table)
- Live seed recording
- Web UI
- Auto-optimization / parameter search
- Integration with Antebot Code Mode

## Technical Spec

### Files to Create
| File | Purpose |
|------|---------|
| `scripts/tools/proving_ground/__init__.py` | Package init |
| `scripts/tools/proving_ground/strategy.py` | Strategy base class + built-in strategies (Flat, IOL, Paroli, Cascade) |
| `scripts/tools/proving_ground/session.py` | Generic session loop (IOL, trail, stops) — the unified boilerplate |
| `scripts/tools/proving_ground/engines.py` | Game engines: Dice, Roulette, HiLo |
| `scripts/tools/proving_ground/monte_carlo.py` | Pillar 1: parallel MC simulation |
| `scripts/tools/proving_ground/markov.py` | Pillar 2: Markov chain exact analysis |
| `scripts/tools/proving_ground/provably_fair.py` | Pillar 3: HMAC-SHA256 replay |
| `scripts/tools/proving_ground/report.py` | Unified report generation |
| `scripts/tools/proving_ground/main.py` | CLI entry point |
| `scripts/tools/proving_ground/seeds.json` | Seed pairs from Shuffle (10 pairs, 2038 total nonces) |

### Shuffle Provably Fair Algorithm
```
HMAC-SHA256(serverSeed_string, "clientSeed:nonce:0") → first 4 bytes → uint32 → / 2^32 → float [0,1)
Dice:     floor(float * 10001) / 100 → roll result (0.00 to 100.00)
Roulette: floor(float * 37) → number (0-36)
HiLo:     floor(float * 13) + 1 → card value (1-13) [needs verification]
```

### Known Seed Pairs (from user's Shuffle account, 2026-04-07)
```json
[
  {"client": "k7a8xxuk2p", "server": "2c01d9109499adf0034370e463ec255906af4abd948820791df10a0e608701c2", "nonces": 831},
  {"client": "dw41eg7x6h", "server": "c19f71d402f19856f4e2dfc97dfff29598d6828c9e75422392a6beb4ac2faeac", "nonces": 321},
  {"client": "rtrks2afd4", "server": "039c18b1227f0a040ebe20b2997d89bb83806ebdb400185cdc78965748bdc547", "nonces": 185},
  {"client": "ph6opc0hgd", "server": "351390846931542ldaa9b3425b90f6fb3645bcd2fe0d16939d3773a88f577b45", "nonces": 183},
  {"client": "qqeu4matrb", "server": "a50aa1c490435f621421ff5e498abf9af7c11477db3cf9c4bcb0b9c25c12f97a", "nonces": 123},
  {"client": "lsada2x4bx", "server": "6eeccf5fc3834c3fac863d1626e4725600b367d75fe563f4a6dd9ad50b6f0496", "nonces": 119},
  {"client": "v90tyvabta", "server": "fc68fd5caaa051be2f86a8e013d56d392b322ff05da236852a722edc89148a73", "nonces": 116},
  {"client": "t9euu783jd", "server": "12c0201bba7b534e9bc565e8d326ac9a5facc422b9e69d4383e47c43db07eee1", "nonces": 89},
  {"client": "21bnler750", "server": "afef78d61572ce63b210abbcf0b0e95361d03ab8c7c005a53de5fbb537bb6db7", "nonces": 46},
  {"client": "9lr01b195i", "server": "f41e2ff1947a85703bcfd129dd02e5db097ad4f1fd575d163900a0b0c91b109a", "nonces": 25}
]
```

### Suggested Sequence
1. Strategy schema + session loop — define base class, implement generic session with IOL/trail/stops (~15 min)
2. Game engines — Dice, Roulette, HiLo outcome resolvers (~10 min)
3. Monte Carlo pillar — parallel MC using session + engines (~10 min)
4. Verify MC — reproduce MAMBA results within 5% of existing optimizer (~5 min)
5. Provably Fair pillar — HMAC-SHA256 implementation + outcome generation (~15 min)
6. Verify PF — test against known Shuffle outcomes (~5 min)
7. Markov pillar — transition matrix builder + absorbing chain solver (~15 min)
8. Unified report — combine all 3 pillars, agreement metrics (~10 min)
9. CLI entry point — argparse, built-in strategies, seeds loading (~10 min)
10. Built-in strategies — MAMBA, COBRA, SIDEWINDER definitions using the schema (~10 min)

### Dependencies & Order
- Steps 1-2 before steps 3-7 (session + engines are shared)
- Steps 3, 5, 7 can run in parallel (three independent pillars)
- Step 8 after all three pillars complete
- Steps 9-10 after step 8

## Evaluation Criteria
- [ ] `python3 proving_ground/main.py --strategy mamba --bank 100 --sessions 5000` produces MC results within 5% of `mamba-trail-v2.py` → Expected: PASS
- [ ] Markov exact ruin probability for flat dice at 65% matches analytical formula → Expected: PASS
- [ ] PF Replay of first seed pair produces 831 valid game outcomes → Expected: PASS
- [ ] `--pillar all` runs all 3 and produces unified report → Expected: PASS
- [ ] MC runs >5x faster than sequential on 10 cores → Expected: PASS

## Verification
- [ ] `python3 scripts/tools/proving_ground/main.py --strategy mamba --bank 100 --sessions 5000`
- [ ] `python3 scripts/tools/proving_ground/main.py --strategy mamba --bank 100 --pillar pf --seeds scripts/tools/proving_ground/seeds.json`
- [ ] `python3 scripts/tools/proving_ground/main.py --strategy flat --bank 100 --pillar markov`
- [ ] Manual: compare MC output with existing `mamba-trail-v2.py` output

## Notes
- The HiLo card formula (`floor(float * 13) + 1`) needs verification against Shuffle — may differ from dice/roulette formula
- Markov analysis only works for strategies with finite state spaces. IOL strategies need a max multiplier cap to bound the state space (soft bust provides this naturally)
- The 2,038 total nonces across 10 seed pairs is a limited dataset. MC remains primary; PF Replay is for validation, not primary testing
- Existing optimizer scripts in `scripts/tools/*.py` remain untouched — PROVING GROUND is additive tooling
