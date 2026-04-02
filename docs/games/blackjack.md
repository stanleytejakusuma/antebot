# Blackjack

> Source: https://forum.antebot.com/t/blackjack/757

## Variables

- `betSize`
Type: float
Required: true
- `sideBetPerfectPairs`
Type: float
Required: true
Note: Side bets are optional and not supported by every casino.
- `sideBet213`
Type: float
Required: true
Note: Side bets are optional and not supported by every casino.

## Functions

- `blackJackPerfectNextAction(currentBet, playerHandIndex, strategy = 'easy', double = 'any')`
Example: `blackJackPerfectNextAction(currentBet, playerHandIndex, 'easy', 'any');`
Returns the next action (see onGameRound return constants below), depending on the given parameters.
The following string parameters can be passed as strategy (3rd parameter):

- `easy`
- `simple`
- `advanced`
- `exactComposition`
- `bjc-supereasy`
- `bjc-simple`
- `bjc-great`

The following string parameters can be passed as doubling option (4th parameter):

- `none`
- `10or11`
- `9or10or11`
- `any`

Please find further information about how the strategies work here: [github.com/gsdriver/blackjack-strategy](https://github.com/gsdriver/blackjack-strategy)
- `blackJackBetMatrixNextAction(currentBet, playerHandIndex, betMatrix)`
Returns the next action (see onGameRound return constants below), depending on the given bet matrix.

The following commands are possible to set in the bet matrix values:

- `H` = Hit
- `S` = Stand
- `P` = Split
- `D` = Double or Hit
- `DS` = Double or Stand

The following code example shows the bet matrix for the perfect strategy:

```json
betMatrix = {
    "hard": {
        "4": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "5": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "6": {"2": "H", "3": "H","4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "7": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "8": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "9": {"2": "H", "3": "D", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "10": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "H", "A": "H"},
        "11": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "D", "A": "H"},
        "12": {"2": "H", "3": "H", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "13": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "14": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "15": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "16": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "17": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "18": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "19": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "20": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "21": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"}
    },
    "soft": {
        "12": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "13": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "14": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "15": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "16": {"2": "H", "3": "H", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "17": {"2": "H", "3": "D", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "18": {"2": "S", "3": "DS", "4": "DS", "5": "DS", "6": "DS", "7": "S", "8": "S", "9": "H", "10": "H", "A": "H"},
        "19": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "20": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "21": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"}
    },
    "splits": {
        "22": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "33": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "44": {"2": "H", "3": "H", "4": "H", "5": "P", "6": "P", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "55": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "H", "A": "H"},
        "66": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "77": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "88": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "P", "9": "P", "10": "P", "A": "P"},
        "99": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "S", "8": "P", "9": "P", "10": "S", "A": "S"},
        "1010": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "AA": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "P", "9": "P", "10": "P", "A": "P"}
    }
};

```

## onGameRound return constants

`BLACKJACK_DOUBLE`
Type: string
- `BLACKJACK_HIT`
Type: string
- `BLACKJACK_SPLIT`
Type: string
- `BLACKJACK_STAND`
Type: string

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 2,
  "nonce": 1027,
  "active": true,
  "game": "blackjack",
  "win": false,
  "amount": 1e-7,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 0,
  "b2bMultiplier": 0,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "player": [
      {
        "value": 17,
        "actions": ["deal"],
        "cards": [
          {"rank": "Q", "suit": "D"},
          {"rank": "7", "suit": "D"}
        ]
      }
    ],
    "dealer": [
      {
        "value": 10,
        "actions": ["deal"],
        "cards": [
          {"rank": "K", "suit": "D"}
        ]
      }
    ],
    "sideBetPerfectPairs": 0.00000001,
    "sideBetPerfectPairsWin": "PERFECT_PAIR",
    "sideBet213": 0.00000001,
    "sideBet213Win": "FLUSH"
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example for built-in strategies
```javascript
// Just plays Black Jack with the optimal strategy, doing martingale

// resetStats();
// resetSeed();

game = 'blackjack';
betSize = 0.00000001; // Bet size is always specified in crypto value, not USD!
sideBetPerfectPairs = 0.00000001; // Side bets are optional and are not supported by all casinos
sideBet213 = 0.00000001; // Side bets are optional and are not supported by all casinos
initialBetSize = betSize;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        if (lastBet.payoutMultiplier > 1) {
            // Only reset bet size, if we hit anything greater than 1x
            betSize = initialBetSize;
        }
    } else {
        betSize *= 2;
    }
});

engine.onGameRound((currentBet, playerHandIndex) => {
    const nextAction = blackJackPerfectNextAction(currentBet, playerHandIndex, 'easy', 'any');
    
    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    log(`Hand: ${playerHandIndex}: ${currentBet.state.player[playerHandIndex].value} vs. ${currentBet.state.dealer[0].value} -> ${nextAction}`);
    
    return nextAction;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
## Code example for bet matrix
```javascript
// Just plays Black Jack with the perfect strategy, doing martingale

// resetStats();
// resetSeed();

game = 'blackjack';
betSize = 0.00000001; // Bet size is always specified in crypto value, not USD!
sideBetPerfectPairs = 0.00000001; // Side bets are optional and are not supported by all casinos
sideBet213 = 0.00000001; // Side bets are optional and are not supported by all casinos
initialBetSize = betSize;

betMatrix = {
    "hard": {
        "4": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "5": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "6": {"2": "H", "3": "H","4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "7": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "8": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "H", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "9": {"2": "H", "3": "D", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "10": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "H", "A": "H"},
        "11": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "D", "A": "H"},
        "12": {"2": "H", "3": "H", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "13": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "14": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "15": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "16": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "17": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "18": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "19": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "20": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "21": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"}
    },
    "soft": {
        "12": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "13": {"2": "H", "3": "H", "4": "H", "5": "H", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "14": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "15": {"2": "H", "3": "H", "4": "H", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "16": {"2": "H", "3": "H", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "17": {"2": "H", "3": "D", "4": "D", "5": "D", "6": "D", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "18": {"2": "S", "3": "DS", "4": "DS", "5": "DS", "6": "DS", "7": "S", "8": "S", "9": "H", "10": "H", "A": "H"},
        "19": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "20": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "21": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"}
    },
    "splits": {
        "22": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "33": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "44": {"2": "H", "3": "H", "4": "H", "5": "P", "6": "P", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "55": {"2": "D", "3": "D", "4": "D", "5": "D", "6": "D", "7": "D", "8": "D", "9": "D", "10": "H", "A": "H"},
        "66": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "H", "8": "H", "9": "H", "10": "H", "A": "H"},
        "77": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "H", "9": "H", "10": "H", "A": "H"},
        "88": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "P", "9": "P", "10": "P", "A": "P"},
        "99": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "S", "8": "P", "9": "P", "10": "S", "A": "S"},
        "1010": {"2": "S", "3": "S", "4": "S", "5": "S", "6": "S", "7": "S", "8": "S", "9": "S", "10": "S", "A": "S"},
        "AA": {"2": "P", "3": "P", "4": "P", "5": "P", "6": "P", "7": "P", "8": "P", "9": "P", "10": "P", "A": "P"}
    }
};

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        if (lastBet.payoutMultiplier > 1) {
            // Only reset bet size, if we hit anything greater than 1x
            betSize = initialBetSize;
        }
    } else {
        betSize *= 2;
    }
});

engine.onGameRound((currentBet, playerHandIndex) => {
    const nextAction = blackJackBetMatrixNextAction(currentBet, playerHandIndex, betMatrix);
    
    if (nextAction === BLACKJACK_DOUBLE) {
        betSize *= 2;
    }

    log(`Hand: ${playerHandIndex}: ${currentBet.state.player[playerHandIndex].value} vs. ${currentBet.state.dealer[0].value} -> ${nextAction}`);
    
    return nextAction;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
