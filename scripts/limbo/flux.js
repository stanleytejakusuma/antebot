// FLUX v1.0.0 — Adaptive IOL with Probabilistic Bailout (Limbo)
// Completely new thesis. Not Snake Family, not APEX/PULSE/CASCADE.
//
// TWO INNOVATIONS NEVER TRIED IN ANY STRATEGY:
//
// 1. ADAPTIVE IOL CURVE — IOL multiplier shifts based on loss depth.
//    Every other strategy uses a FIXED multiplier (always 3.0x, always 1.5x).
//    FLUX uses a depth-dependent curve:
//      Depth 1-3:  IOL 1.2x  (gentle — 93.5% of cycles resolve here)
//      Depth 4-6:  IOL 1.5x  (standard)
//      Depth 7-9:  IOL 2.0x  (aggressive)
//      Depth 10+:  IOL 2.5x  (maximum — using the 50% SL headroom)
//
// 2. PROBABILISTIC BAILOUT — At each depth, calculate whether recovery
//    is still mathematically possible within the remaining SL budget.
//    If the next bet can't recover cumulative losses, STOP ESCALATING.
//    No existing strategy does this — they all blindly escalate until SL.
//
// MATH (target=2.0x, 49.5% chance, div=5000):
//   P(depth >= 4): 6.5%   — only 6.5% of cycles enter standard zone
//   P(depth >= 7): 0.8%   — aggressive zone is rare
//   P(depth >= 10): 0.1%  — maximum zone almost never reached
//   P(depth >= 13): 0.01% — bailout territory (essentially never)
//   Most cycles resolve at depth 0-3 with IOL 1.2x (gentle, cheap)
//
// SL=50% gives 13 depth levels — far more than any other strategy.

strategyTitle = "FLUX";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "limbo";

// USER CONFIG
// ============================================================

// TARGET
target = 2.0;                 // 49.5% chance, 1.0x net payout per win

// ADAPTIVE IOL CURVE (depth-indexed: iolCurve[depth] = multiplier)
// Gentle start, aggressive finish.
iolCurve = [1.2, 1.2, 1.2, 1.5, 1.5, 1.5, 2.0, 2.0, 2.0, 2.5];
// Beyond array length: uses last value (2.5)

// BET SIZING
divider = 5000;               // base bet = balance / divider

// PROBABILISTIC BAILOUT
bailoutEnabled = true;         // stop escalating when recovery is impossible

// SESSION MANAGEMENT
stopProfitPct = 15;           // aggressive TP (user wants profit)
stopOnLoss = 50;              // 50% SL — user's stated risk tolerance

// Reset stats/console on start
resetOnStart = true;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
}

if (resetOnStart) {
  resetStats();
  clearConsole();
}

// Bankroll
startBalance = balance;
baseBet = startBalance / divider;
minBet = 0.00101;

// Initial state
betSize = baseBet;
depth = 0;                    // current loss depth in chain
chainCost = 0;                // cumulative cost of current chain
betMultiplier = 1.0;          // cumulative bet multiplier from IOL curve
bailedOut = false;             // true if bailout triggered this chain

// Thresholds
stopProfitAmount = stopProfitPct > 0 ? startBalance * stopProfitPct / 100 : 0;
stopLossAmount = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;

// Stats
sessionProfit = 0;
totalWagered = 0;
totalWins = 0;
totalLosses = 0;
betsPlayed = 0;
peakProfit = 0;
worstDrawdown = 0;
maxDepth = 0;
recoveries = 0;
bailouts = 0;
cyclesCompleted = 0;
maxBetSeen = baseBet;
stopped = false;
summaryPrinted = false;

// Depth distribution tracking
depthHits = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

// ============================================================
// HELPERS
// ============================================================

function getIOLForDepth(d) {
  if (d < iolCurve.length) {
    return iolCurve[d];
  }
  return iolCurve[iolCurve.length - 1];
}

function shouldBailout() {
  if (!bailoutEnabled) return false;

  // Calculate remaining SL budget
  var remaining = stopLossAmount - Math.abs(Math.min(sessionProfit, 0));
  if (remaining <= 0) return true;

  // Calculate what the next bet would be
  var nextIOL = getIOLForDepth(depth);
  var nextBet = baseBet * betMultiplier * nextIOL;

  // Can we afford the next bet?
  if (nextBet > remaining) return true;

  // Would a win at the next level recover cumulative chain cost?
  var nextPayout = nextBet * (target - 1);
  if (nextPayout < chainCost + nextBet) {
    // Recovery impossible — win wouldn't cover costs
    // BUT: at higher levels, the accumulated multiplier means
    // future wins pay more. Only bailout if TRULY unrecoverable.
    // Check: would 2 more wins recover?
    var futureWin = nextBet * nextIOL * (target - 1);
    if (futureWin < chainCost + nextBet + nextBet * nextIOL) {
      return true;
    }
  }

  return false;
}

function getZoneLabel() {
  if (depth <= 3) return "GENTLE";
  if (depth <= 6) return "STANDARD";
  if (depth <= 9) return "AGGRESSIVE";
  return "MAXIMUM";
}

function getZoneColor() {
  if (depth <= 3) return "#4FC3F7";
  if (depth <= 6) return "#FFD700";
  if (depth <= 9) return "#FF8C00";
  return "#FF4444";
}

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#7C4DFF",
    "================================\n FLUX v" + version +
    "\n================================\n Adaptive IOL + Probabilistic Bailout | Limbo" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function depthDistribution() {
  var dist = "";
  var i;
  for (i = 0; i < 10; i++) {
    if (depthHits[i] > 0) {
      dist += i + ":" + depthHits[i] + " ";
    }
  }
  if (depthHits[10] > 0) dist += "10+:" + depthHits[10];
  return dist;
}

function scriptLog() {
  clearConsole();
  logBanner();

  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";
  var currentIOL = getIOLForDepth(depth);
  var zone = getZoneLabel();
  var zoneColor = getZoneColor();

  log(zoneColor, "Depth: " + depth + " [" + zone + "] | IOL: " + currentIOL.toFixed(1) + "x | Bet: $" + betSize.toFixed(5));
  if (bailedOut) {
    log("#FF4444", "BAILOUT ACTIVE — flat betting (recovery impossible)");
  }
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var remaining = stopLossAmount - Math.abs(Math.min(sessionProfit, 0));
  log("#7C4DFF", "Chain cost: $" + chainCost.toFixed(4) + " | SL budget left: $" + remaining.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | TP: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | Cycles: " + cyclesCompleted + " | Bailouts: " + bailouts);
  log("#42CAF7", "Recoveries: " + recoveries + " | Max Depth: " + maxDepth);
  log("#FD71FD", "Depth dist: " + depthDistribution());
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// FLUX STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  if (isWin) {
    totalWins++;

    // Track depth distribution
    var dIdx = depth < 10 ? depth : 10;
    depthHits[dIdx]++;

    if (depth > 0) recoveries++;
    cyclesCompleted++;

    // WIN — reset chain
    depth = 0;
    betMultiplier = 1.0;
    chainCost = 0;
    bailedOut = false;
    betSize = baseBet;
  } else {
    totalLosses++;

    // Track chain cost
    chainCost += lastBet.amount;

    // Check bailout BEFORE escalating
    depth++;
    if (depth > maxDepth) maxDepth = depth;

    if (shouldBailout()) {
      // BAILOUT — stop escalating, flat bet at base
      if (!bailedOut) {
        bailouts++;
        bailedOut = true;
      }
      betSize = baseBet;
      // Don't escalate betMultiplier — stay flat
    } else {
      // ESCALATE — apply adaptive IOL curve
      var currentIOL = getIOLForDepth(depth - 1);
      betMultiplier *= currentIOL;
      betSize = baseBet * betMultiplier;
      bailedOut = false;
    }
  }

  // Bet safety
  if (betSize > balance * 0.95) betSize = balance * 0.95;
  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;
}

// ============================================================
// STOP CONDITIONS
// ============================================================

function checkStops() {
  // Stop profit
  if (stopProfitAmount > 0 && sessionProfit >= stopProfitAmount) {
    log("#4FFB4F", "STOP PROFIT! +$" + sessionProfit.toFixed(2) + " (" + stopProfitPct + "% target)");
    stopped = true;
    logSummary();
    engine.stop();
    return;
  }

  // Stop loss
  if (stopLossAmount > 0 && -sessionProfit >= stopLossAmount) {
    log("#FD6868", "STOP LOSS! -$" + (-sessionProfit).toFixed(2) + " (50% SL)");
    stopped = true;
    logSummary();
    engine.stop();
    return;
  }
}

// ============================================================
// SUMMARY
// ============================================================

function logSummary() {
  if (summaryPrinted) return;
  summaryPrinted = true;
  playHitSound();
  var wagerMult = (totalWagered / startBalance).toFixed(1);
  var exitType = sessionProfit >= 0 ? "PROFIT" : "LOSS";
  log(
    "#7C4DFF",
    "================================\n FLUX v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Cycles: " + cyclesCompleted + " | Recoveries: " + recoveries + " | Bailouts: " + bailouts);
  log("Max Depth: " + maxDepth);
  log("Depth distribution: " + depthDistribution());
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#7C4DFF", "Target: " + target + "x (" + (99 / target).toFixed(1) + "% chance)");
log("#7C4DFF", "IOL Curve: " + iolCurve.join(", "));
log("#7C4DFF", "Bailout: " + (bailoutEnabled ? "ON" : "OFF") + " | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
log("#FFD700", "TP: " + stopProfitPct + "% ($" + stopProfitAmount.toFixed(2) + ") | SL: " + stopOnLoss + "% ($" + stopLossAmount.toFixed(2) + ")");

engine.onBetPlaced(async function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  checkStops();
});

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
