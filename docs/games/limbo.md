# Limbo

> Source: https://forum.antebot.com/t/limbo/766

## Variables

- `betSize`
Type: float
Required: true
- `target`
Type: float
Required: true
Possible values: 1.00000000000001 - 1000000

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 8,
  "nonce": 1027,
  "active": false,
  "game": "limbo",
  "win": true,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 2,
  "b2bMultiplier": 2,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "result": 39.07902141536203,
    "multiplierTarget": 2,
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Increase target on loss, reset to initial target on win, static bet size

// resetStats();
// resetSeed();

game = 'limbo';
betSize = 0.00000000; // Bet size is always specified in crypto value, not USD!
initialBetSize = betSize;
target = 2;
initialTarget = target;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        target = initialTarget;
    } else {
        target += 1.05;
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
