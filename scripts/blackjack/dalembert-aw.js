// Action-Weighted D'Alembert for Blackjack
// Source: https://forum.antebot.com/t/perfect-bj-d-alembert-new-approach/887
// Inspired by swenmustwatchgames0's concept, refined with Vrafasky's insight
// that unit must equal startBet for D'Alembert to work.
//
// Key innovation: doubles and splits adjust by 2-4 units instead of 1,
// correctly sizing recovery to match actual money lost/won.
//
// Monte Carlo tested: div=2000, cap=10x → 10% bust rate, -$15/session on $1000.

strategyTitle = "BJ D'Alembert AW";
version = "1.0.0";
author = "swenmustwatchgames0";
scripter = "stanz";

game = "blackjack";

// USER CONFIG
// ============================================================
//
// Divider: startBet = balance / divider. Unit = startBet.
// Cap: max bet = startBet * maxBetMultiple.
//
//  Divider | Base Bet ($1000) | Bust% (2000 hands) | Mean Net
// ---------|------------------|---------------------|----------
//      500 | $2.00            | ~70%                | -$65
//     1000 | $1.00            | ~45%                | -$60
//     2000 | $0.50            | ~10%                | -$15
//     5000 | $0.20            |  ~0%                | -$14
divider = 2000;

maxBetMultiple = 10; // Cap at 10x startBet. Prevents runaway on bad streaks.

// Stop conditions. Set 0 to disable.
stopOnProfit = 0;
stopOnLoss = 300;
stopBeforeLoss = 0;

// Seed change on win streak. 0 = disabled.
seedChangeAfterWinStreak = 8;

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(1000);
  resetSeed();
  resetStats();
  clearConsole();
}

startBalance = balance;
unit = startBalance / divider;
if (unit < 0.001) unit = 0.001;
maxBet = unit * maxBetMultiple;

// State
currentBet = unit;
cycleProfit = 0;
peakProfit = 0;
handsPlayed = 0;
totalWins = 0;
totalLosses = 0;
totalPushes = 0;
totalDoubles = 0;
totalSplits = 0;
winStreak = 0;
longestWinStreak = 0;
longestLossStreak = 0;
currentLossStreak = 0;
stopped = false;

betSize = currentBet;
sideBetPerfectPairs = 0;
sideBet213 = 0;

function logBanner() {
  log(
    "#2AFFCA",
    `================================
 🃏 ${strategyTitle} v${version}
================================
 by ${author} | scripted by ${scripter}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  log("#70FD70", `Balance: $${balance.toFixed(2)} | Unit: $${unit.toFixed(4)} | Bet: $${currentBet.toFixed(4)}`);
  log("#42CAF7", `Bet Multiple: ${(currentBet / unit).toFixed(1)}x / ${maxBetMultiple}x cap`);
  log("#FFDB55", `W/L/P: ${totalWins}/${totalLosses}/${totalPushes} | Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log("#A4FD68", `Profit: $${profit.toFixed(2)} | Win Streak: ${winStreak} | Longest LS: ${longestLossStreak}`);
  log("#FD71FD", `Hands: ${handsPlayed} | Balance: $${balance.toFixed(2)}`);
}

// Detect action weight from resolved hand
function getUnitWeight() {
  // Count total exposure units from the resolved hand
  // Normal hand = 1 unit, Double = 2, Split = 2 (1 per hand), Split+Double = 4
  let hands = lastBet.state.player;
  let totalUnits = 0;

  for (let i = 0; i < hands.length; i++) {
    let actions = hands[i].actions;
    let hadDouble = false;

    for (let j = 0; j < actions.length; j++) {
      if (actions[j] === "double") {
        hadDouble = true;
        break;
      }
    }

    totalUnits += hadDouble ? 2 : 1;
  }

  return totalUnits;
}

// Main strategy logic
function mainStrategy() {
  handsPlayed++;

  if (lastBet.win && lastBet.payoutMultiplier > 1) {
    // WIN (profitable hand)
    totalWins++;
    winStreak++;
    currentLossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    let weight = getUnitWeight();
    if (lastBet.state.player.length > 1) totalSplits++;
    if (weight >= 2 && lastBet.state.player.length === 1) totalDoubles++;

    // D'Alembert: decrease by weighted units
    currentBet -= weight * unit;

    // Seed change on win streak
    if (seedChangeAfterWinStreak > 0 && winStreak >= seedChangeAfterWinStreak) {
      resetSeed();
      log("#FFFF2A", `🔄 Seed reset after ${winStreak} win streak`);
    }
  } else if (lastBet.win && lastBet.payoutMultiplier <= 1) {
    // PUSH — no change to progression
    totalPushes++;
  } else {
    // LOSS
    totalLosses++;
    currentLossStreak++;
    winStreak = 0;
    if (currentLossStreak > longestLossStreak) longestLossStreak = currentLossStreak;

    let weight = getUnitWeight();
    if (lastBet.state.player.length > 1) totalSplits++;
    if (weight >= 2 && lastBet.state.player.length === 1) totalDoubles++;

    // D'Alembert: increase by weighted units
    currentBet += weight * unit;
  }

  // Enforce bounds
  if (currentBet < unit) currentBet = unit;
  if (currentBet > maxBet) currentBet = maxBet;

  // Set next bet
  betSize = Math.round(currentBet * 100000000) / 100000000; // 8dp precision
}

// Stop checks
function stopProfitCheck() {
  if (stopOnProfit > 0 && profit >= stopOnProfit) {
    log("#4FFB4F", `✅ Stopped on $${profit.toFixed(2)} Profit`);
    stopped = true;
    engine.stop();
  }
}

function stopLossCheck() {
  if (stopOnLoss > 0 && profit < -Math.abs(stopOnLoss)) {
    log("#FD6868", `⛔ Stopped on $${(-profit).toFixed(2)} Loss`);
    stopped = true;
    engine.stop();
  }

  if (stopBeforeLoss > 0) {
    let worstCase = currentBet * 4; // split + double on both = 4x exposure
    if (profit - worstCase <= -Math.abs(stopBeforeLoss)) {
      log("#FD6868", `⛔ Stopped to prevent potential $${Math.abs(profit - worstCase).toFixed(2)} Loss`);
      stopped = true;
      engine.stop();
    }
  }
}

// Init log
logBanner();
log("#70FD70", `Starting balance: $${startBalance.toFixed(2)}`);
log("#42CAF7", `Unit: $${unit.toFixed(4)} | Max bet: $${maxBet.toFixed(4)} (${maxBetMultiple}x cap)`);
log("#FD71FD", `⚠️  D'Alembert: +N units on loss, -N units on win (N = 1 normal, 2 double/split, 4 split+double)`);

// Main loop
engine.onBetPlaced(async () => {
  if (stopped) return;

  mainStrategy();
  scriptLog();
  stopProfitCheck();
  stopLossCheck();
});

engine.onGameRound(function (currentBet, playerHandIndex) {
  if (stopped) return BLACKJACK_STAND;

  let nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, "advanced", "any");

  if (nextAction === BLACKJACK_DOUBLE) {
    betSize *= 2;
  }

  return nextAction;
});

engine.onBettingStopped(function () {
  playHitSound();
  log(
    "#2AFFCA",
    `================================
 🃏 ${strategyTitle} — Session Over
================================`
  );
  log(`Hands: ${handsPlayed} | W/L/P: ${totalWins}/${totalLosses}/${totalPushes}`);
  log(`Doubles: ${totalDoubles} | Splits: ${totalSplits}`);
  log(`Profit: $${profit.toFixed(2)} | Longest LS: ${longestLossStreak} | Longest WS: ${longestWinStreak}`);
  log(`Final bet: $${currentBet.toFixed(4)} (${(currentBet / unit).toFixed(1)}x) | Balance: $${balance.toFixed(2)}`);
});
