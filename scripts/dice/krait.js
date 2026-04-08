// KRAIT v1.0 — Dual-Regime Dice Strategy
// 50% chance (+0.98x), delayed IOL → Martingale 3x, SL/TP exits.
// Two modes: PROFIT (IOL active) and REST (flat bets @95%, no IOL).
// Switches to REST on drawdown, back to PROFIT after cooldown.
//
// ARCHITECTURE: Unlike trail-based strategies (STRIKER, MAMBA), KRAIT uses
//   hard SL/TP exits. This allows longer sessions where regime switching
//   actually activates and provides protection. Trail kills sessions at
//   ~120 hands — too short for switching to matter.
//
// WHY DUAL-REGIME: At 50%, P(LS>=7) ≈ 86% over 500 rounds. Regime
//   switching reduces exposure: rest mode breaks deep chains, prevents
//   cascading Mart escalation near the SL boundary.
//
// Scorecard ($100, 10k sessions): G=-0.56%, Grade A, HL=124, 0% bust
//   Median: +$5.01, Win: 55%, ~229 bets/session
//
// Snake family: VIPER (BJ) / COBRA (Roulette) / MAMBA (Dice 65%) /
//   TAIPAN (Roulette v2) / SIDEWINDER (HiLo) / BASILISK (Baccarat) /
//   STRIKER (Dice 50%) / KRAIT (Dice dual-regime)

strategyTitle = "KRAIT";
version = "1.0.3";
author = "stanz";
scripter = "stanz";

game = "dice";

// USER CONFIG
// ============================================================
chance = 48;              // Profit mode: 48% chance, 1.0625x payout
profitDivider = 10000;    // Profit mode base bet = balance / profitDivider
wagerDivider = 30000;     // REST mode base bet = balance / wagerDivider (3x profit)
delay = 1;                // Absorb first N losses flat before Mart
martIOL = 3.0;            // Martingale multiplier per consecutive loss
betCapPct = 10;           // Max bet as % of balance
stopLossPct = 5;          // Hard SL: exit at -5% of starting balance
takeProfitPct = 10;       // Hard TP: exit at +10% of starting balance
restChance = 98;          // Rest mode: 98% chance, 0.0102x payout
ddTriggerPct = 3;         // Enter REST when profit drops 3% from entry
restDuration = 30;        // Stay in REST for N rounds, then back to PROFIT
// ============================================================
// DO NOT EDIT BELOW THIS LINE
// ============================================================

if (isSimulationMode) {
  setSimulationBalance(2000);
  resetSeed();
}

resetStats();
clearConsole();

// Computed
target = chanceToMultiplier(chance);
restTarget = chanceToMultiplier(restChance);
startBalance = balance;
profitBaseBet = startBalance / profitDivider;
if (profitBaseBet < 0.00101) profitBaseBet = 0.00101;
restBaseBet = startBalance / wagerDivider;
if (restBaseBet < 0.00101) restBaseBet = 0.00101;
stopLossAmt = startBalance * stopLossPct / 100;
takeProfitAmt = startBalance * takeProfitPct / 100;
ddTriggerAmt = startBalance * ddTriggerPct / 100;

betSize = profitBaseBet;
betHigh = true;

// State — IOL chain
currentMultiplier = 1;
inMart = false;
consecLosses = 0;
currentChainCost = 0;
delayHands = 0;
martHands = 0;

// State — regime
mode = "PROFIT";
restCounter = 0;
entryProfit = profit;
totalSwitches = 0;
restRounds = 0;
profitRounds = 0;
profitModeEntries = 1;
wagerModeEntries = 0;

// State — profit mode cycle stats
profitModesClosed = 0;
profitModeWins = 0;
profitModeLosses = 0;
profitModeBreakeven = 0;
bestProfitModePnl = 0;
worstProfitModePnl = 0;

// State — stats
lossStreak = 0;
winStreak = 0;
longestLossStreak = 0;
longestWinStreak = 0;
totalWins = 0;
totalLosses = 0;
betsPlayed = 0;
peakProfit = 0;
totalWagered = 0;
maxBetSeen = profitBaseBet;
recoveries = 0;
biggestRecovery = 0;
abandonedChains = 0;
stopped = false;
summaryPrinted = false;

// ============================================================
// HELPERS
// ============================================================

function resetChain() {
  if (currentChainCost > profitBaseBet * 2) abandonedChains++;
  currentMultiplier = 1;
  inMart = false;
  consecLosses = 0;
  currentChainCost = 0;
}

function closeProfitModeCycle() {
  cyclePnl = profit - entryProfit;
  profitModesClosed++;
  if (profitModesClosed === 1) {
    bestProfitModePnl = cyclePnl;
    worstProfitModePnl = cyclePnl;
  } else {
    if (cyclePnl > bestProfitModePnl) bestProfitModePnl = cyclePnl;
    if (cyclePnl < worstProfitModePnl) worstProfitModePnl = cyclePnl;
  }
  if (cyclePnl > 0) profitModeWins++;
  else if (cyclePnl < 0) profitModeLosses++;
  else profitModeBreakeven++;
}

function switchMode(newMode) {
  if (mode === newMode) return;
  if (mode === "PROFIT" && newMode === "REST") {
    closeProfitModeCycle();
  }
  mode = newMode;
  totalSwitches++;
  resetChain();
  if (newMode === "PROFIT") {
    profitModeEntries++;
    entryProfit = profit;
    target = chanceToMultiplier(chance);
  } else {
    wagerModeEntries++;
    target = chanceToMultiplier(restChance);
    restCounter = restDuration;
  }
}

// ============================================================
// STRATEGY
// ============================================================

function mainStrategy() {
  betsPlayed++;
  totalWagered += lastBet.amount;

  if (mode === "REST") restRounds++;
  else profitRounds++;

  if (lastBet.win) {
    totalWins++;
    winStreak++;
    lossStreak = 0;
    if (winStreak > longestWinStreak) longestWinStreak = winStreak;

    if (mode === "PROFIT") {
      recoveryAmt = lastBet.amount;
      if (recoveryAmt > biggestRecovery) biggestRecovery = recoveryAmt;
      if (currentChainCost > 0) recoveries++;
      resetChain();
    }

    if (mode === "PROFIT") betSize = profitBaseBet;
    else betSize = restBaseBet;
  } else {
    totalLosses++;
    lossStreak++;
    winStreak = 0;
    if (lossStreak > longestLossStreak) longestLossStreak = lossStreak;

    if (mode === "PROFIT") {
      currentChainCost += lastBet.amount;
      consecLosses++;

      if (consecLosses <= delay) {
        // Delayed IOL: absorb flat
        currentMultiplier = 1;
        delayHands++;
      } else {
        if (!inMart) {
          inMart = true;
          currentMultiplier = 1;
        } else {
          currentMultiplier *= martIOL;
        }
        martHands++;

        // Soft bust
        nextBet = profitBaseBet * currentMultiplier;
        if (nextBet > balance * 0.95) {
          resetChain();
        }
      }

      betSize = profitBaseBet * currentMultiplier;
    } else {
      // REST mode: flat bets always
      betSize = restBaseBet;
    }
  }

  // Bet cap
  if (betCapPct > 0) {
    maxBetAllowed = balance * betCapPct / 100;
    if (betSize > maxBetAllowed) betSize = maxBetAllowed;
  }

  // SL-aware bet cap: prevent single bet from overshooting SL floor
  if (stopLossPct > 0) {
    slCushion = profit + stopLossAmt;
    if (slCushion >= 0 && betSize >= slCushion) betSize = slCushion;
  }

  if (betSize < 0.00101) betSize = 0.00101;
  if (betSize > maxBetSeen) maxBetSeen = betSize;
  if (profit > peakProfit) peakProfit = profit;
}

// ============================================================
// LOGGING
// ============================================================

function scriptLog() {
  clearConsole();

  modeColor = mode === "PROFIT" ? "#FF4500" : "#42CAF7";
  modeTag = mode === "PROFIT" ? "PROFIT" : "REST (" + restCounter + " left)";

  log(modeColor,
    "================================\n KRAIT v" + version + " [" + modeTag + "]" +
    "\n================================\n " + chance + "% dice | delay=" + delay +
    " mart=" + martIOL + "x | SL=" + stopLossPct + "% TP=" + takeProfitPct +
    "% | DD=" + ddTriggerPct + "% r=" + restDuration
  );

  if (mode === "PROFIT") {
    phase = inMart ? "MART " + currentMultiplier.toFixed(0) + "x" : "FLAT";
  } else {
    phase = "REST @" + restChance + "%";
  }
  pctPnL = (profit / startBalance * 100).toFixed(1);

  log(modeColor, "$" + balance.toFixed(2) + " | Bet: $" + betSize.toFixed(4) + " | " + phase);
  log("#4FFB4F", "P&L: $" + profit.toFixed(2) + " (" + pctPnL + "%) | Peak: $" + peakProfit.toFixed(2));

  // SL/TP distance
  if (stopLossPct > 0) slDist = "$" + (profit + stopLossAmt).toFixed(2) + " away";
  else slDist = "disabled";
  if (takeProfitPct > 0) tpDist = "$" + (takeProfitAmt - profit).toFixed(2) + " away";
  else tpDist = "disabled";
  log("#FFD700", "SL: " + slDist + " | TP: " + tpDist);

  profPct = betsPlayed > 0 ? (profitRounds / betsPlayed * 100).toFixed(0) : "100";
  pmWinRate = profitModesClosed > 0 ? (profitModeWins / profitModesClosed * 100).toFixed(1) : "0.0";
  log("#FFDB55", "W/L: " + totalWins + "/" + totalLosses +
    " | Bets: " + betsPlayed + " (" + profPct + "% profit, " + (100 - profPct) + "% rest)" +
    " | Sw: " + totalSwitches);
  log("#8B949E", "Mode entries -> Profit: " + profitModeEntries + " | Wager(REST): " + wagerModeEntries);
  log("#8B949E", "Profit mode -> Win rate: " + pmWinRate + "% (" + profitModeWins + "/" + profitModesClosed + ")" +
    " | L: " + profitModeLosses + " | BE: " + profitModeBreakeven);
}

// ============================================================
// INIT & MAIN LOOP
// ============================================================

log("#FF4500", "KRAIT v" + version + " | " + chance + "% dice | $" + profitBaseBet.toFixed(4) + " base (profit)");
log("#FF4500", "REST base: $" + restBaseBet.toFixed(4) + " | Dividers P/R: " + profitDivider + "/" + wagerDivider);
if (stopLossPct > 0 && takeProfitPct > 0) log("#FF4500", "SL=" + stopLossPct + "% ($" + stopLossAmt.toFixed(2) + ") | TP=" + takeProfitPct + "% ($" + takeProfitAmt.toFixed(2) + ")");
else if (stopLossPct > 0) log("#FF4500", "SL=" + stopLossPct + "% ($" + stopLossAmt.toFixed(2) + ") | TP=disabled");
else if (takeProfitPct > 0) log("#FF4500", "SL=disabled | TP=" + takeProfitPct + "% ($" + takeProfitAmt.toFixed(2) + ")");
else log("#FF4500", "SL=disabled | TP=disabled");
log("#42CAF7", "Delay " + delay + " → Mart " + martIOL + "x | DD=" + ddTriggerPct + "% r=" + restDuration + " @" + restChance + "%");
log("#42CAF7", "Bet cap: " + betCapPct + "% | Casino: " + casino);

engine.onBetPlaced(function () {
  if (stopped) return;

  mainStrategy();
  scriptLog();

  // === EXITS: SL / TP ===
  if (stopLossPct > 0 && profit <= -stopLossAmt) {
    stopped = true;
    playHitSound();
    logSummary("STOP LOSS");
    engine.stop();
    return;
  }
  if (takeProfitPct > 0 && profit >= takeProfitAmt) {
    stopped = true;
    playHitSound();
    logSummary("TAKE PROFIT");
    engine.stop();
    return;
  }

  // === REGIME SWITCHING ===
  if (mode === "PROFIT") {
    dd = entryProfit - profit;
    if (dd >= ddTriggerAmt) {
      switchMode("REST");
    }
  } else {
    restCounter--;
    if (restCounter <= 0) {
      switchMode("PROFIT");
    }
  }
});

// ============================================================
// SUMMARY
// ============================================================

function logSummary(exitType) {
  if (summaryPrinted) return;
  summaryPrinted = true;
  if (mode === "PROFIT") {
    closeProfitModeCycle();
  }
  playHitSound();
  clearConsole();
  pctPnL = (profit / startBalance * 100).toFixed(1);
  rtpFinal = totalWagered > 0 ? ((totalWagered + profit) / totalWagered * 100).toFixed(2) : "100.00";
  profPct = betsPlayed > 0 ? (profitRounds / betsPlayed * 100).toFixed(0) : "100";
  pmWinRate = profitModesClosed > 0 ? (profitModeWins / profitModesClosed * 100).toFixed(1) : "0.0";

  exitColor = profit >= 0 ? "#4FFB4F" : "#FF4500";
  log(
    exitColor,
    "================================\n KRAIT v" + version + " — " + exitType +
    "\n================================"
  );
  log(exitColor, "P&L: $" + profit.toFixed(2) + " (" + pctPnL + "%) | Balance: $" + balance.toFixed(2));
  log("Bets: " + betsPlayed + " | W/L: " + totalWins + "/" + totalLosses);
  log("Peak: $" + peakProfit.toFixed(2) + " | RTP: " + rtpFinal + "%");
  log("Wagered: $" + totalWagered.toFixed(2) + " (" + (totalWagered / startBalance).toFixed(1) + "x)");
  log("Max LS: " + longestLossStreak + " | Max WS: " + longestWinStreak);
  log("Max Bet: $" + maxBetSeen.toFixed(4) + " | Best Recovery: $" + biggestRecovery.toFixed(4) + " | Recoveries: " + recoveries);
  log("#8B949E", "Regime: " + profPct + "% profit / " + (100 - profPct) + "% rest | Switches: " + totalSwitches + " | Abandoned: " + abandonedChains);
  log("#8B949E", "Entries: Profit " + profitModeEntries + " | Wager(REST) " + wagerModeEntries);
  log("#8B949E", "Profit mode WR: " + pmWinRate + "% (" + profitModeWins + "/" + profitModesClosed + ")" +
    " | Loss: " + profitModeLosses + " | BE: " + profitModeBreakeven);
  if (profitModesClosed > 0) {
    log("#8B949E", "Profit mode PnL range: best $" + bestProfitModePnl.toFixed(2) + " | worst $" + worstProfitModePnl.toFixed(2));
  }
  log("#8B949E", "Delay: " + delayHands + " hands | Mart: " + martHands + " hands");
  if (exitType === "STOP LOSS") {
    log("#FF4500", "SL hit at $" + profit.toFixed(2) + " (limit: -$" + stopLossAmt.toFixed(2) + ")");
  } else if (exitType === "TAKE PROFIT") {
    log("#4FFB4F", "TP hit at $" + profit.toFixed(2) + " (target: +$" + takeProfitAmt.toFixed(2) + ")");
  }
}

engine.onBettingStopped(function () {
  if (stopped) return;
  logSummary("MANUAL STOP");
});
