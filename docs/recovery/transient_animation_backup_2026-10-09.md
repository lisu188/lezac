# Transient Animation Backup Recovery

The production behavior-5 updater passed a newly default-constructed
`ActorAnimation` to mode-3 restoration. This invented the backup bytes
`02 02 09 01 01 01 01` rather than reading actor-owned state. `TransientActor`
now owns a separate seven-byte backup, and `updateTransientActor` uses it.
The member is appended so existing aggregate field positions do not change.

## Original Evidence

The retained unmodified-original CPU experiment executes the complete actor
pass at main CS:7EBB..7EEA and subsequent CS:804E..806A work. It patches no
instructions, stubs no calls, and rejects hardware I/O. The observer and a
second neutral CPU agree on all 1 MiB of mapped memory and fourteen registers
at each actor and post-pass return. Four unmodified control passes also match
the earlier pinned native mixed-actor records.

Eighteen seeded cases provide 108 actor passes. Seventeen cases use distinct
backup bytes `2B 2B 2E 02 02 02 FF`; all 104 tagged returns preserve those
bytes with no observed write to actor offsets 29..35. The cases include
corpse-to-reward/fade conversion in one- and thirty-actor pools, delayed corpse
expiry, reward pickup/expiry, bomb expiry, and behavior-5 animation. A fresh
repeat agrees on all 108 complete boundary states and register sets.

The focused behavior-5 mode-3 case starts with active bytes
`09 06 09 00 00 03 01`. Its six original active-animation returns are:

```text
2B 2B 2E 02 02 02 FF
2A 2B 2E 00 02 02 01
2A 2B 2E 01 02 02 01
2A 2B 2E 02 02 02 01
2B 2B 2E 00 02 02 FF
2B 2B 2E 01 02 02 FF
```

The mode-0 control retains `09 06 09 00 00 00 01`. Both cases preserve their
backup, keep position (192,88), and count the timer as 63,63,62,62,61,61.
The compiled call-site negative control misses all six mode-3 returns with
the former default-backup call; an explicit backup matches all twelve updates.
That tiny control is not an execution of the full App.

## Production Regression

`--debug-original-transient-animation-backup` calls the actual App
`updateTransientActor` continuously for both six-update cases. It compares
all seven active and backup bytes, sprite cursor, timer, position, velocity
and fractional carries. CTest registers `transient_animation_backup_original`.
The original trace and source-bound capture producer are retained under
`evidence/transient_animation_backup_20261009/`.

## Limits

These are seeded original CPU experiments, not natural routes, hardware
timing, screenshots, or full rendered-descriptor comparisons. The regression
does not exercise the shared dispatcher or physical actor storage. Default
zero backup state is not a claim about reused original slots.

The neighboring traces establish that in-place conversions preserve backups,
the animation prologue also precedes corpse handling, and reward/pickup
conversions explicitly disable active animation. Integrating those rules
across monster, bomb, reward and marker ownership remains separate work.
This change does not close full 38-byte storage, inactive-tail, campaign,
visual, sound, or whole-game fidelity requirements. All broad flags stay false.
