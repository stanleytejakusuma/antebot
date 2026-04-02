# Roulette

> Source: https://forum.antebot.com/t/roulette/770

## Variables

- `selection`
Type: object
Required: true
Possible indexes: number0, number1, number2, number3, number4, number5, number6, number7, number8, number9, number10, number11, number12, number13, number14, number15, number16, number17, number18, number19, number20, number21, number22, number23, number24, number25, number26, number27, number28, number29, number30, number31, number32, number33, number34, number35, number36, row1 row2, row3, colorRed, colorBlack, parityEven, parityOdd, range0112, range1324, range2536, range0118, range1936

## Functions

- `rouletteNumberColor(number)`
Example: `numberColor = rouletteNumberColor(lastBet.state.result); // returns 'red', 'black' or 'green'`
Returns the color of a roulette number

## lastBet example
```json
{
  "id":"XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid":"casino:888888888",
  "rollNumber":10,
  "nonce":1027,
  "active": false,
  "game":"roulette",
  "win":false,
  "amount":0,
  "fiatAmount": "$0.00",
  "payoutMultiplier":0.5,
  "b2bMultiplier": 0,
  "payout":0,
  "fiatPayout": "$0.00",
  "currency":"eth",
  "dateTime":"2022-05-01T00:00:00.000Z",
  "deepLink":"https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state":{
    "result": 3,
    "numbers":[
      {"amount": 1e-8, "value": "number0"},
      {"amount": 1e-8, "value": "number1"},
      {"amount": 1e-8, "value": "number2"},
      {"amount": 1e-8, "value": "number3"},
      {"amount": 1e-8, "value": "number4"},
      {"amount": 1e-8, "value": "number5"},
      {"amount": 1e-8, "value": "number6"},
      {"amount": 1e-8, "value": "number7"},
      {"amount": 1e-8, "value": "number8"},
      {"amount": 1e-8, "value": "number9"},
      {"amount": 1e-8, "value": "number10"},
      {"amount": 1e-8, "value": "number11"},
      {"amount": 1e-8, "value": "number12"},
      {"amount": 1e-8, "value": "number13"},
      {"amount": 1e-8, "value": "number14"},
      {"amount": 1e-8, "value": "number15"},
      {"amount": 1e-8, "value": "number16"},
      {"amount": 1e-8, "value": "number17"},
      {"amount": 1e-8, "value": "number18"},
      {"amount": 1e-8, "value": "number19"},
      {"amount": 1e-8, "value": "number20"},
      {"amount": 1e-8, "value": "number21"},
      {"amount": 1e-8, "value": "number22"},
      {"amount": 1e-8, "value": "number23"},
      {"amount": 1e-8, "value": "number24"},
      {"amount": 1e-8, "value": "number25"},
      {"amount": 1e-8, "value": "number26"},
      {"amount": 1e-8, "value": "number27"},
      {"amount": 1e-8, "value": "number28"},
      {"amount": 1e-8, "value": "number29"},
      {"amount": 1e-8, "value": "number30"},
      {"amount": 1e-8, "value": "number31"},
      {"amount": 1e-8, "value": "number32"}
      {"amount": 1e-8, "value": "number33"}
      {"amount": 1e-8, "value": "number34"},
      {"amount": 1e-8, "value": "number35"},
      {"amount": 1e-8, "value": "number36"},
    ],
    "colors":[
      {"amount": 1e-8, "value": "colorRed"},
      {"amount": 1e-8, "value": "colorBlack"}
    ],
    "parities":[
      {"amount": 1e-8,"value": "parityEven"},
      {"amount": 1e-8, "value": "parityOdd"}
    ],
    "ranges":[
      {"amount": 1e-8, "value": "range0112"},
      {"amount": 1e-8, "value": "range1324"},
      {"amount": 1e-8, "value": "range2536"},
      {"amount": 1e-8, "value": "range0118"},
      {"amount": 1e-8, "value": "range1936"}
    ],
    "rows":[
      {"amount": 3.0000000000000004e-8 ,"value": "row1"}
      {"amount": 3.0000000000000004e-8 ,"value": "row2"}
      {"amount": 3.0000000000000004e-8 ,"value": "row3"}
    ]
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Simple martingale on number color

// resetStats();
// resetSeed();

game = 'roulette';
baseBet = 0.00000000;
targetColor = 'black';
selection = {'colorBlack': baseBet}

engine.onBetPlaced(async (lastBet) => {
    if (rouletteNumberColor(lastBet.state.result) !== targetColor) {
        selection.colorBlack *= 2;

        return;
    }

    selection.colorBlack = baseBet;
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
