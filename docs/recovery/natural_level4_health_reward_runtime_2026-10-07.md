# Natural Level 4 Health Reward

The ordinary route through tick 11360 reaches a ground-monster reward and
collects it at tick 11306. Original health changes from 22 to 55, with seven
Medium bombs retained. This branch ends with two objectives and 144 destroyed
structures. The earlier three-objective/244-structure route remains a separate,
stronger campaign-progress anchor; neither route completes Level 4.

## Original Evidence

`tests/fixtures/natural_level4_health_reward/native.json.gz` is exported solely
from the closed, coherent original capture. Its pinned SHA-256 is
`b516c145eb34b84fa90a336c2e5a8aa8800460e7d7ac5de023e57a52ab7fc732`.
The original Level 4 stream has SHA-256
`9b944f2a7e8485a7ec7346f1df0f5d05823df804c0b2963537a4cfe5f4bb6226`.
The independent raw-memory audit covers 5878 atomic boundaries, with zero
coherence differences and zero normalized bytes. Expected values were not
read from the C++ replay.

The original keeps actor bytes +0x16..+0x1c through corpse-to-reward conversion
at ticks 9788 and 11230, then through reward-to-score-marker conversion at
11306. The captured seven-byte animations are respectively
`33 32 34 fe 02 00 01` and `2c 2c 2d fe 02 00 01`.
The disabled animation remains frozen while the score marker moves and expires.

The initial diagnostic matched all 2000 RGB presentations, but found 100
animation-state differences after pickup. A broader transient diagnostic also
reported 30 portal-marker boundaries because it inspected only the port's
transient collection, not its separate launch/portal-marker collection.
The new regression compares both collections in shared actor birth order.

## Recovery And Regression

`BonusDrop` now retains the corpse animation and passes it to the collected
score marker. Presentation tracing exposes reward and portal-marker animation
bytes. The existing sprite-88 projection now checks the complete original
descriptor, including its pixel offset: sprites 85..88 share a 20-by-6 shape
and cannot be distinguished by dimensions alone.

`natural_level4_health_reward_original` runs the full ordinary-input prefix
from Level 1, compares 2000 RGB presentations and 3940 existing mapped,
lifecycle, monster and terrain boundaries, then checks 3878 Level 4 boundaries
containing 1590 kind-11 observations and 552 reward observations. Those added
observations include position, velocity, fractions, kind, lifetime, hotspot,
full sprite descriptor and all seven animation bytes.

The guard rejects a change to each inherited animation byte and exercises
all four equal-sized descriptor choices. The existing 28 reward-pickup cases
also check inherited animation and its disabled next-update behavior.

These are scoped original-backed route checks, not full actor-byte, sound,
timing, two-player, Level 4 completion or whole-game fidelity claims. All runs
use dummy audio. Broad completion flags remain false.
