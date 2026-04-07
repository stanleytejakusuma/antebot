// BLITZ v2.0 — Maximum Speed Dice + Inline IOL
// asyncMode + minimal callback. IOL runs per-bet (just one if/else).
// No clearConsole/log in the hot path. Single log() every N bets.
//
// How it works: same IOL 3.0x as MAMBA but stripped to bare metal.
// The callback is 5 lines: track, IOL if/else, periodic check.
// asyncMode lets engine fire before callback finishes.
//
// Expected: 10-50+ bets/sec depending on engine limits.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat) / BLITZ (Dice)

strategyTitle = "BLITZ";
version = "2.0.0";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
chance = 65;
divider = 2000;     // Aggressive — $0.05 base on $100. Visible bets.
iolMultiplier = 3.0; // IOL on every loss (same as MAMBA v2, raw speed)

// Log interval: show status every N bets (single log line, no clearConsole)
logInterval = 500;

// Trail
trailActivatePct = 10;
trailLockPct = 60;

// Stops
stopTotalPct = 15;
stopOnLoss = 15;
stopAfterHands = 0;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
}

resetStats();
clearConsole();

asyncMode = true;
target = chanceToMultiplier(chance);
startBalance = balance;
baseBet = startBalance / divider;
if (baseBet < 0.00101) baseBet = 0.00101;

betSize = baseBet;
betHigh = true;

// Thresholds
stopT = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
slT = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
actT = startBalance * trailActivatePct / 100;

// State — absolute minimum
mult = 1;
n = 0;
w = 0;
pk = 0;
wag = 0;
ta = false;
t0 = Date.now();
stopped = false;

// ============================================================
// MAIN LOOP — bare metal IOL + periodic single-line log
// ============================================================

log("#00FFFF", "BLITZ v" + version + " | $" + baseBet.toFixed(4) + " base | IOL " + iolMultiplier + "x | trail " + trailActivatePct + "/" + trailLockPct);

engine.onBetPlaced(async function () {
  if (stopped) return;

  // === CORE: 5 lines — track + IOL ===
  n++;
  wag += lastBet.amount;
  if (lastBet.win) {
    w++; mult = 1; betSize = baseBet;
  } else {
    mult *= iolMultiplier;
    betSize = baseBet * mult;
    // Soft bust
    if (betSize > balance * 0.95) { mult = 1; betSize = baseBet; }
  }

  // Trail-aware bet cap (cheap — only runs when trail active)
  if (ta) {
    fl = pk * trailLockPct / 100;
    mx = profit - fl;
    if (mx > 0 && betSize > mx) betSize = mx;
    if (betSize < baseBet) betSize = baseBet;
  }

  // === PERIODIC CHECK: every logInterval bets ===
  if (n % logInterval === 0) {
    if (profit > pk) pk = profit;
    if (!ta && profit >= actT) ta = true;

    // Trail fire
    if (ta && profit <= pk * trailLockPct / 100) {
      stopped = true;
      playHitSound();
      log("#FFD700", "TRAIL | $" + profit.toFixed(2) + " < floor $" + (pk * trailLockPct / 100).toFixed(2) + " | peak $" + pk.toFixed(2));
      engine.stop(); return;
    }
    // Stop profit
    if (stopT > 0 && profit >= stopT && mult <= 1.01) {
      stopped = true;
      playHitSound();
      log("#4FFB4F", "TARGET | $" + profit.toFixed(2));
      engine.stop(); return;
    }
    // Stop loss
    if (slT > 0 && profit < -slT) {
      stopped = true;
      log("#FD6868", "STOP LOSS | $" + profit.toFixed(2));
      engine.stop(); return;
    }

    // Single-line status (no clearConsole — append only)
    el = (Date.now() - t0) / 1000;
    log("#00FFFF", n + "b " + (n/el).toFixed(0) + "/s | $" + profit.toFixed(2) + " P&L | $" + wag.toFixed(2) + " wag (" + (wag/startBalance).toFixed(1) + "x) | pk $" + pk.toFixed(2) + " | " + (ta ? "TRAIL" : "arm@$" + actT.toFixed(2)));
  }

  // Fast trail check between log intervals (every 100 bets)
  if (n % 100 === 50) {
    if (profit > pk) pk = profit;
    if (!ta && profit >= actT) ta = true;
    if (ta && profit <= pk * trailLockPct / 100) {
      stopped = true;
      playHitSound();
      log("#FFD700", "TRAIL | $" + profit.toFixed(2) + " (peak $" + pk.toFixed(2) + ")");
      engine.stop();
    }
  }
});

engine.onBettingStopped(function () {
  if (stopped) return;
  el = (Date.now() - t0) / 1000;
  playHitSound();
  log("#00FFFF", "BLITZ v" + version + " DONE | " + n + " bets " + (n/el).toFixed(0) + "/s | $" + profit.toFixed(2) + " P&L | $" + wag.toFixed(2) + " wag | " + el.toFixed(1) + "s");
});
