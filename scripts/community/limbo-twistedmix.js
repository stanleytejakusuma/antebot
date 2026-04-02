strategyTitle = "TwistedMix";
version = "1.0.2";
author = "Vrafasky";
scripter = "Vrafasky";

game = "limbo";
startBalance = balance;

//USER CONFIG

// Combo setup
combo = [5, 5, 5]; // Put your target multiplier combo sequence here, separated by comma.

//Preroll Mode Setup
preroll = false; // True to enable preroll mode. False to disable
attemptsToPreroll = 125; //how many attempts you want to preroll before placing real bet size
prerollBetSize = minBetSize; //betsize during preroll. default is minBetSize, you could use 0 if you play on  Stake
stopOnPreroll = true; // Optional feature. set to true if you want to stop the script after the number of atemptsToPreroll is reach. This is useful if you want to continue play manually

// Bet Size increment setup
increaseMode = "auto"; // Options are "auto", "manual", or "everyX", (case sensitive) . Read the explanations below
/* =======================
         "auto" :  automatically calculate the divider and the percentage increase needed to recover your B2B combo multi target, based on the number of attempts  you want to cover (as defined by the coveredAttempts).

         "manual" : manually setting up divider and option to use auto-calculated or manual IOL percentage after every attempts

         "everyX" : flat betting and then increase the baseBet after every X of attempts. For example like double the betSize every 50 failed attempts

         YOU CAN CONFIGURE THE INCREASE SETUP for EACH MODE BELOW
    =========================*/

// auto - SETUP
coveredAttempts = 750; // This define how many attempts you want to cover. For example, if your set it to 3000, the script will calculate the initial bet size, divider , and increase % needed to cover 3000 attempts in chasing the combo.

// manual - SETUP
manualDivider = 5000; // This is the balance divider used to calculate starting bet size on manual Mode
autoIncreaseOnManualMode = false; // set this to true to use auto-calculated increaseOnLoss on manual mode, if false, set the value of manualOnLossIncreasePercent below
manualOnLossIncreasePercent = 0.81; // This represents the percentage amount to increase the bet size on loss. Set to 0 to use auto increase on loss.

// everyX - SETUP
everyXDivider = 5000; // This is the balance divider used to calculate starting bet size on everyX Mode
increaseEveryAttempts = 200; // This is how many attempts you want to flat betting before changing the baseBet, for example increase every 100 attempts, etc.
increasePercentage = 100; // the percentange

// Vaulting & Stop P/L Setup. Set 0 to disable
vaultProfitsThreshold = 0; //vaulting amount
stopOnProfit = 0; // stop if this profit reached
stopBeforeLoss = 0; // stop if next bet can go over this amount
stopOnLoss = 0; // stop if this loss exceeded.

// END OF USER CONFIG
// DO NOT EDIT BELOW THIS LINE

longestLS = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
comboMulti = combo.reduce(
  (accumulator, currentValue) => accumulator * currentValue,
  1,
);

if (increaseMode === "auto") {
  iol = calcIncrease(comboMulti);
  divider = Math.ceil(calcDivider(iol, coveredAttempts));
} else if (increaseMode === "manual") {
  divider = manualDivider;
  if (autoIncreaseOnManualMode) {
    iol = calcIncrease(comboMulti);
  } else {
    iol = 1 + manualOnLossIncreasePercent / 100;
  }
} else if (increaseMode === "everyX") {
  divider = everyXDivider;
  iol = 1 + increasePercentage / 100;
}

// Simulation Setup
if (isSimulationMode) {
  setSimulationBalance(Number(1000));
  resetSeed();
  resetStats();
  clearConsole();
}

startBalance = balance;
initialBaseBet = startBalance / divider;
if (preroll) {
  baseBet = prerollBetSize;
} else {
  baseBet = initialBaseBet;
}

betSize = baseBet;

target = combo[0];

ourStreak = 0;
totalComboWin = 0;

//vault init
lastVaultedProfit = profit;
startProfit = profit;

lossCount = 0;

function mainStrategy() {
  if (lastBet.win) {
    ourStreak++;
    betSize = lastBet.payout;

    if (ourStreak == combo.length) {
      ourStreak = 0;
      if (preroll) {
        baseBet = prerollBetSize;
      } else {
        baseBet = initialBaseBet;
      }
      betSize = baseBet;
      totalComboWin++;

      if (lossCount > Math.min(...longestLS)) {
        longestLS.push(lossCount);
        longestLS.sort((a, b) => b - a).splice(longestLS.length - 1, 1);
      }
      lossCount = 0;
    }

    target = combo[ourStreak];
  } else {
    ourStreak = 0;
    lossCount++;
    target = combo[0];
    if (increaseMode == "everyX") {
      if (increaseEveryAttempts && lossCount % increaseEveryAttempts == 0) {
        baseBet *= iol;
      }
    } else {
      baseBet *= iol;
    }

    if (preroll) {
      if (lossCount < attemptsToPreroll) {
        baseBet = minBetSize;
      } else if (lossCount == attemptsToPreroll) {
        baseBet = initialBaseBet;
        if (stopOnPreroll) {
          log(
            "#FD6868",
            `Script Stopped. Reaching ${attemptsToPreroll} Prerolling attempts.`,
          );
          engine.stop();
        }
      }
    }
    betSize = baseBet;
  }
}

engine.onBetPlaced(async (lastBet) => {
  scriptLog();
  stopProfitCheck();
  await vaultHandle();

  mainStrategy();

  stopLossCheck();
});

// Functions for auto calculating betSize/divider

function calcSum(r, t, s = 1) {
  return (s * (1 - Math.pow(r, t))) / (1 - r);
}

function calcIncrease(payout) {
  multi = 1 / (payout - 1) + 1;
  return multi;
}

function calcDivider(iol, maxStreak) {
  return calcSum(iol, maxStreak) + 1; // + 1 to get rid of balance rounding
}

function scriptLog() {
  clearConsole();
  logBanner();
  log(
    "#70FD70",
    increaseMode === "auto"
      ? `Increase Mode:
Auto-calculated to cover ${coveredAttempts} attempts with  ${(100 * (iol - 1)).toFixed(2)}% inc.`
      : increaseMode === "manual"
        ? `Increase Mode:
Manual mode set with ${manualDivider} divider` +
          (autoIncreaseOnManualMode
            ? ` and auto-calculated ${(100 * (iol - 1)).toFixed(2)}% IOL.`
            : ` and ${manualOnLossIncreasePercent}% IOL.`)
        : increaseMode === "everyX"
          ? `Increase Mode:
Increase by ${increasePercentage}% every ${increaseEveryAttempts} attempts`
          : "Increase Mode: Unknown",
  );
  log("#FD71FD", `🟢 Total Combo Hit: ${totalComboWin} times`);
  if (preroll) {
    log(
      "#FDBA68",
      `Preroll Mode: True. Prerolling ${attemptsToPreroll} attempts`,
    );
  }

  log("#A4FD68", `Current Attempts Count: ${lossCount + 1} attempts`);
  log(
    "#FFDB55",
    `B2B Combo Target Sequence:
${combo.join("x -> ")}x`,
  );
  log("#FF7D1F", `Total Combo B2B Multi Target: ${comboMulti}x`);
  log(
    "#42CAF7",
    `🎯 Longest attempts without Combo Hit:
${longestLS.join(" / ")}`,
  );
}

function logBanner() {
  log(
    "#2AFFCA",
    `================================
 🌀 ${strategyTitle} 🌀 by ${author}
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`,
  );
}

Number.prototype.dynFixed = function () {
  return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

function checkStopWithLog(
  condition,
  color,
  messagePrefix,
  amount,
  conditionMessage = "",
) {
  if (condition) {
    log(
      color,
      `${messagePrefix} ${amount.dynFixed()} ${currency.toUpperCase()} ${conditionMessage}`,
    );
    engine.stop();
  }
}

function stopProfitCheck() {
  checkStopWithLog(
    stopOnProfit && profit >= stopOnProfit,
    "#4FFB4F",
    "✅ Stopped on",
    profit,
    "Profit",
  );
}

function stopLossCheck() {
  potentialLoss = -(profit - betSize);

  checkStopWithLog(
    stopOnLoss !== 0 && profit < -Math.abs(stopOnLoss),
    "#FFFF2A",
    "⛔️ Stopped on loss of",
    -profit,
    "Loss",
  );
  checkStopWithLog(
    stopBeforeLoss !== 0 && profit - betSize <= -Math.abs(stopBeforeLoss),
    "#FFFF2A",
    "⛔️ Stopped to prevent a",
    potentialLoss,
    "Loss",
  );
}

async function vaultHandle() {
  if (
    vaultProfitsThreshold > 0 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;
    await depositToVault(vaultingAmount);
    log(
      `Vaulting ${vaultingAmount.toFixed(Math.max(-Math.floor(Math.log10(vaultingAmount)), 0) + 2)} ${currency}`,
    );
    lastVaultedProfit = profit;
  }
}
