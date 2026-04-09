"""PROVING GROUND — Game engines that resolve RNG into outcomes."""

import random as _random


class DiceEngine:
    """Dice game engine: fixed chance%, IOL-friendly payout."""

    name = "dice"

    def __init__(self, chance=65):
        self.chance = chance
        self.win_prob = chance / 100.0
        # Net profit multiplier on win (e.g. 65% chance -> ~0.5231x net profit)
        self.net_payout = 0.99 * 100.0 / chance - 1.0

    def resolve(self, rng):
        """Returns (won: bool, net_payout_mult: float).

        net_payout_mult on win  = self.net_payout (positive)
        net_payout_mult on loss = -1.0
        """
        won = rng.random() < self.win_prob
        if won:
            return (True, self.net_payout)
        return (False, -1.0)

    def resolve_from_float(self, f):
        """From provably fair float. Dice: floor(f*10001)/100, win if < chance."""
        result = int(f * 10001) / 100.0
        won = result < self.chance
        if won:
            return (True, self.net_payout)
        return (False, -1.0)


class RouletteEngine:
    """Roulette engine: fixed covered count (23 by default = COBRA config)."""

    name = "roulette"

    def __init__(self, covered_count=23):
        self.covered_count = covered_count
        self.win_prob = covered_count / 37.0
        # Net profit multiplier on win
        self.net_payout = 36.0 / covered_count - 1.0

    def resolve(self, rng):
        """Returns (won: bool, net_payout_mult: float)."""
        won = rng.random() < self.win_prob
        if won:
            return (True, self.net_payout)
        return (False, -1.0)

    def resolve_from_float(self, f):
        """From provably fair float. Roulette: floor(f*37) gives 0-36."""
        result = int(f * 37)
        # Assume covered numbers are 0..(covered_count-1) for simplicity
        won = result < self.covered_count
        if won:
            return (True, self.net_payout)
        return (False, -1.0)


class HiLoEngine:
    """HiLo card game engine.

    Cards drawn from 1-13, skip middle cards, bet HIGH if <=7 else LOW.
    Chain predictions until cashout_target multiplier or wrong prediction.
    """

    name = "hilo"

    def __init__(self, skip_set=None, cashout_target=1.5, start_val=1):
        self.skip_set = frozenset(skip_set) if skip_set is not None else frozenset({6, 7, 8})
        self.cashout_target = cashout_target
        self.start_val = start_val

    def configure(self, hand_config):
        """Update skip_set and cashout_target from strategy hand config."""
        if "skip_set" in hand_config:
            self.skip_set = frozenset(hand_config["skip_set"])
        if "cashout_target" in hand_config:
            self.cashout_target = hand_config["cashout_target"]

    def _card_payout(self, val, bet_high):
        """Returns (win_prob, gross_mult) for a single prediction.

        gross_mult is the total return on stake (e.g. 1.0825 means +8.25% net).
        Returns (0.0, 0.0) if the bet is impossible (e.g. betting high on King).
        """
        if bet_high:
            winning = 13 - val
        else:
            winning = val - 1

        if winning <= 0:
            return (0.0, 0.0)

        prob = winning / 13.0
        gross_mult = 0.99 * 13.0 / winning
        return (prob, gross_mult)

    def resolve(self, rng):
        """Simulate one HiLo hand.

        Cards 1-13, skip middle cards in skip_set, bet HIGH if <=7 else LOW.
        Chain predictions until cashout_target reached or wrong prediction.

        Returns (won: bool, net_mult: float)
          won=True:  net_mult = accumulated_gross - 1.0  (positive profit factor)
          won=False: net_mult = -1.0
        """
        current_card = rng.randint(1, 13)
        accumulated = 1.0
        max_draws = 52

        for _ in range(max_draws):
            # Skip unfavorable middle cards
            if current_card in self.skip_set:
                current_card = rng.randint(1, 13)
                continue

            # Decide direction
            bet_high = current_card <= 7
            prob, gross_mult = self._card_payout(current_card, bet_high)

            if prob <= 0:
                # Impossible bet — skip (shouldn't happen with valid skip_set)
                current_card = rng.randint(1, 13)
                continue

            # Draw next card
            next_card = rng.randint(1, 13)

            # Check prediction
            if bet_high:
                correct = next_card > current_card
            else:
                correct = next_card < current_card

            if not correct:
                # Lost the hand
                return (False, -1.0)

            # Accumulate multiplier
            accumulated *= gross_mult
            current_card = next_card

            # Check cashout condition
            if accumulated >= self.cashout_target:
                return (True, accumulated - 1.0)

        # Reached max draws — cash out at current accumulated
        return (True, accumulated - 1.0)


class MinesEngine:
    """Mines engine: 5x5 grid, configurable mines and field picks.

    Binary outcome: all picked fields safe (win) or hit a mine (lose).
    Payout uses 1% house edge like all Shuffle games.

    Win probability = C(25-mines, fields) / C(25, fields)
                    = product((safe-i)/(25-i)) for i in range(fields)

    Gross payout = 0.99 / win_prob
    """

    name = "mines"

    def __init__(self, mines=5, fields=1):
        self.mines = mines
        self.fields = fields
        # Win probability: combinatorial
        safe = 25 - mines
        prob = 1.0
        for i in range(fields):
            prob *= (safe - i) / (25.0 - i)
        self.win_prob = prob
        # Net profit multiplier on win (1% house edge)
        self.net_payout = 0.99 / prob - 1.0

    def resolve(self, rng):
        """Returns (won: bool, net_payout_mult: float)."""
        won = rng.random() < self.win_prob
        if won:
            return (True, self.net_payout)
        return (False, -1.0)

    def resolve_from_float(self, f):
        """From provably fair float."""
        won = f < self.win_prob
        if won:
            return (True, self.net_payout)
        return (False, -1.0)


ENGINES = {
    "dice": DiceEngine,
    "roulette": RouletteEngine,
    "hilo": HiLoEngine,
    "mines": MinesEngine,
}
