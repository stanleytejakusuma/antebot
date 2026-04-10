// APEX v1.0.0 — Escalating Target IOL (Limbo)
// Completely new thesis, separate from the Snake Family.
//
// CORE IDEA: On loss, escalate BOTH bet size AND target multiplier.
// Snake Family only escalates bet size at a fixed target.
// APEX escalates the target too — each successive loss hits a harder
// but higher-paying multiplier. This is limbo-native (impossible in
// roulette/BJ where you don't control the multiplier).
//
// ADVANTAGE: Far more capital-efficient than standard IOL.
// At recovery level 4: 130%+ ROI vs Snake Family's ~34% ROI.
// The elevated target means each recovery win pays disproportionately more.
//
// MECHANIC:
//   Base: bet at startTarget (2.0x, 49.5% chance)
//   On loss: target *= targetStep, betSize *= betIOL (dual escalation)
//   Target caps at targetCap — beyond that, only bet escalates
//   On win: reset BOTH target and bet to base, pocket profit
//
// ESCALATION SCHEDULE (targetStep=1.15, betIOL=1.5, cap=10x):
//   Level  Target  Chance  BetMult
//     0    2.00x   49.5%   1.0x
//     1    2.30x   43.0%   1.5x
//     2    2.65x   37.4%   2.25x
//     3    3.04x   32.6%   3.38x
//     4    3.50x   28.3%   5.06x
//     5    4.02x   24.6%   7.59x
//    ...
//    11    9.31x   10.6%   86.5x
//    12   10.00x    9.9%   129.7x  (cap)

strategyTitle = "APEX";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "limbo";

// USER CONFIG
// ============================================================

// TARGET ESCALATION
startTarget = 2.0;            // starting multiplier (49.5% chance)
targetStep = 1.15;            // multiply target by this on each loss
targetCap = 10.0;             // stop escalating target beyond this

// BET ESCALATION
betIOL = 1.5;                 // multiply bet by this on each loss
divider = 10000;              // base bet = balance / divider

// SESSION MANAGEMENT
stopProfitPct = 10;           // exit at +10% profit
stopOnLoss = 30;              // hard stop loss (% of balance)

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
target = startTarget;
escalationLevel = 0;

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
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
maxLevel = 0;
recoveries = 0;
maxBetSeen = baseBet;
stopped = false;
summaryPrinted = false;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#FF8C00",
    "================================\n APEX v" + version +
    "\n================================\n Escalating Target IOL | Limbo" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  var chance = target > 0 ? (99 / target).toFixed(1) : "0";
  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";

  var levelColor = escalationLevel === 0 ? "#4FC3F7" : escalationLevel < 5 ? "#FFD700" : "#FF6B6B";
  log(levelColor, "Level: " + escalationLevel + " | Target: " + target.toFixed(2) + "x (" + chance + "%) | Bet: $" + betSize.toFixed(5));
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | Target: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses + " | WS: " + winStreak + " | LS: " + lossStreak);
  log("#42CAF7", "Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// APEX STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

  // Track streaks
  if (isWin) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;
  }

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  if (isWin) {
    // WIN — reset both target and bet to base
    if (escalationLevel > 0) {
      recoveries++;
    }
    escalationLevel = 0;
    target = startTarget;
    betSize = baseBet;
  } else {
    // LOSS — escalate both target and bet
    escalationLevel++;
    if (escalationLevel > maxLevel) maxLevel = escalationLevel;

    // Escalate target (with cap)
    if (target < targetCap) {
      target *= targetStep;
      if (target > targetCap) target = targetCap;
    }

    // Escalate bet
    betSize *= betIOL;
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
  log(
    "#FF8C00",
    "================================\n APEX v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Longest WS: " + longestWinStreak + " | Longest LS: " + longestLossStreak);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#FF8C00", "Target: " + startTarget + "x -> " + targetCap + "x (step " + targetStep + "x/loss)");
log("#FF8C00", "Bet IOL: " + betIOL + "x/loss | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
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
