strategyTitle = "GoGo Gadgeto Rouletto ";
author = "Dandalf";
version = "1.0.0";
scripter = "009";

if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

game = "roulette";

divider = 20000;
initialBetSize = balance / divider;
initialBetSize = Math.max(initialBetSize, minBetSize);

increaseAtStreak = 2; // every x loss you add numberIncrease Fields to the bet
numberIncrease = 2; // how many fields you add per increase

vaultProfitsThreshold = 0; // vautling  threshold

// END OF EDITION ZONE
// DO NOT EDIT BELOW

startBalance = balance;
let highestBalance = startBalance;

lastVaultedProfit = profit;
startProfit = profit;

function console() {
  clearConsole();

  logBanner();
}

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

const plainNumbers = Array.from(Array(37).keys()).map((e) => "number" + e);

function rouletteGetRandomPlainNumbers(amount, bKeepCurrentSelection = false) {
  if (!bKeepCurrentSelection) {
    return shuffle(plainNumbers).slice(0, amount);
  }

  const currentNumbers = Object.keys(selection);
  return shuffle(plainNumbers.filter((e) => !currentNumbers.includes(e))).slice(
    0,
    amount,
  );
}

selection = {};
selection[rouletteGetRandomPlainNumbers(1)[0]] = initialBetSize;

individualBetSize = initialBetSize;

async function checkVaultAllProfits() {
  if (
    vaultProfitsThreshold > 0 &&
    profit - lastVaultedProfit >= vaultProfitsThreshold
  ) {
    let vaultingAmount = profit - lastVaultedProfit;

    await depositToVault(vaultingAmount);

    lastVaultedProfit = profit;
  }
}

engine.onBetPlaced(async (lastBet) => {
  await checkVaultAllProfits();
  await console();

  if (lastBet.win) {
    individualBetSize = initialBetSize;
    selection = {};
    selection[rouletteGetRandomPlainNumbers(1)[0]] = individualBetSize;
  } else {
    let numbersAmount = Object.keys(selection).length;
    if (currentStreak % increaseAtStreak === 0 && numbersAmount < 35) {
      const newNumber = rouletteGetRandomPlainNumbers(1, true);
      numbersAmount = numberIncrease;
      selection[newNumber] = individualBetSize;
    }

    const targetMultiplier = 36 / numbersAmount;
    const toRecover = highestProfit - profit;
    if (
      toRecover >
      individualBetSize * numbersAmount * (targetMultiplier - 1)
    ) {
      const betSize = toRecover / (targetMultiplier - 1);
      individualBetSize = betSize / numbersAmount;
      Object.keys(selection).forEach(
        (key) => (selection[key] = individualBetSize),
      );
    }
  }
});
