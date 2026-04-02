# Baccarat

> Source: https://forum.antebot.com/t/baccarat/756

## Variables

- `bankerBetSize`
Type: float
Required: true
- `playerBetSize`
Type: float
Required: true
- `tieBetSize`
Type: float
Required: true

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 2,
  "nonce": 1027,
  "active": false,
  "game": "baccarat",
  "win": true,
  "amount": 1e-7,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 2,
  "b2bMultiplier": 2,
  "payout": 2e-7,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "playerCards": [
      {"suit": "D", "rank": "Q"},
      {"suit": "C", "rank": "5"},
      {"suit": "C", "rank": "9"}
    ],
    "bankerCards": [
      {"suit": "S", "rank": "J"},
      {"suit": "D", "rank": "3"},
      {"suit": "S", "rank": "8"}
    ],
    "tie": 0,
    "player": 1e-7,
    "banker": 0,
    "result": "player"
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Fibonnaci sequence betting

// resetStats();
// resetSeed();

game = 'baccarat';
bankerBetSize = 0.00000000;
playerBetSize = 0.00000010;
tieBetSize = 0.00000000;
initialPlayerBetSize = playerBetSize;
fibonacciSequence = [
    1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377,
    610, 987, 1597, 2584, 4181, 6765, 10946, 17711,
    28657, 46368, 75025, 121393, 196418, 317811
];

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        playerBetSize = initialPlayerBetSize;
    } else {
        playerBetSize = initialPlayerBetSize * fibonacciSequence[Math.abs(currentStreak)];
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
