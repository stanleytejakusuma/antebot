# Plinko

> Source: https://forum.antebot.com/t/plinko/768

## Variables

- `betSize`
Type: float
Required: true
- `risk`
Type: string
Required: true
Possible values: low, medium, high, expert (only on stake)
- `rows`
Type: integer
Required: true
Numbers in the range from 8 to 16.

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 10,
  "nonce": 1027,
  "active": false,
  "game": "plinko",
  "win": false,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 0.5,
  "b2bMultiplier": 0,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "risk": "medium",
    "rows": 16,
    "point": 405.12394637942276,
    "path": ["R", "R", "L", "L", "R", "L", "R", "R", "L", "L", "R", "L", "R", "R", "L", "R"]
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

game = 'plinko';
betSize = 0.00000000;
initialBetSize = betSize;
risk = 'medium';
rows = 16;

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
