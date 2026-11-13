# Shipped Level 3 Completion Requirements

The Level 3 objective requirement is **seven**, not the number of objective
tiles remaining on the map. The ordinary original-backed route through tick
8750 has collected nine, so its objective gate is already satisfied. It has
destroyed 114 of the 148 required physical-damage cells; 34 more remain before
the raw destruction gate is satisfied. Natural Level 3 completion is unproven.

## Original Data And Runtime Evidence

`LIVELS.SCH` has SHA-256
`d8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2`.
The Level 3 record begins at byte offset 4923. Its first eight bytes,
`96003c006c070014`, decode in the existing little-endian loader as:

| Field | Value |
| --- | ---: |
| Width | 150 |
| Height | 60 |
| Objective glyph | 108 |
| Required objectives | 7 |
| Required destruction percent | 20 |

The shipped `fieldB` denominator is 739. The integer-floor production predicate
requires `destroyed * 100 / 739 >= 20`, whose first satisfying count is 148.
The diagnostic reports ten objective tiles in the initial map, which is a
different quantity from the required objective count. One objective remains
in the verified tick-8750 original map at pixel position `(864,208)`; collecting
it is not needed to meet the objective threshold.

The tick-8750 endpoint is backed by the independently retained original capture
`refs/notes/qa-natural-level3-20261005-corrected-ammo-original-20261006-raw`,
anchored to source commit `e4a7f90872c3b9ea3d089b4aa652e9b16b33d6b8`.
Its archive SHA-256 is
`3b72b757b2a9e9aa596213421e8da9765f9f3f807faa7e3b8c52b58ab2492d2c`.
Whole-archive bytes and all 5,093 members were checked through independent
remote readback. The original Level 3 stream SHA-256 is
`0fe4d1736a7c2152f16dc6fafd2ae5e94782d0f372aaf9f3b8ecaebf01e960bb`.
The mapped post-update state has progress `[9,114]`. Its tile and word planes
have SHA-256 values
`019aee75a790634cec24d9d52ed70305b17e60d50236dbb212865547fb2bf13c` and
`c076afd5200696155f6e527f18119f8d238052491ed1a28c3db7e6a2906e06cc`.

## Regression Scope

`--debug-level-completion-denominator` now pins both shipped requirements for
all seven levels. It checks that reaching each destruction threshold with one
objective too few does not complete the level, and that reaching the objective
threshold with one destroyed cell too few also does not complete it. The
existing exact-threshold and 100-percent checks remain in place.

This is a deterministic predicate regression, not an ordinary-input completion
route or proof of the later presentation transition. The original completion
path also waits for the cached HUD completion flags and an empty collapse queue.
The separate `level_completion_gate` regression retains those checks.

The original map/header inspection changes no gameplay state. All game and
test runs use dummy audio. It does not establish all-actor byte equivalence,
physical timing, audible sound parity, later-level completion or whole-game
fidelity. `port_functionally_complete=0` and `original_fidelity_claim=0` remain
unchanged.
