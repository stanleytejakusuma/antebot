// NOVA v1.0.0 — B2B Chain Let-it-Ride (Keno)
// First B2B profit strategy for Keno. Separate from Snake Family and Limbo family.
//
// CORE IDEA: Hunt consecutive wins. On win, bet = payout (let it ride).
// One B2B streak of N wins compounds into massive payoff.
// Bank after N consecutive wins to lock in profit. IOL on chain failure.
//
// MECHANIC:
//   Base: 9 picks, high risk, base bet from divider
//   On win: betSize = lastBet.payout (compound the streak)
//   After chainTarget consecutive wins: BANK! Reset to base bet.
//   On loss mid-chain: lost chain bet. IOL for next chain attempt.
//   On loss at base: IOL for next attempt.
//
// CHAIN ECONOMICS (example: 9 picks, high risk):
//   Chain of 3 wins at ~2x each: 2^3 = 8x payout on initial bet
//   Chain of 5 wins: 2^5 = 32x payout
//   IOL between chains: gentle 1.2x (8x+ chain payout covers many failures)
//
// Number selection: random (provably fair RNG = number choice irrelevant)

strategyTitle = "NOVA";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "keno";

// USER CONFIG
// ============================================================

// CHAIN SETTINGS
chainTarget = 3;              // bank after this many consecutive wins
chainIOL = 1.2;               // IOL on chain failure (gentle — chain payout is large)

// KENO CONFIG
numPicks = 9;                 // number of picks per bet
kenoRisk = "high";            // risk level for bigger B2B payouts

// BET SIZING
divider = 10000;              // base chain bet = balance / divider

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

// Chain state
chainStep = 0;                // consecutive wins in current chain
chainBet = baseBet;           // current chain's base bet (escalates on fail)
chainAttempts = 0;            // consecutive failed chains

// Initial state
betSize = chainBet;
risk = kenoRisk;
numbers = randomNumbers(numPicks);

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
chainsCompleted = 0;
chainsFailed = 0;
maxChainAttempts = 0;
maxBetSeen = baseBet;
biggestChainPayout = 0;
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
  for (i = pool.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var temp = pool[i];
    pool[i] = pool[j];
    pool[j] = temp;
  }
  return pool.slice(0, count);
}

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#FF6D00",
    "================================\n NOVA v" + version +
    "\n================================\n B2B Chain Let-it-Ride | Keno" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function chainProgressBar() {
  var bar = "";
  var i;
  for (i = 0; i < chainTarget; i++) {
    if (i < chainStep) {
      bar += "[WIN] ";
    } else if (i === chainStep) {
      bar += "[>>>] ";
    } else {
      bar += "[   ] ";
    }
  }
  return bar;
}

function scriptLog() {
  clearConsole();
  logBanner();

  var drawdown = peakProfit - sessionProfit;
  var ddBar = drawdown > 0.001 ? " | DD: -$" + drawdown.toFixed(2) : "";
  var wagerMult = totalWagered > 0 ? (totalWagered / startBalance).toFixed(1) : "0.0";

  var chainColor = chainStep === 0 ? "#4FC3F7" : chainStep < chainTarget - 1 ? "#FFD700" : "#00FF7F";
  log(chainColor, "Chain: " + chainProgressBar() + " (" + chainStep + "/" + chainTarget + ")");
  log("#FF6D00", "Chain bet: $" + chainBet.toFixed(5) + " | Attempts: " + chainAttempts + " | IOL: " + chainIOL + "x");
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | TP: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "Chains: " + chainsCompleted + " completed / " + chainsFailed + " failed");
  log("#42CAF7", "Max streak: " + maxChainAttempts + " failed | Best payout: $" + biggestChainPayout.toFixed(4));
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// NOVA STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  // Track profit
  sessionProfit += (lastBet.payout - lastBet.amount);
  if (sessionProfit > peakProfit) peakProfit = sessionProfit;
  if (sessionProfit < worstDrawdown) worstDrawdown = sessionProfit;

  var isWin = lastBet.win;

  if (isWin) {
    totalWins++;
    chainStep++;

    if (chainStep >= chainTarget) {
      // CHAIN COMPLETE! Bank the profits.
      chainsCompleted++;
      var chainPayout = lastBet.payout;
      if (chainPayout > biggestChainPayout) biggestChainPayout = chainPayout;
      log("#00FF7F", "CHAIN COMPLETE! " + chainTarget + " B2B wins! Payout: $" + chainPayout.toFixed(4));

      // Reset chain
      chainStep = 0;
      chainAttempts = 0;
      chainBet = baseBet;
      betSize = chainBet;
    } else {
      // Mid-chain: LET IT RIDE — bet the full payout
      betSize = lastBet.payout;
    }

    // Fresh random numbers each bet
    numbers = randomNumbers(numPicks);

  } else {
    totalLosses++;

    // Chain failed (or base bet lost)
    chainStep = 0;
    chainAttempts++;
    chainsFailed++;
    if (chainAttempts > maxChainAttempts) maxChainAttempts = chainAttempts;

    // IOL: escalate next chain's bet
    chainBet *= chainIOL;
    betSize = chainBet;

    // Fresh random numbers
    numbers = randomNumbers(numPicks);
  }

  // Bet safety
  if (betSize > balance * 0.95) {
    // Soft bust on chain bet — reset IOL
    chainBet = baseBet;
    chainAttempts = 0;
    chainStep = 0;
    betSize = baseBet;
  }
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
    "#FF6D00",
    "================================\n NOVA v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Chains: " + chainsCompleted + " completed / " + chainsFailed + " failed");
  log("Max chain attempts streak: " + maxChainAttempts);
  log("Best chain payout: $" + biggestChainPayout.toFixed(4));
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#FF6D00", "Chain: " + chainTarget + " consecutive wins to bank | " + numPicks + " picks | " + kenoRisk + " risk");
log("#FF6D00", "Chain IOL: " + chainIOL + "x on fail | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
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
