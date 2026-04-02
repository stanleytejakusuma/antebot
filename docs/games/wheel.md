# Wheel

> Source: https://forum.antebot.com/t/wheel/775

## Variables

- `betSize`
Type: float
Required: true
- `risk`
Type: string
Required: true
Possible values: low, medium, high
- `segments`
Type: integer
Required: true
Possible values: 10, 20, 30, 40, 50

## lastBet example
```json
{
  "id": "XXXX-XXXX-XXXX-XXXX-XXXX",
  "iid": "casino:888888888",
  "rollNumber": 12,
  "nonce": 1027,
  "game": "wheel",
  "win": false,
  "amount": 0,
  "fiatAmount": "$0.00",
  "payoutMultiplier": 0,
  "b2bMultiplier": 1,
  "payout": 0,
  "fiatPayout": "$0.00",
  "currency": "eth",
  "dateTime": "2022-05-01T00:00:00.000Z",
  "deepLink": "https://stake.com/?betId=XXXX-XXXX-XXXX-XXXX-XXXX&modal=bet",
  "state": {
    "result": 17,
    "segments": 50,
    "risk": "high"
  },
  "clientSeed": "yourClientSeed",
  "serverSeed": "XXX", // Simulation Mode only
  "serverSeedHashed": "XXX" // Live Mode only
}

```
## Code example
```javascript
// Hunt 49.5x with pre-rolls

// resetStats();
// resetSeed();

game = 'wheel';
betSize = 0;
baseBetSize = 0.00000001;
risk = 'high';
segments = 50;

engine.onBetPlaced(async (lastBet) => {
    if (lastBet.win) {
        betSize = 0;
    }
    
    if (!lastBet.win && betSize > 0) {
        betSize *= 1.0207;
    }
    
    if (currentStreak === -50) {
        log('Loss streak of 50 reached. Setting bet size...');
        
        betSize = baseBetSize;
    }
});

engine.onBettingStopped((isManualStop, lastError) => {
    playHitSound();
    log(`Betting stopped!`);
});

```
