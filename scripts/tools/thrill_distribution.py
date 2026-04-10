#!/usr/bin/env python3
"""Thrill Provably Fair — Dice vs Limbo Distribution Visualization (Pass 3).

Algorithm (cracked & verified):
  HMAC-SHA512(server_seed, "clientSeed:nonce:cursor")
  Walk hash in 4-byte LE uint32 chunks, rejection sampling.

Dice:  (value % 10001) / 100  → uniform [0.00, 100.00]
Limbo: float generation (7 bytes → 52-bit mask → /2^52), then 99/float/100
"""
import hmac, hashlib, struct
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ======================================================================
# Thrill PF engine
# ======================================================================

def thrill_hash(server, client, nonce, cursor=0):
    msg = client + ':' + str(nonce) + ':' + str(cursor)
    return hmac.new(server.encode(), msg.encode(), hashlib.sha512).digest()

def thrill_dice(server, client, nonce):
    MAX_U32 = 2**32
    limit = MAX_U32 - (MAX_U32 % 10001)
    cursor = 0
    while True:
        h = thrill_hash(server, client, nonce, cursor)
        for i in range(0, len(h) - 3, 4):
            val = struct.unpack('<I', h[i:i+4])[0]
            if val < limit:
                return (val % 10001) / 100.0
        cursor += 1

def thrill_float(server, client, nonce, cursor=0):
    h = thrill_hash(server, client, nonce, cursor)
    bits = 0
    for b in h[:7]:
        bits = (bits << 8) | b
    masked = bits & ((1 << 52) - 1)
    return masked / (2**52)

def thrill_limbo(server, client, nonce):
    f = thrill_float(server, client, nonce)
    if f == 0:
        return 1000000.0
    raw = 99.0 / f
    result = int(raw) / 100.0
    return max(result, 1.0)

# ======================================================================
# Generate samples
# ======================================================================

seeds = [
    ('CBIC5dZiNgyT499Y9UqN4J2FRvZUJ2V7biODt5chBtuEr51TKxAh3YfPK5HA9kZ0',
     'fmHwFrieHNZlKdZz'),
    ('01fNefjLlUVA1JVlqSnhb9wHS00KDZ845jmCFJDXNs5tiEqK4r6ko1GLVeHUCliQ',
     '5sFKlsaEiUfiWiD6'),
    ('JL95v6BwHWuMRVrVUI3pp30VKFjbeqf6lTcst2IOdTpiAEpQNxtV99ZeokOHXnlD',
     'sNhNp8PiN3a4IgVc'),
]

N = 10000
print(f"Generating {N} results across {len(seeds)} seed pairs...")

dice_results, limbo_results = [], []
nonce = 0
for server, client in seeds:
    for i in range(N // len(seeds)):
        nonce += 1
        dice_results.append(thrill_dice(server, client, nonce))
        limbo_results.append(thrill_limbo(server, client, nonce))

dice_arr = np.array(dice_results)
limbo_arr = np.array(limbo_results)
med_limbo = np.median(limbo_arr)

print(f"Dice:  mean={dice_arr.mean():.2f}  std={dice_arr.std():.2f}")
print(f"Limbo: median={med_limbo:.2f}  P(>=2x)={np.sum(limbo_arr>=2)/len(limbo_arr)*100:.1f}%")

# ======================================================================
# Colors
# ======================================================================

BG       = '#0d1117'
PANEL    = '#161b22'
DICE_C   = '#58a6ff'
LIMBO_C  = '#f97583'
GOLD     = '#e3b341'
GREEN    = '#3fb950'
MUTED    = '#8b949e'
TEXT     = '#c9d1d9'
GRID     = '#21262d'
WHITE    = '#f0f6fc'

def style_ax(ax, title=''):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(True, alpha=0.12, color=MUTED, linewidth=0.5)
    if title:
        ax.set_title(title, fontsize=12, fontweight='bold', color=WHITE,
                     pad=10, fontfamily='monospace')

# ======================================================================
# Layout: 5 panels
# ======================================================================

fig = plt.figure(figsize=(18, 22), facecolor=BG)
gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.22,
                      left=0.06, right=0.96, top=0.93, bottom=0.03,
                      height_ratios=[1, 1, 0.15, 1.2])

# --- Header ---
fig.text(0.5, 0.975, 'DICE   vs   LIMBO',
         ha='center', fontsize=30, fontweight='bold', color=WHITE, fontfamily='monospace')
fig.text(0.5, 0.955, 'Thrill Provably Fair  |  HMAC-SHA512  |  '
         f'{N:,} samples  |  3 verified seed pairs',
         ha='center', fontsize=11, color=MUTED, fontfamily='monospace')

# ==========================
# ROW 1: Histograms
# ==========================

# --- 1A: Dice ---
ax1 = fig.add_subplot(gs[0, 0])
style_ax(ax1, 'DICE — Outcome Distribution')

ax1.hist(dice_arr, bins=50, color=DICE_C, alpha=0.75, edgecolor=PANEL, linewidth=0.5)
expected_per_bin = N / 50
ax1.axhline(y=expected_per_bin, color=GOLD, linestyle='--', alpha=0.5, linewidth=1)
ax1.set_xlabel('Dice Result (0 – 100)')
ax1.set_ylabel('Frequency')
ax1.set_xlim(0, 100)

ax1.text(0.5, 0.93,
         f'Uniform distribution  |  mean {dice_arr.mean():.1f}  |  std {dice_arr.std():.1f}',
         transform=ax1.transAxes, ha='center', fontsize=9, color=MUTED,
         fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.4', facecolor=BG, edgecolor=GRID))

# Label the expected line
ax1.text(2, expected_per_bin + 8, f'expected: {expected_per_bin:.0f}/bin',
         fontsize=8, color=GOLD, fontfamily='monospace')

# --- 1B: Limbo ---
ax2 = fig.add_subplot(gs[0, 1])
style_ax(ax2, 'LIMBO — Multiplier Distribution')

# Separate dead zone (<1.01x) from playable zone
bins_dead = np.arange(1.0, 1.01 + 0.001, 0.1)  # single bin for 1.0-1.1
bins_play = np.arange(1.1, 12.1, 0.1)
all_bins = np.arange(1.0, 12.1, 0.1)

limbo_cap = limbo_arr[limbo_arr <= 12]

# Plot all bins first in limbo color
counts, bin_edges, patches = ax2.hist(limbo_cap, bins=all_bins, color=LIMBO_C, alpha=0.75,
                                       edgecolor=PANEL, linewidth=0.3)

# Color the first bin (1.0-1.1) red — contains the 1.00x dead zone
RED_DEAD = '#da3633'
patches[0].set_facecolor(RED_DEAD)
patches[0].set_alpha(0.9)

# Dead zone shading and label
ax2.axvspan(1.0, 1.01, alpha=0.25, color=RED_DEAD, zorder=2)
ax2.axvline(x=1.01, color=RED_DEAD, linestyle='-', linewidth=1.5, alpha=0.8, zorder=4)

# Count results in dead zone
dead_count = np.sum(limbo_arr < 1.01)
dead_pct = dead_count / len(limbo_arr) * 100
ax2.annotate(f'DEAD ZONE\n<1.01x = loss\n{dead_pct:.1f}% of results',
             xy=(1.01, counts[0] * 0.7),
             xytext=(3.5, counts[0] * 0.85),
             fontsize=9, color=RED_DEAD, fontfamily='monospace', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=RED_DEAD, lw=1.5),
             bbox=dict(boxstyle='round,pad=0.3', facecolor=BG, edgecolor=RED_DEAD, alpha=0.9))

ax2.set_xlabel('Multiplier Result')
ax2.set_ylabel('Frequency')
ax2.set_xlim(1.0, 12)

# Median + 2x lines
ax2.axvline(x=med_limbo, color=GOLD, linestyle='--', alpha=0.7, linewidth=1.2)
ax2.axvline(x=2.0, color=DICE_C, linestyle=':', alpha=0.4, linewidth=1)

# Stats
pct2 = np.sum(limbo_arr >= 2) / len(limbo_arr) * 100
pct5 = np.sum(limbo_arr >= 5) / len(limbo_arr) * 100
pct10 = np.sum(limbo_arr >= 10) / len(limbo_arr) * 100
ax2.text(0.97, 0.93,
         f'median {med_limbo:.2f}x  |  P(>=2x) {pct2:.0f}%  |  P(>=5x) {pct5:.0f}%  |  P(>=10x) {pct10:.0f}%',
         transform=ax2.transAxes, ha='right', fontsize=9, color=MUTED,
         fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.4', facecolor=BG, edgecolor=GRID))

# Annotate median
ax2.annotate(f'median\n{med_limbo:.2f}x', xy=(med_limbo, counts[0] * 0.45),
             xytext=(med_limbo + 2.5, counts[0] * 0.5),
             fontsize=9, color=GOLD, fontfamily='monospace', fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=GOLD, lw=1.2))

# ==========================
# ROW 2: Verification plots
# ==========================

# --- 2A: Dice CDF ---
ax3 = fig.add_subplot(gs[1, 0])
style_ax(ax3, 'DICE — CDF Verification')

dice_sorted = np.sort(dice_arr)
dice_cdf = np.arange(1, len(dice_sorted)+1) / len(dice_sorted) * 100
ax3.plot(dice_sorted, dice_cdf, color=DICE_C, linewidth=2, label='Empirical', zorder=3)
ax3.plot([0, 100], [0, 100], color=GOLD, linestyle='--', alpha=0.4,
         linewidth=1.5, label='Theoretical')
ax3.fill_between(dice_sorted, dice_cdf,
                 np.linspace(100/len(dice_sorted), 100, len(dice_sorted)),
                 alpha=0.04, color=DICE_C)
ax3.set_xlabel('Dice Result')
ax3.set_ylabel('Cumulative %')
ax3.set_xlim(0, 100)
ax3.set_ylim(0, 100)

max_dev = np.max(np.abs(dice_cdf - np.linspace(100/len(dice_sorted), 100, len(dice_sorted))))
ax3.text(0.03, 0.92, f'Max deviation from uniform: {max_dev:.2f}%',
         transform=ax3.transAxes, fontsize=9, color=GREEN, fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.3', facecolor=BG, edgecolor=GRID))
ax3.legend(fontsize=9, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc='lower right')

# --- 2B: Limbo survival ---
ax4 = fig.add_subplot(gs[1, 1])
style_ax(ax4, 'LIMBO — Survival Curve  P(result >= target)')

x_range = np.logspace(0, 2, 500)
emp_surv = np.array([np.sum(limbo_arr >= x) / len(limbo_arr) * 100 for x in x_range])
theo_surv = np.array([min(99.0/x, 100) for x in x_range])

ax4.plot(x_range, emp_surv, color=LIMBO_C, linewidth=2, label='Empirical', zorder=3)
ax4.plot(x_range, theo_surv, color=GOLD, linestyle='--', alpha=0.5,
         linewidth=1.5, label='Theoretical (99/x)')
ax4.fill_between(x_range, emp_surv, alpha=0.06, color=LIMBO_C)

ax4.set_xscale('log')
ax4.set_yscale('log')
ax4.set_xlabel('Target Multiplier')
ax4.set_ylabel('Win Probability %')
ax4.set_xlim(1, 100)
ax4.set_ylim(0.8, 105)

# Clean tick labels
ax4.xaxis.set_major_formatter(mticker.FormatStrFormatter('%g'))
ax4.yaxis.set_major_formatter(mticker.FormatStrFormatter('%g'))
ax4.set_xticks([1, 2, 3, 5, 10, 20, 50, 100])
ax4.set_yticks([1, 2, 5, 10, 20, 50, 100])

# Probability markers — spaced to avoid overlap
markers = [
    (1.5, 66, GREEN, '1.5x  66%'),
    (2.0, 49.5, DICE_C, '2x  49.5%'),
    (5.0, 19.8, GOLD, '5x  19.8%'),
    (10.0, 9.9, LIMBO_C, '10x  9.9%'),
    (50.0, 1.98, MUTED, '50x  1.98%'),
]
for target, prob, color, label in markers:
    ax4.plot(target, prob, 'o', color=color, markersize=6, zorder=5,
             markeredgecolor=WHITE, markeredgewidth=0.8)
    ax4.annotate(label, xy=(target, prob), xytext=(8, -2),
                 textcoords='offset points', fontsize=8, color=color,
                 fontfamily='monospace', fontweight='bold')

ax4.legend(fontsize=9, facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, loc='lower left')

# ==========================
# ROW 2.5: Spacer with key insight text
# ==========================

ax_spacer = fig.add_subplot(gs[2, :])
ax_spacer.set_facecolor(BG)
for spine in ax_spacer.spines.values():
    spine.set_visible(False)
ax_spacer.set_xticks([])
ax_spacer.set_yticks([])

ax_spacer.text(0.5, 0.5,
    'BOTH GAMES USE THE SAME HMAC-SHA512 RNG  —  '
    'DICE IS UNIFORM, LIMBO IS INVERSE  —  '
    'SAME EV (-1%), DIFFERENT VARIANCE SHAPE',
    ha='center', va='center', fontsize=11, color=GOLD, fontfamily='monospace',
    fontweight='bold', style='italic')

# ==========================
# ROW 3: DoubleDose mapping (full width)
# ==========================

ax5 = fig.add_subplot(gs[3, :])
style_ax(ax5, 'DOUBLEDOSE TRANSLATION  —  Dice Chance %  ↔  Limbo Target Multiplier')

chances = np.linspace(2, 99, 500)
targets = 99.0 / chances

# Main curve
ax5.plot(chances, targets, color=WHITE, linewidth=2.5, zorder=3)
ax5.fill_between(chances, targets, 0.9, alpha=0.04, color=DICE_C)

# DoubleDose operating zone
ax5.axvspan(25, 98, alpha=0.06, color=GREEN, zorder=1)
ax5.text(61.5, 0.97, 'DoubleDose operating range',
         fontsize=9, color=GREEN, fontfamily='monospace', alpha=0.7,
         transform=ax5.get_xaxis_transform(), ha='center')

# Key mapping points — positioned to avoid overlap
points = [
    (98,  99/98,  'DD Start: chance=98%',     GREEN,  (-60, 55)),
    (85,  99/85,  'After 1 loss: ~85%',       DICE_C, (30, 45)),
    (50,  99/50,  'Mid-range: 50%',           GOLD,   (-130, 25)),
    (25,  99/25,  'Win streak shift: 25%',    LIMBO_C,(-140, -25)),
]

for chance, target, label, color, offset in points:
    ax5.plot(chance, target, 'o', color=color, markersize=10, zorder=5,
             markeredgecolor=WHITE, markeredgewidth=1.5)

    payout_pct = (target - 1) * 100
    full_label = f'{label}\ntarget = {target:.2f}x  |  +{payout_pct:.1f}% per win'

    ax5.annotate(full_label, xy=(chance, target), xytext=offset,
                 textcoords='offset points', fontsize=9.5, color=color,
                 fontfamily='monospace', fontweight='bold', ha='center',
                 arrowprops=dict(arrowstyle='->', color=color, lw=1.5,
                                 connectionstyle='arc3,rad=0.15'),
                 bbox=dict(boxstyle='round,pad=0.4', facecolor=BG,
                           edgecolor=color, alpha=0.92))

# Minimum target line
RED_DEAD = '#da3633'
ax5.axhline(y=1.01, color=RED_DEAD, linestyle='-', linewidth=1.2, alpha=0.6, zorder=2)
ax5.text(3, 1.04, 'min target 1.01x', fontsize=8, color=RED_DEAD,
         fontfamily='monospace', alpha=0.8)

ax5.set_xlabel('Dice Chance %', fontsize=11)
ax5.set_ylabel('Limbo Target Multiplier', fontsize=11)
ax5.set_xlim(0, 100)
ax5.set_ylim(0.9, 15)
ax5.set_yscale('log')

ax5.yaxis.set_major_formatter(mticker.FormatStrFormatter('%gx'))
ax5.yaxis.set_minor_formatter(mticker.NullFormatter())
ax5.set_yticks([1, 1.5, 2, 3, 4, 5, 7, 10, 15])
ax5.xaxis.set_major_formatter(mticker.FormatStrFormatter('%g%%'))

# Formula bar at bottom
ax5.text(0.5, 0.04,
         'target = 99 / chance          chance = 99 / target          same RNG  ·  same EV  ·  different game surface',
         transform=ax5.transAxes, ha='center', fontsize=10,
         color=MUTED, fontfamily='monospace',
         bbox=dict(boxstyle='round,pad=0.5', facecolor=BG, edgecolor=GRID, alpha=0.9))

# ======================================================================
# Save
# ======================================================================

out = '/Users/stanz/codebase/SYMIR/antebot/scripts/tools/thrill_dice_vs_limbo.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=BG)
print(f"\nSaved to {out}")
