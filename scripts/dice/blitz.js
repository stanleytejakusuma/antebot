// BLITZ v1.0 — Maximum Speed Dice Strategy
// Batch-react architecture: BLITZ (flat, zero-logging) → EVAL → RECOVER
// Designed for raw throughput. 95% of bets have a 3-line callback.
//
// BLITZ phase:  Flat bet, no logging, no decisions. Pure speed.
// EVAL phase:   Every N bets, check P&L, log status, decide next action.
// RECOVER phase: Mini-Martingale burst (IOL 3.0x, max 5 steps) to recover deficit.
//
// Expected speed: 50-200+ bets/sec (vs ~5/sec with full logging).
// Tradeoff: no per-bet reaction. Strategy operates on batch-level P&L.
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat) / BLITZ (Dice)

strategyTitle = "BLITZ";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
chance = 65;
divider = 5000;

// Batch size: bets between evaluations. Larger = faster but less reactive.
batchSize = 200;

// Recovery: mini-Martingale after negative batch
recoveryIOL = 3.0;
recoveryMaxSteps = 5; // Max IOL escalations before accepting loss and resetting

// Trail
trailActivatePct = 10;
trailLockPct = 60;

// Stops
stopTotalPct = 15;
stopOnLoss = 0;     // 0 = trail only (no hard stop loss)
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

target = chanceToMultiplier(chance);
startBalance = balance;
baseBet = startBalance / divider;
if (baseBet < 0.00101) baseBet = 0.00101;

betSize = baseBet;
betHigh = true;

// Thresholds
stopOnTotalProfit = stopTotalPct > 0 ? startBalance * stopTotalPct / 100 : 0;
stopLossThreshold = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;
trailActivateThreshold = startBalance * trailActivatePct / 100;

// State
phase = "blitz";  // "blitz", "recover", "stopped"
batchCount = 0;    // Bets in current batch
totalBets = 0;
totalWins = 0;
totalLosses = 0;
totalWagered = 0;
peakProfit = 0;
maxBetSeen = baseBet;
batchesCompleted = 0;
recoveriesAttempted = 0;
recoveriesWon = 0;

// Recovery state
recoveryMult = 1;
recoveryStep = 0;
recoveryDeficit = 0;

// Trail state
trailActive = false;
trailFloor = 0;
trailStopFired = false;

// Timing
startTime = Date.now();
stopped = false;

// ============================================================
// EVAL — runs every batchSize bets (or on recovery resolution)
// ============================================================

function evaluate() {
  batchesCompleted++;
  elapsed = (Date.now() - startTime) / 1000;
  bps = totalBets / elapsed;
  wps = totalWagered / elapsed;

  // Peak tracking
  if (profit > peakProfit) peakProfit = profit;

  // Trail activation
  if (!trailActive && profit >= trailActivateThreshold) {
    trailActive = true;
  }

  // Trail fire
  if (trailActive) {
    trailFloor = peakProfit * trailLockPct / 100;
    if (profit <= trailFloor) {
      trailStopFired = true;
      phase = "stopped";
      logSummary("TRAIL EXIT");
      engine.stop();
      return;
    }
  }

  // Stop profit
  if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit) {
    phase = "stopped";
    logSummary("TARGET HIT");
    engine.stop();
    return;
  }

  // Stop loss
  if (stopLossThreshold > 0 && profit < -stopLossThreshold) {
    phase = "stopped";
    logSummary("STOP LOSS");
    engine.stop();
    return;
  }

  // Log status (single update, no clearConsole for speed)
  clearConsole();
  log(
    "#00FFFF",
    "================================\n BLITZ v" + version +
    "\n================================"
  );
  log("#00FFFF", "Phase: " + phase.toUpperCase() + " | Batch #" + batchesCompleted + " (" + batchSize + " bets/batch)");
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + profit.toFixed(2) + " | Peak: $" + peakProfit.toFixed(2));

  trailBar = "";
  if (trailActive) {
    trailBar = "TRAIL floor $" + trailFloor.toFixed(2) + " (peak $" + peakProfit.toFixed(2) + ")";
  } else if (profit > 0) {
    trailBar = "Trail arms at $" + trailActivateThreshold.toFixed(2);
  }
  log("#FFD700", trailBar);
  log("#42CAF7", "Speed: " + bps.toFixed(1) + " bets/s | $" + wps.toFixed(2) + "/s wager");
  log("#FFDB55", "Bets: " + totalBets + " | W/L: " + totalWins + "/" + totalLosses + " (" + (totalBets > 0 ? (totalWins / totalBets * 100).toFixed(1) : "0") + "%)");
  log("#4FFB4F", "Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x) | Recoveries: " + recoveriesWon + "/" + recoveriesAttempted);
  log("#FD71FD", "Max Bet: $" + maxBetSeen.toFixed(4) + " | Elapsed: " + elapsed.toFixed(1) + "s");

  // Decide next phase
  if (profit < -baseBet * 5 && phase === "blitz") {
    // Significant deficit — enter recovery
    phase = "recover";
    recoveryDeficit = -profit;
    recoveryMult = 1;
    recoveryStep = 0;
    recoveriesAttempted++;
    betSize = baseBet * recoveryIOL;
    if (betSize > balance * 0.95) betSize = baseBet;
  } else {
    // Stay in blitz
    phase = "blitz";
    betSize = baseBet;
    batchCount = 0;
  }
}

// ============================================================
// SUMMARY
// ============================================================

function logSummary(exitType) {
  elapsed = (Date.now() - startTime) / 1000;
  bps = totalBets / elapsed;
  playHitSound();
  clearConsole();
  log(
    "#00FFFF",
    "================================\n BLITZ v" + version + " — " + exitType +
    "\n================================"
  );
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("Bets: " + totalBets + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("#00FFFF", "Speed: " + bps.toFixed(1) + " bets/s | Time: " + elapsed.toFixed(1) + "s");
  log("Batches: " + batchesCompleted + " | Recoveries: " + recoveriesWon + "/" + recoveriesAttempted);
  log("Max Bet: $" + maxBetSeen.toFixed(4));
  if (trailStopFired) {
    log("#FFD700", "Trail: exited at $" + profit.toFixed(2) + " (floor $" + trailFloor.toFixed(2) + ")");
  }
}

// ============================================================
// MAIN LOOP — minimal callback for maximum throughput
// ============================================================

engine.onBetPlaced(async function () {
  if (stopped) return;

  // === UNIVERSAL TRACKING (every bet, minimal cost) ===
  totalBets++;
  totalWagered += lastBet.amount;
  if (lastBet.win) { totalWins++; } else { totalLosses++; }
  if (betSize > maxBetSeen) maxBetSeen = betSize;

  // === PHASE ROUTING ===
  if (phase === "blitz") {
    // BLITZ: flat bet, no decisions, max speed
    batchCount++;
    if (batchCount >= batchSize) {
      evaluate();
    }
    // betSize stays at baseBet — no change needed

  } else if (phase === "recover") {
    // RECOVER: mini-Martingale to recover batch deficit
    if (lastBet.win) {
      // Recovery win — check if deficit cleared
      recoveriesWon++;
      phase = "blitz";
      betSize = baseBet;
      batchCount = 0;
      // Quick trail/stop check
      if (profit > peakProfit) peakProfit = profit;
      if (trailActive && profit <= peakProfit * trailLockPct / 100) {
        trailStopFired = true;
        phase = "stopped";
        stopped = true;
        logSummary("TRAIL EXIT");
        engine.stop();
        return;
      }
    } else {
      // Recovery loss — escalate
      recoveryStep++;
      if (recoveryStep >= recoveryMaxSteps) {
        // Max recovery reached — accept loss, back to blitz
        phase = "blitz";
        betSize = baseBet;
        batchCount = 0;
      } else {
        betSize = betSize * recoveryIOL;
        // Soft bust
        if (betSize > balance * 0.95) {
          betSize = baseBet;
          phase = "blitz";
          batchCount = 0;
        }
      }
    }

  } else if (phase === "stopped") {
    return;
  }

  // Hard bust check
  if (balance <= baseBet) {
    stopped = true;
    logSummary("BUST");
    engine.stop();
  }

  // Periodic trail check during blitz (every 50 bets, cheap)
  if (phase === "blitz" && totalBets % 50 === 0) {
    if (profit > peakProfit) peakProfit = profit;
    if (!trailActive && profit >= trailActivateThreshold) trailActive = true;
    if (trailActive && profit <= peakProfit * trailLockPct / 100) {
      trailStopFired = true;
      stopped = true;
      logSummary("TRAIL EXIT");
      engine.stop();
    }
    if (stopOnTotalProfit > 0 && profit >= stopOnTotalProfit) {
      stopped = true;
      logSummary("TARGET HIT");
      engine.stop();
    }
  }
});

engine.onBettingStopped(function () {
  if (!stopped) logSummary("MANUAL STOP");
});
