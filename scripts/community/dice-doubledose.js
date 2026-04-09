strategyTitle = 'DoubleDose';
author = 'captde.v';
version = '1.1';
scripter = 'ConnorMcLeod';

// simulation mode initial setting
if (isSimulationMode) {
    setSimulationBalance(1000);
    resetSeed();
    resetStats();
    clearConsole();
}

divider = 1000000
initialBetSize = balance / divider;
initialChance = 98; // win chance (you may want to edit min chance and max chance (max up to 99.99% on stake) at the end of edition area
initialBetHigh = false; // true or false

vaultProfitsThreshold = 0;

seedChangeAfterRolls = 0;
seedChangeAfterWins = 0;
seedChangeAfterLosses = 0;
seedChangeAfterWinStreak = 0;
seedChangeAfterLossStreak = 0;
stopOnResetSeedFailure = false; // if stake won't allow seed change, stop

forceRestart = false; // force restart on stake's errors

// stop on loss and stop on profit
// not needed if your conditions already has that feature
// you may feel it more userfriendly to use those variables though
stopOnProfit = balance * 0.2;
stopOnLoss = balance * 0.1; // this one can't be reached, will stop if next bet can go over the loss
stopOnReachedLoss = 0; // will only stop if reached (if async mode is false)

// restart script condition (will reset internal console stats, not main ones)
resetOnProfit = balance * 0.025; // restart strategy on profit (internal mini-session profit)
resetOnLoss = balance * 0.05; // restart strategy on loss (internal mini-session loss)
resetSeedOnReset = false; // if one of above variables triggers a restart, do we want to reset seed as well ?

// stats colors // you can pick some on https://encycolorpedia.com/
green = '#49b675';
red = '#d22d46';
white = '#f5f5f5';
bannerColor = '#49b675';
logStatsOnEveryRollsStreakOf = 1; // 0 to disable, else put the rolls period

// browser console command : JSON.parse(localStorage.getItem('strategies_saved')).find(strategy => strategy.label === 'Martingale')
strategy = {
    "label": "2x increase",
    "blocks": [{
            "id": "gFYUECbT",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 1,
                "betType": "lose",
                "profitType": "profit"
            },
            "do": {
                "type": "increaseByPercentage",
                "value": 200
            }
        },
        {
            "id": "YOkJsQlL",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 1,
                "betType": "win",
                "profitType": "profit"
            },
            "do": {
                "type": "resetWinChance",
                "value": 0
            }
        },
        {
            "id": "XCi0hBha",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 1,
                "betType": "win",
                "profitType": "profit"
            },
            "do": {
                "type": "resetAmount",
                "value": 0
            }
        },
        {
            "id": "dPo8ioII",
            "type": "bets",
            "on": {
                "type": "everyStreakOf",
                "value": 8,
                "betType": "win",
                "profitType": "profit"
            },
            "do": {
                "type": "switchOverUnder",
                "value": 0
            }
        },
        {
            "id": "7gVmk-h2",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 5,
                "betType": "bet",
                "profitType": "profit"
            },
            "do": {
                "type": "switchOverUnder",
                "value": 0
            }
        },
        {
            "id": "8KY5BsYs",
            "type": "bets",
            "on": {
                "type": "firstStreakOf",
                "value": 5,
                "betType": "win",
                "profitType": "profit"
            },
            "do": {
                "type": "setWinChance",
                "value": 25
            }
        },
        {
            "id": "hsGHwcGa",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 1,
                "betType": "lose",
                "profitType": "profit"
            },
            "do": {
                "type": "increaseWinChanceBy",
                "value": 5
            }
        },
        {
            "id": "zYKmprUP",
            "type": "bets",
            "on": {
                "type": "every",
                "value": 1,
                "betType": "win",
                "profitType": "profit"
            },
            "do": {
                "type": "decreaseWinChanceBy",
                "value": 2
            }
        }
    ],
    "isDefault": false
};

// resetStats(); // you may want to reset STATS on start
// resetSeed(); // you may want to reset SEED on start

const MIN_CHANCE = 0.01;
const MAX_CHANCE = 98.00;
// end of edition area
// end of edition area
// end of edition area
// end of edition area
game = 'dice';

function logBanner() {
    log('#80EE51', `================================
${strategyTitle} v${version} by ${author} 
================================
Scripted by ${scripter} for Antebot Originals
-------------------------------------------
`);
}

clearConsole();
logBanner();

betSize = initialBetSize;
chance = initialChance;
target = chanceToMultiplier(chance);
betHigh = initialBetHigh;

lastVaultedProfit = profit;
startProfit = profit;
startBalance = balance;
vaulting = false;
lastResetMsg = '';
totalResets = 0;

bStop = false;
bRunning = true;

Number.prototype.dynFixed = function() {
    return this.toFixed(Math.max(-Math.floor(Math.log10(this)), 0) + 2);
};

Number.prototype.toFiatString = function() {
    return (this * getConversionRate()).toLocaleString("en-US", {
        style: "currency",
        currency: "USD"
    });
};

function checkStopProfit() {
    if (stopOnProfit && profit >= stopOnProfit) {
        log(`Made ${profit.dynFixed()} ${currency} profit / ${profit.toFiatString()}`);
        stop();
    }
}

function checkStopLoss() {
    if (stopOnReachedLoss !== 0 && profit < -Math.abs(stopOnReachedLoss)) {
        log(`Lost ${(-profit).dynFixed()} ${currency} / ${(-profit).toFiatString()}`);
        stop();
    }
    if (stopOnLoss !== 0 && profit - betSize <= -Math.abs(stopOnLoss)) {
        log(`Stopped to prevent a ${(-(profit-betSize)).dynFixed()} ${currency} / ${(-(profit-betSize)).toFiatString()} loss`);
        stop();
    }
}

function checkVaultAllProfits() {
    if (!vaulting && vaultProfitsThreshold > 0 && profit - lastVaultedProfit >= vaultProfitsThreshold) {
        let vaultingAmount = profit - lastVaultedProfit;
        vaulting = true;
        depositToVault(vaultingAmount)
            .then(response => {
                log(`Vaulting ${vaultingAmount.dynFixed()} ${currency} / ${vaultingAmount.toFiatString()}`);
                lastVaultedProfit = profit;
            })
            .catch(response => {
                log(response[0].message);
            })
            .finally(() => {
                vaulting = false;
            });
    }
}

const resetseed = () => {
    // 'Finish existing games to change seed'
    // 'Please try again in an hour. '
    // 'Please try again in 39 minutes. '
    resetSeed()
        .then(response => {

        })
        .catch(response => {
            if (response[0].message.includes('Please try again in')) {
                if (response[0].message.includes('hour')) {
                    log('#ee3a1f', "Can't change seed before 1 hour");
                } else {
                    minutes = response[0].message.match(/\d+/)[0];
                    log('#ee3a1f', `Can't change seed before ${minutes} minutes`);
                }
            } else {
                log('#ee3a1f', response[0].message);
            }
            if (stopOnResetSeedFailure) {
                stop();
            }
        })
        .finally(() => {
            resettingSeed = false;
        });
};

function checkResetSeed() {
    if (seedChangeAfterRolls && rollNumber % seedChangeAfterRolls === 0) {
        resetseed();
    } else if (lastBet.win) {
        if (seedChangeAfterWins && wins % seedChangeAfterWins === 0) {
            resetseed();
        } else if (seedChangeAfterWinStreak && currentStreak % seedChangeAfterWinStreak === 0) {
            resetseed();
        }
    } else {
        if (seedChangeAfterLosses && losses % seedChangeAfterLosses === 0) {
            resetseed();
        } else if (seedChangeAfterLossStreak && currentStreak % seedChangeAfterLossStreak === 0) {
            resetseed();
        }
    }
}

function isMatching(conditionType, conditionsOn) {
    if (conditionType === 'bets') {
        variableToUse = 0;
        switch (conditionsOn.betType) {
            case 'bet':
                variableToUse = stats.rollNumber;
                break;
            case 'win':
                if (!lastBet.win) {
                    return false;
                }
                variableToUse = conditionsOn.type === 'every' ? stats.wins : stats.currentStreak;
                break;
            case 'lose':
                if (lastBet.win) {
                    return false;
                }
                variableToUse = conditionsOn.type === 'every' ? stats.losses : -stats.currentStreak;
                break;
            default:
                stop(`error in conditions, not recognized condition bet type ${conditionsOn.betType}`);
        }

        switch (conditionsOn.type) {
            case 'every':
                return !(variableToUse % conditionsOn.value);
            case 'everyStreakOf':
                return !(variableToUse % conditionsOn.value);
            case 'firstStreakOf':
                return variableToUse === conditionsOn.value;
            case 'streakGreaterThan':
                return variableToUse > conditionsOn.value;
            case 'streakLowerThan':
                return variableToUse < conditionsOn.value;
            default:
                stop(`error in conditions, not recognized condition on type ${conditionsOn.type}`);
        }
    } else // 'profit'
    {
        variableToUse = 0;
        switch (conditionsOn.profitType) {
            case 'balance':
                variableToUse = balance;
                break;
            case 'loss':
                variableToUse = -stats.profit;
                break;
            case 'profit':
                variableToUse = stats.profit;
                break;
            default:
                stop(`error in conditions, not recognized condition on profitType ${conditionsOn.profitType}`);
        }

        switch (conditionsOn.type) {
            case 'greaterThan':
                return variableToUse > conditionsOn.value;
            case 'greaterThanOrEqualTo':
                return variableToUse >= conditionsOn.value;
            case 'lowerThan':
                return variableToUse < conditionsOn.value;
            case 'lowerThanOrEqualTo':
                return variableToUse <= conditionsOn.value;
            default:
                stop(`error in conditions, not recognized condition on type ${conditionsOn.type}`);
        }
    }
}

function execute(doAction) {
    switch (doAction.type) {
        case 'increaseByPercentage':
            betSize *= 1 + doAction.value / 100;
            break;
        case 'decreaseByPercentage':
            betSize *= 1 - doAction.value / 100;
            break;
        case 'increaseWinChanceBy':
            chance *= 1 + doAction.value / 100;
            break;
        case 'decreaseWinChanceBy':
            chance *= 1 - doAction.value / 100;
            break;
        case 'addToAmount':
            betSize += doAction.value;
            break;
        case 'subtractFromAmount':
            betSize -= doAction.value;
            break;
        case 'addToWinChance':
            chance += doAction.value;
            break;
        case 'subtractFromWinChance':
            chance -= doAction.value;
            break;
        case 'setAmount':
            betSize = doAction.value;
            break;
        case 'setWinChance':
            chance = doAction.value;
            break;
        case 'switchOverUnder':
            betHigh = !betHigh;
            break;
        case 'resetAmount':
            betSize = initialBetSize;
            break;
        case 'resetWinChance':
            chance = initialChance;
            break;
        case 'stop':
            stop();
            break;
        default:
            stop(`error in conditions, not recognized action type ${doAction.type}`);
    }
}

stats = {
    rollNumber: 0,
    wins: 0,
    losses: 0,
    // win: false,
    currentStreak: 0,
    maxWinsStreak: 0,
    maxLossesStreak: 0,
    wagered: 0,
    rtp: 100,
    profit: 0,
    highestProfit: 0,
    lowestProfit: 0,
    colors: [red, white, green],
    //forceLog
    resetStats() {
        this.rollNumber = 0;
        this.wins = 0;
        this.losses = 0;
        // this.win = lastBet.win;
        this.currentStreak = 0;
        this.maxWinsStreak = 0;
        this.maxLossesStreak = 0;
        this.wagered = 0;
        this.rtp = 100;
        this.profit = 0;
        this.highestProfit = 0;
        this.lowestProfit = 0;
    },
    computeStats() {
        this.profit += lastBet.payout - lastBet.amount;
        this.highestProfit = Math.max(this.highestProfit, this.profit);
        this.lowestProfit = Math.min(this.lowestProfit, this.profit);
        this.rollNumber++;
        this.wagered += lastBet.amount;
        this.rtp = 100 + 100 * this.profit / this.wagered;
        // this.win = lastBet.win; // useless ?
        if (lastBet.win) {
            this.wins++;
            this.currentStreak = Math.max(1, ++this.currentStreak);
            this.maxWinsStreak = Math.max(this.currentStreak, this.maxWinsStreak);
        } else {
            this.losses++;
            this.currentStreak = Math.min(-1, --this.currentStreak);
            this.maxLossesStreak = Math.max(-this.currentStreak, this.maxLossesStreak);
        }
    },
    logStats() {
        log(this.colors[Math.sign(this.profit) + 1], `Profit: ${this.profit.toFixed(8)} / ${this.profit.toFiatString()}
RTP: ${this.rtp.toFixed(2)}%`);
        log(green, `Wins: ${this.wins}\t${Math.max(0, this.currentStreak)} / ${this.maxWinsStreak}`);
        log(red, `Wins: ${this.losses}\t${Math.max(0, -this.currentStreak)} / ${this.maxLossesStreak}`);
        log(white, `Highest: ${this.highestProfit.toFixed(8)} / ${this.highestProfit.toFiatString()} (${(this.highestProfit / startBalance * 100).toFixed(2)}%)
Lowest: ${this.lowestProfit.toFixed(8)} / ${this.lowestProfit.toFiatString()} (${(this.lowestProfit / startBalance * 100).toFixed(2)}%)
Wagered: ${this.wagered.toFixed(8)} / ${this.wagered.toFiatString()} (${(this.wagered / startBalance * 100).toFixed(2)}%)`);
        if (totalResets > 0) {
            log('#FFFF2A', `Resets: ${totalResets} | Last: ${lastResetMsg}`);
        }
    }
};

engine.onBetPlaced((lastBet) => {
    checkVaultAllProfits();
    checkResetSeed();

    stats.computeStats();

    for (let condition of strategy.blocks) {
        if (isMatching(condition.type, condition.on)) {
            execute(condition.do);
        }
    }

    chance = Math.min(Math.max(chance, MIN_CHANCE), MAX_CHANCE);
    target = chanceToMultiplier(chance);

    if ((resetOnProfit > 0 && stats.profit >= resetOnProfit) || (resetOnLoss > 0 && -stats.profit >= resetOnLoss)) {
        var resetReason = stats.profit >= 0 ? 'profit +' + stats.profit.toFixed(4) : 'loss ' + stats.profit.toFixed(4);
        totalResets++;
        lastResetMsg = 'Cycle #' + totalResets + ' ended (' + resetReason + ' ' + currency + ')';
        betSize = initialBetSize;
        chance = initialChance;
        target = chanceToMultiplier(chance);
        betHigh = initialBetHigh;
        stats.resetStats();
        if (logStatsOnEveryRollsStreakOf > 1) {
            clearConsole();
            logBanner();
            stats.logStats();
        }
        if (resetSeedOnReset) {
            resetseed();
        }
    }


    if (logStatsOnEveryRollsStreakOf > 0 && stats.rollNumber % logStatsOnEveryRollsStreakOf === 0) {
        clearConsole();
        logBanner();
        stats.logStats();
    }
    checkStopProfit();
    checkStopLoss();
});

function stop(logText = '') {
    if (logText.length) {
        log(logText);
    }
    bStop = true;
    engine.stop();
}

engine.onBettingStopped((isManualStop) => {
    if (forceRestart && !isManualStop && !bStop && betSize < balance) {
        notification('Forced restart');
        engine.start();
    } else {
        bRunning = false;
    }
});

conditionsString = {
    'on': {
        'bets': {
            'type': {
                'every': 'Every',
                'everyStreakOf': 'Every streak of',
                'firstStreakOf': 'First streak of',
                'streakGreaterThan': 'Streak greater than',
                'streakLowerThan': 'Streak lower than'
            },
            'betType': {
                'win': 'Wins',
                'lose': 'Losses',
                'bet': 'Bets'
            }
        },
        'profit': {
            'profitType': {
                'balance': 'Balance',
                'loss': 'Loss',
                'profit': 'Profit'
            },
            'type': {
                'greaterThan': 'Greater than',
                'greaterThanOrEqualTo': 'Greater than or equal to',
                'lowerThan': 'Lower than',
                'lowerThanOrEqualTo': 'Lower than or equal to'
            }
        }
    },
    'do': {
        'type': {
            'increaseByPercentage': 'Increase bet amount',
            'decreaseByPercentage': 'Decrease bet amount',
            'increaseWinChanceBy': 'Increase win chance',
            'decreaseWinChanceBy': 'Decrease win chance',
            'addToAmount': 'Add to bet amount',
            'subtractFromAmount': 'Subtract from bet amount',
            'addToWinChance': 'Add to win chance',
            'subtractFromWinChance': 'Subtract from win chance',
            'setAmount': 'Set bet amount',
            'setWinChance': 'Set win chance',
            'switchOverUnder': 'Switch over under',
            'resetAmount': 'Reset bet amount',
            'resetWinChance': 'Reset win chance',
            'stop': 'Stop autobet'
        }
    }
};

function logConditions() {
    conditions = [];
    strategy.blocks.forEach((condition, i) => {
        buffer = `Condition ${i+1}\n`;
        if (condition.type === 'bets') {
            buffer += `On ${conditionsString.on.bets.type[condition.on.type]} ${condition.on.value} ${conditionsString.on.bets.betType[condition.on.betType]}`;
        } else {
            buffer += `On ${conditionsString.on.profit.type[condition.on.type]} ${condition.on.value.toFixed(8)} ${currency} ${conditionsString.on.profit.profitType[condition.on.profitType]}`;
        }

        buffer += `\n > ${conditionsString.do.type[condition.do.type]}`;
        if (['addToAmount', 'subtractFromAmount', 'setAmount'].includes(condition.do.type)) {
            buffer += ` ${condition.do.value.toFixed(8)} ${currency}`;
        } else if (!['switchOverUnder', 'resetAmount', 'resetWinChance', 'stop'].includes(condition.do.type)) {
            buffer += ` ${condition.do.value.toFixed(2)} %`;
        }

        conditions.push(buffer);
    });

    if (bRunning) {
        alert(`\t${strategy.label}\n\n${conditions.join('\n\n')}\n\n!! CLIC OUTSIDE OF QBOT WINDOW IN ORDER TO BE ABLE TO USE CONSOLE AGAIN !!`);
    } else {
        log(`\t${strategy.label}\n\n${conditions.join('\n\n')}`);
    }
}
