// HELIX v1.0.0 — Escalating Chain IOL (HiLo)
// Separate from Snake Family. Extension of APEX thesis to HiLo.
//
// CORE IDEA: On loss, escalate THREE HiLo-native dimensions:
//   1. Cashout target (1.5x -> 2.0x -> 2.5x -> 3.0x -> 5.0x)
//   2. Skip set width (wide -> narrow — accept more predictions per chain)
//   3. Bet size (IOL 1.3x per loss)
// On WIN: reset all three to base.
//
// WHY THIS WORKS: HiLo has a built-in chain mechanic — each bet IS
// a chain of predictions. The cashout target controls the chain length
// AND the payout. Higher cashout = longer chain = more risk but bigger
// recovery payout. The skip set controls HOW MANY cards you'll predict
// on — wider skip = safer predictions but slower chains.
//
// ESCALATION SCHEDULE:
//   Level  Cashout  Skip         Bet mult  Win%  Profile
//     0    1.5x     {5,6,7,8,9}  1.0x     ~75%  Safe (skip risky cards)
//     1    2.0x     {6,7,8}      1.3x     ~64%  Standard
//     2    2.5x     {7}          1.69x    ~55%  Aggressive (skip only 7)
//     3    3.0x     {7}          2.20x    ~51%  Sniper
//     4    5.0x     {}           2.86x    ~33%  Moon shot (skip nothing)
//     5+   5.0x     {}           +1.3x    ~33%  Bet-only escalation
//
// Start card: A (Ace) — guaranteed 92% first prediction (bet high).

strategyTitle = "HELIX";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "hilo";

// USER CONFIG
// ============================================================

// ESCALATION SCHEDULES
cashoutSchedule = [1.5, 2.0, 2.5, 3.0, 5.0];
// Skip sets: [min, max] pairs — cards in this range get skipped
// Level 0: skip 5-9 (very safe, only predict on 1-4 and 10-13)
// Level 1: skip 6-8 (standard, like SIDEWINDER)
// Level 2: skip 7 only (aggressive)
// Level 3: skip 7 only
// Level 4: skip nothing (accept all cards)
skipSchedule = [[5, 9], [6, 8], [7, 7], [7, 7], [0, 0]];

// BET ESCALATION
betIOL = 1.3;                 // multiply bet by this on each loss
divider = 10000;              // base bet = balance / divider

// Starting card (A = guaranteed ~92% first prediction)
startCard = { rank: "A", suit: "C" };

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

// Card value lookup
rankValues = {
  "A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
  "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13
};

// Initial state
escalationLevel = 0;
betSize = baseBet;
currentCashout = cashoutSchedule[0];
currentSkipMin = skipSchedule[0][0];
currentSkipMax = skipSchedule[0][1];

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
maxLevel = 0;
recoveries = 0;
maxBetSeen = baseBet;
stopped = false;
summaryPrinted = false;

// ============================================================
// HELPERS
// ============================================================

function getCashoutForLevel(level) {
  if (level < cashoutSchedule.length) {
    return cashoutSchedule[level];
  }
  return cashoutSchedule[cashoutSchedule.length - 1];
}

function getSkipForLevel(level) {
  if (level < skipSchedule.length) {
    return skipSchedule[level];
  }
  return skipSchedule[skipSchedule.length - 1];
}

function updateEscalationState() {
  currentCashout = getCashoutForLevel(escalationLevel);
  var skip = getSkipForLevel(escalationLevel);
  currentSkipMin = skip[0];
  currentSkipMax = skip[1];
}

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00E5FF",
    "================================\n HELIX v" + version +
    "\n================================\n Escalating Chain IOL | HiLo" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function skipLabel() {
  if (currentSkipMin === 0 && currentSkipMax === 0) return "none";
  if (currentSkipMin === currentSkipMax) return "" + currentSkipMin;
  return currentSkipMin + "-" + currentSkipMax;
}

function scriptLog() {
  clearConsole();
  logBanner();

  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";

  var levelColor = escalationLevel === 0 ? "#4FC3F7" : escalationLevel < 3 ? "#FFD700" : "#FF6B6B";
  log(levelColor, "Level: " + escalationLevel + " | Cashout: " + currentCashout.toFixed(1) + "x | Skip: {" + skipLabel() + "} | Bet: $" + betSize.toFixed(5));
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | TP: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses);
  log("#42CAF7", "Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// GAME ROUND — Per-card decision within each hand
// ============================================================

engine.onGameRound(function (currentBet) {
  var rounds = currentBet.state.rounds;
  var roundCount = rounds ? rounds.length : 0;
  var skipCount = 0;
  var accumulated = 0;
  var cardRank = currentBet.state.startCard ? currentBet.state.startCard.rank : "A";

  if (roundCount > 0) {
    for (var i = 0; i < roundCount; i++) {
      if (rounds[i].guess === "skip") skipCount++;
    }
    cardRank = rounds[roundCount - 1].card.rank;
    accumulated = rounds[roundCount - 1].payoutMultiplier;
  }

  var cardVal = rankValues[cardRank] || 7;

  // CASHOUT: if accumulated multiplier meets current target
  if (accumulated >= currentCashout) {
    return HILO_CASHOUT;
  }

  // SKIP: if card is in current skip range (and skip is enabled)
  if (currentSkipMin > 0 && currentSkipMax > 0) {
    if (cardVal >= currentSkipMin && cardVal <= currentSkipMax && skipCount < 52) {
      return HILO_SKIP;
    }
  }

  // BET: high if low card, low if high card
  if (cardVal <= 7) {
    return HILO_BET_HIGH;
  }
  return HILO_BET_LOW;
});

// ============================================================
// BET PLACED — Session-level logic after each hand
// ============================================================

engine.onBetPlaced(async function () {
  if (stopped) return;

  betsPlayed++;
  totalWagered += lastBet.amount;

  var isWin = lastBet.win;

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  if (isWin) {
    totalWins++;
    if (escalationLevel > 0) {
      recoveries++;
    }

    // WIN — reset all three dimensions
    escalationLevel = 0;
    updateEscalationState();
    betSize = baseBet;
  } else {
    totalLosses++;

    // LOSS — escalate all three dimensions
    escalationLevel++;
    if (escalationLevel > maxLevel) maxLevel = escalationLevel;
    updateEscalationState();
    betSize *= betIOL;
  }

  // Bet safety
  if (betSize > balance * 0.95) betSize = balance * 0.95;
  if (betSize < minBet) betSize = minBet;
  if (betSize > maxBetSeen) maxBetSeen = betSize;

  scriptLog();
  checkStops();
});

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
    "#00E5FF",
    "================================\n HELIX v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Recoveries: " + recoveries + " | Max Level: " + maxLevel);
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#00E5FF", "Cashout: " + cashoutSchedule.join("x -> ") + "x");
log("#00E5FF", "Skip: " + skipSchedule.map(function(s) { return s[0] === 0 ? "none" : s[0] + "-" + s[1]; }).join(" -> "));
log("#00E5FF", "Bet IOL: " + betIOL + "x/loss | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
log("#FFD700", "Stop profit: " + stopProfitPct + "% ($" + stopProfitAmount.toFixed(2) + ") | Stop loss: " + stopOnLoss + "%");

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary();
});
