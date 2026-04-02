strategyTitle = "Mirage Limbo Wager";
author = "vrafasky";
version = "1.0";
scripter = "vrafasky";

game = "limbo";

// USER CONFIGURABLE SETTINGS

divider = 1000; // balance divider to calculate the base bet size. e.g. 1000 means base bet will be starting balance / 1000

stopOnFreeWageredMulti = 0; // Stop when this multiple of starting balance is wagered while the profit is above 0, so it's a "free wager".  Set 0 to disable

//game settings
wagerTarget = 1.0102; // Target multiplier on wager  phase
recoverTarget = 2; // Target multiplier on recovery phase

// DO NOT EDIT BELOW THIS LINE UNLESS YOU KNOW WHAT YOU ARE DOING
target = wagerTarget;

// Simulation Setup
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

initialBetSize = balance / divider;
betSize = initialBetSize;
sessionProfit = 0;
startBalance = balance;

engine.onBetPlaced(async (lastBet) => {
  sessionProfit += lastBet.payout - lastBet.amount;
  sessionProfitRatio = Math.abs(sessionProfit) / startBalance;

  if (sessionProfit >= 0) {
    if (lastBet.win) {
      if (lastBet.state.multiplierTarget == wagerTarget) {
        betSize = lastBet.payout;
      } else {
        betSize = initialBetSize;
      }
      if (currentStreak % 70 == 0) {
        sessionProfit = 0;
        betSize = initialBetSize;
      }
    } else {
      betSize = initialBetSize;
    }
    target = wagerTarget;
  } else {
    target = recoverTarget;
    betSize =
      initialBetSize +
      initialBetSize * Math.round((sessionProfitRatio * divider) / 50);
  }

  //stop on wagered
  if (
    stopOnFreeWageredMulti &&
    wagered >= stopOnFreeWageredMulti * startBalance &&
    sessionProfit > 0
  ) {
    log(
      "#f0e747ff",
      `✅ Stopped on ${stopOnFreeWageredMulti}x Starting Balance Wagered`,
    );
    engine.stop();
  }
});

logBanner();

function logBanner() {
  log(
    "#80EE51",
    `================================
${strategyTitle} v${version} by ${author}
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`,
  );
}