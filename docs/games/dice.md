# Dice

> Source: https://forum.antebot.com/t/dice/762

## Variables

- `betSize`
Type: float
Required: true
- `target`
Type: float
Required: true
- `betHigh`
Type: boolean
Required: true

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 5,
  "nonce": 1027,
  "active": false,
  "game": "dice",
  "win": true,
  "amount": 1,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 2,
  "b2bMultiplier": 2,
  "payout": 2,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "result": 87.54,
    "target": 50.5,
    "multiplierTarget": 2,
    "condition": "above"
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Basic martingale example with stop on loss streak of 10

// resetStats();
// resetSeed();

game = 'dice';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
betHigh = true;
target = chanceToMultiplier(49.5);

engine.onBetPlaced(async (lastBet) => {
    if (currentStreak === -10) {
        log('Loss streak of 10 reached. Stopping...');
        engine.stop();
    }

    if (lastBet.win) {
        betSize = initialBetSize;
    } else {
        betSize *= 2;
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
