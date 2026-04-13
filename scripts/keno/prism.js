// PRISM v1.0.0 — 3D Escalation IOL (Keno)
// First Keno profit strategy. Separate from Snake Family and Limbo family.
//
// CORE IDEA: Keno has THREE escalation dimensions no other game has:
//   1. Pick count (9 -> 7 -> 5 -> 3 -> 1) — fewer picks = bigger payout
//   2. Risk level (medium -> high) — higher risk = more extreme payout curve
//   3. Bet size (IOL 1.3x) — standard bet escalation
//
// On FULL LOSS (0x): escalate all three dimensions
// On PARTIAL MATCH (0 < mult < 1.0): escalate bet only (close to hitting)
// On WIN (mult >= 1.0): reset all three to base
//
// ESCALATION SCHEDULE:
//   Level  Picks  Risk    Bet mult  Profile
//     0      9    medium   1.0x     Safe start (many picks, balanced risk)
//     1      7    medium   1.3x     Tightening coverage
//     2      5    high     1.69x    Fewer picks, aggressive risk
//     3      3    high     2.20x    Sniper mode
//     4      1    high     2.86x    Moon shot
//     5+     1    high     +1.3x    Bet-only escalation (picks bottomed out)
//
// Number selection: random (provably fair RNG = number choice irrelevant)

strategyTitle = "PRISM";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "keno";

// USER CONFIG
// ============================================================

// ESCALATION SCHEDULE (picks per level)
pickSchedule = [9, 7, 5, 3, 1];  // reduces on each full loss
// Risk schedule: medium for first 2 levels, high for rest
riskSchedule = ["medium", "medium", "high", "high", "high"];

// BET ESCALATION
betIOL = 1.3;                 // multiply bet by this on each loss
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
escalationLevel = 0;
betSize = baseBet;
risk = riskSchedule[0];
currentPicks = pickSchedule[0];
numbers = randomNumbers(currentPicks);

// Thresholds
stopProfitAmount = stopProfitPct > 0 ? startBalance * stopProfitPct / 100 : 0;
stopLossAmount = stopOnLoss > 0 ? startBalance * stopOnLoss / 100 : 0;

// Stats
sessionProfit = 0;
totalWagered = 0;
totalWins = 0;
totalLosses = 0;
partialMatches = 0;
betsPlayed = 0;
peakProfit = 0;
worstDrawdown = 0;
maxLevel = 0;
recoveries = 0;
maxBetSeen = baseBet;
stopped = false;
summaryPrinted = false;

// ============================================================
// HELPERS
// ============================================================

function randomNumbers(count) {
  var pool = [];
  var i;
  for (i = 0; i < 40; i++) {
    pool.push(i);
  }
  // Fisher-Yates shuffle
  for (i = pool.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var temp = pool[i];
    pool[i] = pool[j];
    pool[j] = temp;
  }
  return pool.slice(0, count);
}

function getPicksForLevel(level) {
  if (level < pickSchedule.length) {
    return pickSchedule[level];
  }
  return pickSchedule[pickSchedule.length - 1];
}

function getRiskForLevel(level) {
  if (level < riskSchedule.length) {
    return riskSchedule[level];
  }
  return riskSchedule[riskSchedule.length - 1];
}

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#E040FB",
    "================================\n PRISM v" + version +
    "\n================================\n 3D Escalation IOL | Keno" +
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

  var levelColor = escalationLevel === 0 ? "#4FC3F7" : escalationLevel < 3 ? "#FFD700" : "#FF6B6B";
  log(levelColor, "Level: " + escalationLevel + " | Picks: " + currentPicks + " | Risk: " + risk + " | Bet: $" + betSize.toFixed(5));
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | TP: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "W/L/P: " + totalWins + "/" + totalLosses + "/" + partialMatches);
  log("#42CAF7", "Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// PRISM STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  var mult = lastBet.payoutMultiplier;

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  if (mult >= 1.0) {
    // WIN — reset all three dimensions
    totalWins++;
    if (escalationLevel > 0) {
      recoveries++;
    }
    escalationLevel = 0;
    currentPicks = getPicksForLevel(0);
    risk = getRiskForLevel(0);
    betSize = baseBet;
    numbers = randomNumbers(currentPicks);

  } else if (mult > 0 && mult < 1.0) {
    // PARTIAL MATCH — escalate bet only (close to hitting)
    partialMatches++;
    betSize *= betIOL;
    // Keep same picks and risk — we're in the right zone
    numbers = randomNumbers(currentPicks);

  } else {
    // FULL LOSS (0x) — escalate all three dimensions
    totalLosses++;
    escalationLevel++;
    if (escalationLevel > maxLevel) maxLevel = escalationLevel;

    currentPicks = getPicksForLevel(escalationLevel);
    risk = getRiskForLevel(escalationLevel);
    betSize *= betIOL;
    numbers = randomNumbers(currentPicks);
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
    "#E040FB",
    "================================\n PRISM v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L/Partial: " + totalWins + "/" + totalLosses + "/" + partialMatches);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#E040FB", "Picks: " + pickSchedule.join(" -> ") + " | Risk: " + riskSchedule.join(" -> "));
log("#E040FB", "Bet IOL: " + betIOL + "x/loss | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
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
