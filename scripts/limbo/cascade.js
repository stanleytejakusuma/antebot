// CASCADE v1.0.0 — Chain-Level IOL (Limbo)
// Completely new thesis, separate from the Snake Family.
//
// CORE IDEA: Hunt multi-win CHAINS (3 consecutive wins at 2.0x = 8x payout).
// IOL kicks in only on CHAIN FAILURE, not individual bet failure.
// This means IOL can be very gentle (1.25x) because the 8x chain payout
// covers everything.
//
// KEY INSIGHT: No matter where in a chain you fail, you lose exactly
// the chain's initial bet. If you win step 1 (get 2x), bet it all
// on step 2 and lose — you lost your original bet, not 2x.
// This makes chain cost = 1x bet, chain payout = 8x bet.
//
// MECHANIC:
//   Attempt chain: bet B at 2.0x
//     Win step 1 → bet payout (2B) at 2.0x
//     Win step 2 → bet payout (4B) at 2.0x
//     Win step 3 → CHAIN COMPLETE! Received 8B. Reset, pocket profit.
//     Lose at any step → chain failed. Lost B. IOL for next chain.
//
// CHAIN ECONOMICS:
//   Chain success: (0.495)^3 = 12.1% chance, 8x payout
//   Chain fail: 87.9% chance, 1x cost
//   After 10 fails at IOL 1.25: next chain payout = 74.5x base
//   P(bust in 35 chains): < 1%

strategyTitle = "CASCADE";
version = "1.0.0";
author = "stanz";
scripter = "stanz";

game = "limbo";

// USER CONFIG
// ============================================================

// CHAIN SETTINGS
chainTarget = 2.0;            // target for each chain step
chainLength = 3;              // consecutive wins needed for complete chain
chainIOL = 1.25;              // IOL on chain failure (gentle)

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
chainStep = 0;                // 0 = start of new chain, 1 = won step 1, 2 = won step 2
chainBet = baseBet;           // current chain's initial bet (escalates on fail)
chainAttempts = 0;            // consecutive failed chains (resets on success)

// Initial bet
betSize = chainBet;
target = chainTarget;

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
stopped = false;
summaryPrinted = false;

// ============================================================
// LOGGING
// ============================================================

function logBanner() {
  log(
    "#00BFFF",
    "================================\n CASCADE v" + version +
    "\n================================\n Chain-Level IOL | Limbo" +
    "\n by " + author +
    "\n-------------------------------------------"
  );
}

function chainProgressBar() {
  var bar = "";
  var i;
  for (i = 0; i < chainLength; i++) {
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

  var chainColor = chainStep === 0 ? "#4FC3F7" : chainStep === 1 ? "#FFD700" : "#00FF7F";
  log(chainColor, "Chain: " + chainProgressBar() + " (" + chainStep + "/" + chainLength + ")");
  log("#FF8C00", "Chain bet: $" + chainBet.toFixed(5) + " | Attempts: " + chainAttempts + " | IOL: " + chainIOL + "x");
  log("#00FF7F", "Balance: $" + balance.toFixed(2) + " | P&L: $" + sessionProfit.toFixed(2) + ddBar);
  log("#4FFB4F", "Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));

  var targetBar = stopProfitAmount > 0 ? " | Target: $" + sessionProfit.toFixed(2) + "/$" + stopProfitAmount.toFixed(2) : "";
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)" + targetBar);

  log("#FFDB55", "Chains: " + chainsCompleted + " completed / " + chainsFailed + " failed");
  log("#42CAF7", "Max streak: " + maxChainAttempts + " failed chains");
  log("#FD71FD", "Bets: " + betsPlayed + " | Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// CASCADE STRATEGY
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
    chainStep++;

    if (chainStep >= chainLength) {
      // CHAIN COMPLETE! Big payday.
      chainsCompleted++;
      log("#00FF7F", "CHAIN COMPLETE! " + chainLength + " wins! Payout: $" + lastBet.payout.toFixed(4));

      // Reset chain
      chainStep = 0;
      chainAttempts = 0;
      chainBet = baseBet;
      betSize = chainBet;
    } else {
      // Mid-chain: let it ride — bet the full payout
      betSize = lastBet.payout;
    }
  } else {
    totalLosses++;

    // Chain failed — lose the original chain bet
    chainStep = 0;
    chainAttempts++;
    chainsFailed++;
    if (chainAttempts > maxChainAttempts) maxChainAttempts = chainAttempts;

    // IOL: escalate next chain's bet
    chainBet *= chainIOL;
    betSize = chainBet;
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
    "#00BFFF",
    "================================\n CASCADE v" + version + " — " + exitType + "\n================================"
  );
  log("#4FFB4F", "P&L: $" + sessionProfit.toFixed(2) + " | Balance: $" + balance.toFixed(2));
  log("#FFD700", "Wager: $" + totalWagered.toFixed(2) + " (" + wagerMult + "x)");
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Chains: " + chainsCompleted + " completed / " + chainsFailed + " failed");
  log("Max chain attempts streak: " + maxChainAttempts);
  log("Peak: $" + peakProfit.toFixed(2) + " | Worst DD: $" + worstDrawdown.toFixed(2));
  log("Max Bet: $" + maxBetSeen.toFixed(4));
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

logBanner();
log("#00FF7F", "Starting balance: $" + startBalance.toFixed(2));
log("#00BFFF", "Chain: " + chainLength + " wins at " + chainTarget + "x = " + Math.pow(chainTarget, chainLength).toFixed(0) + "x payout");
log("#00BFFF", "Chain IOL: " + chainIOL + "x on fail | div=" + divider + " ($" + baseBet.toFixed(4) + ")");
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
