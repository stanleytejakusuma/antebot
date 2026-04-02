strategyTitle = "Profit on Red/Black";
version = "1.3.0";
author = "Community";
scripter = "stanz";

game = "roulette";

// USER CONFIG — Edit this section
// ============================================================
//
//    Divider | Max LS | P(hitting it)
// ----------|--------|---------------
//        17 |   3    | 4.337%
//        60 |   4    | 1.524%
//       210 |   5    | 0.535%
//       735 |   6    | 0.188%
//     2,574 |   7    | 0.066%
//     9,008 |   8    | 0.023%
//    31,526 |   9    | 0.008%
//   110,342 |  10    | 0.003%
//   386,197 |  11    | 0.001%
// 1,351,688 |  12    | 0.0004%

divider = 110342;

increaseOnLossPercent = 250; // Increase bets by this % on loss. 250 = multiply by 3.5x
seedChangeAfterLossStreak = 5; // Reset seed after this many consecutive losses. 0 = disabled.

// Numbers with NO bet (uncovered). When these hit, you lose everything.
// Original profile: 0, 4, 9, 12, 13, 21, 25, 36
uncoveredNumbers = [0, 4, 9, 12, 13, 21, 25, 36];

// Numbers with SMALL bet. When these hit, payout is ~0.28x (partial loss).
// Original profile: 1, 16, 24, 31, 33
smallBetNumbers = [1, 16, 24, 31, 33];

// All other numbers (1-36 minus uncovered and small) get the BIG bet.
// When these hit, payout is ~1.44x (profit).
// Ratio between big and small bets. 5 = big bets are 5x the small bet.
bigToSmallRatio = 5;

// Vaulting & Stop P/L Setup. Set 0 to disable.
vaultProfitsThreshold = 100; // Vault profits when cumulative profit reaches this amount
stopOnProfit = 0; // Stop script at this profit. 0 = disabled.
stopOnLoss = 0; // Stop script at this loss. 0 = disabled.
stopBeforeLoss = 0; // Stop if next bet could exceed this loss. 0 = disabled.
stopAfterVaults = 0; // Stop after this many successful vaults. 0 = disabled.

// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

// Simulation Setup
if (isSimulationMode) {
  setSimulationBalance(1500);
  resetSeed();
  resetStats();
  clearConsole();
}

startBalance = balance;
iol = 1 + increaseOnLossPercent / 100;

// Build number lists
bigBetNumbers = [];
for (i = 1; i <= 36; i++) {
  if (uncoveredNumbers.indexOf(i) === -1 && smallBetNumbers.indexOf(i) === -1) {
    bigBetNumbers.push(i);
  }
}

coveredCount = bigBetNumbers.length + smallBetNumbers.length;

// Calculate bet amounts so total = balance / divider
// total = bigCount * (smallBet * ratio) + smallCount * smallBet
// total = smallBet * (bigCount * ratio + smallCount)
totalBetAmount = startBalance / divider;
smallBet = totalBetAmount / (bigBetNumbers.length * bigToSmallRatio + smallBetNumbers.length);
bigBet = smallBet * bigToSmallRatio;

// State
currentMultiplier = 1;
lossStreak = 0;
longestLossStreak = 0;
totalWins = 0;
totalLosses = 0;
lastVaultedProfit = profit;
stopped = false;

// Calculate max survivable loss streak
function calcMaxLossStreak() {
  let cumulative = 0;
  let bet = totalBetAmount;
  let streak = 0;
  while (cumulative + bet <= startBalance) {
    cumulative += bet;
    streak++;
    bet *= iol;
  }
  return streak;
}

maxSurvivableLosses = calcMaxLossStreak();

// Build the selection object
function buildSelection(multiplier) {
  let sel = {};

  for (let i = 0; i < bigBetNumbers.length; i++) {
    sel["number" + bigBetNumbers[i]] = bigBet * multiplier;
  }

  for (let i = 0; i < smallBetNumbers.length; i++) {
    sel["number" + smallBetNumbers[i]] = smallBet * multiplier;
  }

  // Uncovered numbers: not in selection = no bet
  return sel;
}

// Set initial selection
selection = buildSelection(1);

// Banner
function logBanner() {
  log(
    "#2AFFCA",
    `================================
 🎰 ${strategyTitle} v${version}
================================
 Adapted by ${scripter}
-------------------------------------------`
  );
}

function scriptLog() {
  clearConsole();
  logBanner();

  let currentTotal = totalBetAmount * currentMultiplier;
  log("#70FD70", `Balance: $${balance.toFixed(2)} | Divider: ${divider}`);
  log("#42CAF7", `Current Bet Total: $${currentTotal.toFixed(2)} | Multiplier: ${currentMultiplier.toFixed(2)}x`);
  log("#FFDB55", `Covered: ${coveredCount}/37 | Big: ${bigBetNumbers.length} (1.44x) | Small: ${smallBetNumbers.length} (0.28x) | Uncovered: ${uncoveredNumbers.length}`);
  log("#A4FD68", `W/L: ${totalWins}/${totalLosses} | Current LS: ${lossStreak} | Longest LS: ${longestLossStreak}`);
  log("#FD71FD", `Max Survivable LS: ${maxSurvivableLosses} | IOL: ${iol}x (${increaseOnLossPercent}%)`);

  if (vaultProfitsThreshold > 0) {
    log("#FF7D1F", `Vault Threshold: $${vaultProfitsThreshold} | Vaulted: $${vaulted.toFixed(2)}`);
  }
}

// Main strategy logic
function mainStrategy() {
  if (lastBet.win) {
    // Win = payout >= total bet (multiplier >= 1x). Big number hit.
    totalWins++;
    lossStreak = 0;
    currentMultiplier = 1;
    selection = buildSelection(1);
  } else {
    // Loss = payout < total bet. Small number or uncovered number hit.
    totalLosses++;
    lossStreak++;
    if (lossStreak > longestLossStreak) {
      longestLossStreak = lossStreak;
    }

    currentMultiplier *= iol;
    selection = buildSelection(currentMultiplier);

    if (seedChangeAfterLossStreak > 0 && lossStreak % seedChangeAfterLossStreak === 0) {
      resetSeed();
      log("#FFFF2A", `🔄 Seed reset after ${lossStreak} consecutive losses`);
    }
  }
}

// Vault handling — only vault when back at base (just won, not mid-streak)
async function vaultHandle() {
  if (
    vaultProfitsThreshold > 0 &&
    currentMultiplier === 1 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;
    await depositToVault(vaultingAmount);
    log("#4FFB4F", `💰 Vaulted $${vaultingAmount.toFixed(2)} | Total vaulted: $${vaulted.toFixed(2)}`);
    lastVaultedProfit = profit;

    // Recalculate bet sizes from current balance to maintain divider ratio
    let oldTotal = totalBetAmount;
    startBalance = balance;
    totalBetAmount = startBalance / divider;
    smallBet = totalBetAmount / (bigBetNumbers.length * bigToSmallRatio + smallBetNumbers.length);
    bigBet = smallBet * bigToSmallRatio;
    selection = buildSelection(1);
    maxSurvivableLosses = calcMaxLossStreak();
    log("#42CAF7", `📐 Rebased: $${oldTotal.toFixed(4)} → $${totalBetAmount.toFixed(4)} | Max LS: ${maxSurvivableLosses}`);

    // Walk-away after N vaults
    if (stopAfterVaults > 0 && vaultCount >= stopAfterVaults) {
      log("#4FFB4F", `🏁 Target reached: ${vaultCount} vaults ($${vaulted.toFixed(2)}). Stopping.`);
      stopped = true;
      engine.stop();
    }
  }
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
    let nextTotalBet = totalBetAmount * currentMultiplier;
    if (profit - nextTotalBet <= -Math.abs(stopBeforeLoss)) {
      log("#FD6868", `⛔ Stopped to prevent $${Math.abs(profit - nextTotalBet).toFixed(2)} Loss`);
      stopped = true;
      engine.stop();
    }
  }
}

// Init log
logBanner();
log("#70FD70", `Starting balance: $${startBalance.toFixed(2)}`);
log("#42CAF7", `Base bet total: $${totalBetAmount.toFixed(4)} | Small: $${smallBet.toFixed(4)} | Big: $${bigBet.toFixed(4)}`);
log("#FFDB55", `Big numbers (${bigBetNumbers.length}): [${bigBetNumbers.join(", ")}]`);
log("#FF7D1F", `Small numbers (${smallBetNumbers.length}): [${smallBetNumbers.join(", ")}]`);
log("#FD6868", `Uncovered (${uncoveredNumbers.length}): [${uncoveredNumbers.join(", ")}]`);
log("#FD71FD", `⚠️  Max survivable loss streak: ${maxSurvivableLosses} (before bankrupt)`);

// Main loop
engine.onBetPlaced(async () => {
  if (stopped) return;

  scriptLog();
  stopProfitCheck();
  await vaultHandle();

  mainStrategy();

  stopLossCheck();
});

engine.onBettingStopped((isManualStop) => {
  playHitSound();
  log(
    "#2AFFCA",
    `================================
 🎰 ${strategyTitle} — Session Over
================================`
  );
  log(`Spins: ${totalWins + totalLosses} | W/L: ${totalWins}/${totalLosses}`);
  log(`Profit: $${profit.toFixed(2)} | Longest LS: ${longestLossStreak}`);
  log(`Vaulted: $${vaulted.toFixed(2)} | Balance: $${balance.toFixed(2)}`);
});
