strategyTitle = "Five-Stage Dice Strategy";
strategyAuthor = "wreckless6862";
scripter = "SuperX";
strategyVersion = "1.1";

/* ────────────────────────────────────────────────
   Simulation Settings
──────────────────────────────────────────────── */
if (isSimulationMode) {
  setSimulationBalance(100);
  resetSeed();
  resetStats();
  clearConsole();
}

/* ────────────────────────────────────────────────
   Core Strategy Configuration
──────────────────────────────────────────────── */
// Stage bet amount dividers
STAGE_1_BET_DIVIDER = 4000;
STAGE_2_BET_DIVIDER = 2000;
STAGE_3_BET_DIVIDER = 1000;
STAGE_4_BET_DIVIDER = 500;
STAGE_5_MARTINGALE_DIVIDER = 4000;

// Stage take profit dividers
STAGE_1_TP_DIVIDER = 500;
STAGE_2_TP_DIVIDER = 250;
STAGE_3_TP_DIVIDER = 125;
STAGE_4_TP_DIVIDER = 60;

// Stage stop loss dividers
STAGE_1_SL_DIVIDER = 250;
STAGE_2_SL_DIVIDER = 166.67;
STAGE_3_SL_DIVIDER = 80;
STAGE_4_SL_DIVIDER = 40;

// Win chance settings
WIN_CHANCE = 49.5;
TARGET_MULTIPLIER = 2.0;

// Martingale settings for Stage 5
MARTINGALE_MULTIPLIER = 2;
MAX_MARTINGALE_BETS = 20;

/* ────────────────────────────────────────────────
   Initialize Strategy State
──────────────────────────────────────────────── */
// Starting values - using current balance
let initialBalance = balance;
let currentStage = 1;
let stageBetAmount = initialBalance / STAGE_1_BET_DIVIDER;
let stageProfit = 0;
let stageLoss = 0;
let stageStartBalance = balance;
let targetProfit = initialBalance / STAGE_1_TP_DIVIDER;
let stopLoss = initialBalance / STAGE_1_SL_DIVIDER;
let martingaleCount = 0;
let totalLoss = 0;
let stageWins = 0;
let stageLosses = 0;

// Tracking variables for direct profit/loss calculation
let stageStartingBalance = balance;
let currentBalance = balance;

// Game settings
game = "dice";
betHigh = true;
betSize = stageBetAmount;
target = TARGET_MULTIPLIER;

/* ────────────────────────────────────────────────
   Main Logic & Event Handling
──────────────────────────────────────────────── */
engine.onBetPlaced(async (lastBet) => {
  // Calculate actual profit/loss since last bet
  currentBalance = balance;

  // Process bet result
  if (lastBet.win) {
    handleWin(lastBet);
  } else {
    handleLoss(lastBet);
  }

  // Update display
  displayStatus();
});

/* ────────────────────────────────────────────────
   Core Functions
──────────────────────────────────────────────── */
function handleWin(bet) {
  // Increment wins counter
  stageWins++;

  // Calculate profit dynamically
  stageProfit = Math.max(0, currentBalance - stageStartingBalance);

  // In Stage 5 (Martingale), reset bet size on win
  if (currentStage === 5) {
    martingaleCount = 0;
    betSize = initialBalance / STAGE_5_MARTINGALE_DIVIDER;

    // If we've recovered our losses plus a small profit, go back to Stage 1
    if (stageProfit >= totalLoss + initialBalance / 10000) {
      log("#4FFB4F", `✅ Stage 5 complete! Recovered losses plus profit.`);
      resetToStage1();
      return;
    }
  }

  // Check if we've hit the target profit for current stage
  if (currentStage < 5 && stageProfit >= targetProfit) {
    log(
      "#4FFB4F",
      `✅ Stage ${currentStage} profit target reached! Moving back to Stage 1.`,
    );
    resetToStage1();
  }
}

function handleLoss(bet) {
  // Increment losses counter
  stageLosses++;

  // Calculate loss directly from stage starting balance
  stageLoss = Math.max(0, stageStartingBalance - currentBalance);

  // Check if we need to move to the next stage (when stop loss is hit)
  if (currentStage < 5 && stageLoss >= stopLoss) {
    moveToNextStage();
    return;
  }

  // Handle Martingale progression in Stage 5
  if (currentStage === 5) {
    martingaleCount++;
    if (martingaleCount <= MAX_MARTINGALE_BETS) {
      // Increase bet using Martingale progression
      betSize = betSize * MARTINGALE_MULTIPLIER;
      log(
        "#FF9900",
        `🔄 Martingale: Increasing bet to ${formatAmount(betSize)} (step ${martingaleCount}/${MAX_MARTINGALE_BETS})`,
      );
    } else {
      // Safety reset if we hit max Martingale steps
      log("#FF6347", `⚠️ Reset Martingale: Max steps reached`);
      martingaleCount = 0;
      betSize = initialBalance / STAGE_5_MARTINGALE_DIVIDER;
    }
  }
}

function moveToNextStage() {
  currentStage++;
  totalLoss += stageLoss;

  log(
    "#FF9900",
    `⚠️ Stop loss hit (${formatAmount(stageLoss)}). Moving to Stage ${currentStage}`,
  );
  log("#FF6347", `💸 Total loss so far: ${formatAmount(totalLoss)}`);

  // Reset stage tracking variables
  stageStartingBalance = balance;
  stageProfit = 0;
  stageLoss = 0;
  stageWins = 0;
  stageLosses = 0;

  if (currentStage === 2) {
    stageBetAmount = initialBalance / STAGE_2_BET_DIVIDER;
    targetProfit = initialBalance / STAGE_2_TP_DIVIDER;
    stopLoss = initialBalance / STAGE_2_SL_DIVIDER;
  } else if (currentStage === 3) {
    stageBetAmount = initialBalance / STAGE_3_BET_DIVIDER;
    targetProfit = initialBalance / STAGE_3_TP_DIVIDER;
    stopLoss = initialBalance / STAGE_3_SL_DIVIDER;
  } else if (currentStage === 4) {
    stageBetAmount = initialBalance / STAGE_4_BET_DIVIDER;
    targetProfit = initialBalance / STAGE_4_TP_DIVIDER;
    stopLoss = initialBalance / STAGE_4_SL_DIVIDER;
  } else if (currentStage === 5) {
    // Start Martingale stage
    stageBetAmount = initialBalance / STAGE_5_MARTINGALE_DIVIDER;
    targetProfit = totalLoss + initialBalance / 10000; // Recover all losses plus tiny profit
    stopLoss = Infinity; // No stop loss in Martingale stage
    martingaleCount = 0;
  }

  betSize = stageBetAmount;

  log(
    "#FFFF2A",
    `🎯 Stage ${currentStage} started with bet ${formatAmount(betSize)}`,
  );
  log("#FFFF2A", `📈 Target profit: ${formatAmount(targetProfit)}`);
  if (currentStage < 5) {
    log("#FFFF2A", `🛑 Stop loss: ${formatAmount(stopLoss)}`);
  } else {
  }
}

function resetToStage1() {
  currentStage = 1;
  stageStartingBalance = balance;
  stageProfit = 0;
  stageLoss = 0;
  stageWins = 0;
  stageLosses = 0;
  totalLoss = 0;

  stageBetAmount = initialBalance / STAGE_1_BET_DIVIDER;
  targetProfit = initialBalance / STAGE_1_TP_DIVIDER;
  stopLoss = initialBalance / STAGE_1_SL_DIVIDER;

  betSize = stageBetAmount;

  log("#4FFB4F", `🔄 Strategy reset to Stage 1`);
  log("#FFFF2A", `🎯 Stage 1 started with bet ${formatAmount(betSize)}`);
  log("#FFFF2A", `📈 Target profit: ${formatAmount(targetProfit)}`);
  log("#FFFF2A", `🛑 Stop loss: ${formatAmount(stopLoss)}`);
}

/* ────────────────────────────────────────────────
   Display Functions
──────────────────────────────────────────────── */
function displayStatus() {
  clearConsole();
  logBanner();

  // Show current state
  stageNames = [
    "",
    "First Stage",
    "Second Stage",
    "Third Stage",
    "Fourth Stage",
    "Martingale Recovery",
  ];
  stageName = stageNames[currentStage] || `Stage ${currentStage}`;

  log("#FFFF2A", `⭐ Current: ${stageName}`);
  log("#96f58cff", `🎲 Bet amount: ${formatAmount(betSize)} ${currency}`);
  // Show progress with formatted values
  log(
    "#4FFB4F",
    `💰 Stage profit: ${formatAmount(stageProfit)} / ${formatAmount(targetProfit)} ${currency}`,
  );
  if (currentStage < 5) {
    log(
      "#FF6347",
      `⚠️ Stage loss: ${formatAmount(stageLoss)} / ${formatAmount(stopLoss)} ${currency}`,
    );
  }

  // Show overall profit
  profitPercent = isNaN((profit / initialBalance) * 100)
    ? "0.00"
    : ((profit / initialBalance) * 100).toFixed(2);
  log(
    profit >= 0 ? "#4FFB4F" : "#FF6347",
    `💰 Total profit: ${formatAmount(profit)} ${currency} (${profitPercent}%)`,
  );

  if (currentStage === 5) {
    log(
      "#FF9900",
      `🔄 Martingale step: ${martingaleCount}/${MAX_MARTINGALE_BETS}`,
    );
    log(
      "#FF6347",
      `💸 Trying to recover: ${formatAmount(totalLoss)} ${currency}`,
    );
  }
}

// Format currency amounts with appropriate precision
function formatAmount(amount) {
  if (isNaN(amount)) return "0.00";
  return Math.abs(amount) >= 1 ? amount.toFixed(2) : amount.toFixed(8);
}

// Display strategy banner
function logBanner() {
  log(
    "#80EE51",
    `================================
${strategyTitle} v${strategyVersion} by ${strategyAuthor}
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`,
  );
}