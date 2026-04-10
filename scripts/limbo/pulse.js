// PULSE v1.0.0 — Windowed Stint IOL (Limbo)
// Completely new thesis, separate from the Snake Family.
//
// CORE IDEA: Don't bet real money on every roll.
// Observe losses at minimum bet (preroll), then enter real IOL
// for a capped "stint", then RETREAT if no hit. IOL chain is
// bounded by stint length — prevents the infinite blowup that
// causes bust in standard IOL strategies.
//
// Derived from Vrafasky's RollingStint with our own hardening.
//
// MECHANIC:
//   PREROLL PHASE: bet minBet for N rolls (almost free observation)
//   STINT PHASE:   bet real money with IOL for M rolls
//     - Win during stint: profit, reset IOL, back to preroll
//     - Stint expires without win: retreat, reset IOL, try again
//
// IOL is auto-calculated from target: iol = 1/(target-1) + 1
// This ensures each win EXACTLY recovers all previous stint losses + profit.
// Divider is auto-calculated from coveredStreak.
//
// STINT ECONOMICS (target=5.0x, stint=15):
//   P(at least 1 win in 15 bets at 19.8%): 96.6%
//   Full stint wipeout cost: ~$10.42 (10.4% of balance)
//   Can sustain ~3 wipeouts before SL ($30)
//   Each win profits exactly 4x base at the level it hits.

strategyTitle = "PULSE";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "limbo";

// USER CONFIG
// ============================================================

// TARGET & IOL
target = 5.0;                 // 19.8% chance, 4x profit per win
// IOL auto-calculated below: 1/(target-1)+1

// STINT SETTINGS
prerollLength = 5;            // observation bets at minBet before stint
stintLength = 15;             // real IOL bets per stint (capped)

// COVERAGE
coveredStreak = 25;           // safety margin for divider calculation
// divider auto-calculated below from coveredStreak

// SESSION MANAGEMENT
stopProfitPct = 10;           // exit at +10% profit
stopOnLoss = 30;              // hard stop loss (% of balance)

// Reset stats/console on start
resetOnStart = true;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

// Auto-calculate IOL and divider (from RollingStint formula)
function calcIncrease(payout) {
  return 1 / (payout - 1) + 1;
}

function calcSum(r, t) {
  return (1 - Math.pow(r, t)) / (1 - r);
}

function calcDivider(iolVal, maxStreak) {
  return Math.ceil(calcSum(iolVal, maxStreak)) + 1;
}

iol = calcIncrease(target);
divider = calcDivider(iol, coveredStreak);

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

// State
phase = "preroll";            // "preroll" or "stint"
prerollCount = 0;             // bets in current preroll
stintCount = 0;               // bets in current stint
stintBet = baseBet;           // current stint's IOL-escalated bet

// Initial bet
betSize = minBet;

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
stintsAttempted = 0;
stintsWon = 0;
stintsFailed = 0;
maxStintDepth = 0;
longestPreroll = 0;
maxBetSeen = baseBet;
stopped = false;
summaryPrinted = false;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#DA70D6",
    "================================\n PULSE v" + version +
    "\n================================\n Windowed Stint IOL | Limbo" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";

  var phaseLabel;
  var phaseColor;
  if (phase === "preroll") {
    phaseLabel = "PREROLL (" + prerollCount + "/" + prerollLength + ")";
    phaseColor = "#808080";
  } else {
    phaseLabel = "STINT (" + stintCount + "/" + stintLength + ") | IOL depth: " + stintCount;
    phaseColor = stintCount < 5 ? "#4FC3F7" : stintCount < 10 ? "#FFD700" : "#FF6B6B";
  }

  log(phaseColor, "Phase: " + phaseLabel);
  log("#DA70D6", "Stint bet: $" + stintBet.toFixed(5) + " | Target: " + target.toFixed(1) + "x (" + (99 / target).toFixed(1) + "%)");
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | Target: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  var winRate = stintsAttempted > 0 ? (stintsWon / stintsAttempted * 100).toFixed(1) : "0.0";
  log("#FFDB55", "Stints: " + stintsWon + "W / " + stintsFailed + "F (" + winRate + "% win)");
  log("#42CAF7", "Max stint depth: " + maxStintDepth + " | IOL: " + iol.toFixed(4) + "x | div=" + divider);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// PULSE STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  if (isWin) totalWins++;
  else totalLosses++;

  // --- PREROLL PHASE ---
  if (phase === "preroll") {
    if (!isWin) {
      prerollCount++;
    }
    // Preroll counts consecutive losses at minBet
    if (isWin) {
      // Reset preroll counter on win (we want N consecutive losses)
      prerollCount = 0;
    }

    // Check: transition to stint?
    if (prerollCount >= prerollLength) {
      phase = "stint";
      stintCount = 0;
      stintBet = baseBet;
      stintsAttempted++;
      betSize = stintBet;
      if (prerollCount > longestPreroll) longestPreroll = prerollCount;
      return;
    }

    // Stay in preroll
    betSize = minBet;
    return;
  }

  // --- STINT PHASE ---
  if (phase === "stint") {
    stintCount++;
    if (stintCount > maxStintDepth) maxStintDepth = stintCount;

    if (isWin) {
      // WIN during stint! Profit captured. Reset and retreat.
      stintsWon++;
      log("#4FFB4F", "STINT WIN at depth " + stintCount + "! Payout: $" + lastBet.payout.toFixed(4));

      // Reset to preroll
      phase = "preroll";
      prerollCount = 0;
      stintCount = 0;
      stintBet = baseBet;
      betSize = minBet;
    } else {
      // LOSS during stint — IOL for next stint bet
      if (stintCount >= stintLength) {
        // Stint expired! Retreat without a win.
        stintsFailed++;
        log("#FF6B6B", "STINT EXPIRED after " + stintLength + " bets. Retreating.");

        // Reset to preroll
        phase = "preroll";
        prerollCount = 0;
        stintCount = 0;
        stintBet = baseBet;
        betSize = minBet;
      } else {
        // IOL: escalate for next stint bet
        stintBet *= iol;
        betSize = stintBet;
      }
    }
  }

  // Bet safety
  if (betSize > balance * 0.95) {
    // Soft bust — retreat to preroll
    phase = "preroll";
    prerollCount = 0;
    stintCount = 0;
    stintBet = baseBet;
    betSize = minBet;
  }
  if (betSize < minBet && phase === "stint") betSize = minBet;
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
    log("#FD6868", "STOP LOSS! -$" + (-sessionProfit).toFixed(2));
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
  var winRate = stintsAttempted > 0 ? (stintsWon / stintsAttempted * 100).toFixed(1) : "0.0";
  log(
    "#DA70D6",
    "================================\n PULSE v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Stints: " + stintsWon + "W / " + stintsFailed + "F (" + winRate + "% win)");
  log("Max stint depth: " + maxStintDepth + " | Longest preroll: " + longestPreroll);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Max Bet: $" + maxBetSeen.toFixed(4));
  log("Auto-config: IOL=" + iol.toFixed(4) + "x | div=" + divider);
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#DA70D6", "Target: " + target + "x (" + (99 / target).toFixed(1) + "% chance)");
log("#DA70D6", "Preroll: " + prerollLength + " losses at minBet | Stint: " + stintLength + " IOL bets");
log("#DA70D6", "IOL (auto): " + iol.toFixed(4) + "x | div (auto): " + divider + " ($" + baseBet.toFixed(4) + ")");
log("#FFD700", "Stop profit: " + stopProfitPct + "% ($" + stopProfitAmount.toFixed(2) + ") | Stop loss: " + stopOnLoss + "%");

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
