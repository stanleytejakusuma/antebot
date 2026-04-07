"""PROVING GROUND — Strategy base class and built-in strategies."""


class Strategy:
    game = "dice"
    name = "base"

    def initial_state(self):
        return {}

    def on_result(self, won, payout_mult, profit, bank, state):
        """Called after each hand. Returns (iol_mult, new_state).

        iol_mult: multiplier for next bet (1.0=base, 3.0=3x base).
        Session runner handles actual bet sizing, soft bust, trail cap.
        """
        return (1.0, state)

    def get_hand_config(self, state):
        """For multi-round games (HiLo). Returns dict like {skip_set, cashout_target}."""
        return {}


class FlatStrategy(Strategy):
    """Always returns iol_mult=1.0 — flat betting."""

    name = "flat"

    def __init__(self, game="dice"):
        self.game = game

    def initial_state(self):
        return {}

    def on_result(self, won, payout_mult, profit, bank, state):
        return (1.0, state)


class IOLStrategy(Strategy):
    """Multiply by `iol` on loss, reset to 1.0 on win."""

    name = "iol"

    def __init__(self, iol=3.0, game="dice"):
        self.iol = iol
        self.game = game

    def initial_state(self):
        return {"mult": 1.0}

    def on_result(self, won, payout_mult, profit, bank, state):
        state = dict(state)
        if won:
            state["mult"] = 1.0
        else:
            state["mult"] = state.get("mult", 1.0) * self.iol
        return (state["mult"], state)


class MambaStrategy(Strategy):
    """MAMBA: Dice 65%, IOL 3.0x on loss, reset on win."""

    name = "mamba"
    game = "dice"

    def __init__(self, iol=3.0):
        self.iol = iol

    def initial_state(self):
        return {"mult": 1.0}

    def on_result(self, won, payout_mult, profit, bank, state):
        state = dict(state)
        if won:
            state["mult"] = 1.0
        else:
            state["mult"] = state.get("mult", 1.0) * self.iol
        return (state["mult"], state)


class SidewinderStrategy(Strategy):
    """SIDEWINDER HiLo strategy with mode-switching.

    Modes:
      cruise     — normal play
      recovery   — when profit < -recovery_pct% of bank or IOL elevated
      capitalize — when trail is active (overridden by session runner)

    Session runner overrides mode to capitalize when trail is active.
    """

    name = "sidewinder"
    game = "hilo"

    def __init__(
        self,
        iol=3.0,
        cashout_cruise=1.5,
        cashout_recovery=2.5,
        cashout_capitalize=1.1,
        recovery_pct=5,
        skip_set=None,
    ):
        self.iol = iol
        self.cashout_cruise = cashout_cruise
        self.cashout_recovery = cashout_recovery
        self.cashout_capitalize = cashout_capitalize
        self.recovery_pct = recovery_pct
        self.skip_set = frozenset(skip_set) if skip_set is not None else frozenset({6, 7, 8})

    def initial_state(self):
        return {"mult": 1.0, "mode": "cruise"}

    def on_result(self, won, payout_mult, profit, bank, state):
        state = dict(state)
        if won:
            state["mult"] = 1.0
        else:
            state["mult"] = state.get("mult", 1.0) * self.iol

        # Mode determination (trail override handled by session runner)
        recovery_threshold = bank * self.recovery_pct / 100.0
        current_mult = state["mult"]
        if profit < -recovery_threshold or current_mult > 1.5:
            state["mode"] = "recovery"
        else:
            state["mode"] = "cruise"

        return (state["mult"], state)

    def get_hand_config(self, state):
        mode = state.get("mode", "cruise")
        if mode == "capitalize":
            cashout = self.cashout_capitalize
        elif mode == "recovery":
            cashout = self.cashout_recovery
        else:
            cashout = self.cashout_cruise
        return {
            "skip_set": self.skip_set,
            "cashout_target": cashout,
        }


STRATEGIES = {
    "flat": FlatStrategy,
    "iol": IOLStrategy,
    "mamba": MambaStrategy,
    "sidewinder": SidewinderStrategy,
}
