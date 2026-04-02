strategyTitle = "Roulette Fibo Profit ";
author = "Coomar";
version = "0.1";
scripter = "Coomar";

// simulation mode initial setting
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}
divider = 100000;
initialBetSize = balance / divider;
lastBetSize = 0;
betSize = initialBetSize;

game = "roulette";
targetColor = "row1";
selection = { row1: betSize };
asyncMode = false;

stopOnProfit = balance * 2; // set crypto amount for stop profit. I like to put it between 0.80ct$ - 1$.
stopOnLoss = balance * -0.5; // set crypto amount for stop profit. I like to put it between 0.80ct$ - 1$.

resetStats();

clearConsole();

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

// Event listener for bet outcomes
engine.onBetPlaced(async (lastBet) => {
  if (lastBet.win) {
    selection.row1 = initialBetSize;
    lastBetSize = 0;
  } else {
    selection.row1 = lastBet._amount + lastBetSize;
    lastBetSize = lastBet._amount;
  }

  clearConsole();
  logBanner();
  log(
    "#f625f4",
    ` =============
 Profit Target : ${stopOnProfit}$
 Stop Loss at : ${balance - stopOnLoss}$
 ===========================
`,
  );

  if (profit >= stopOnProfit) {
    log(`Finaly Reach Profit Target gg or qq :)`);
    engine.stop();
  } else if (profit <= stopOnLoss) {
    log(`Loose Sorry for That How much LS ? let me know :/`);
    engine.stop();
  } else {
    return;
  }
});
