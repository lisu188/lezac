# Retained Original Flyer Motion Captures

`native-captures.tar.gz` preserves both complete 176-case native captures,
their raw local bytes, configurations, logs, original bootstrap screenshots,
restoration receipts, the executed producer and validation snapshot, and the
failed-before/fixed-after production diagnostics. All 24 members were compared
byte-for-byte before retention; the archive validator repeats the per-file
checks and reproduces the pinned fixture from each original capture.

- Bytes: 87,844
- SHA-256: `b285a0969e7e070c0a996cec82f828ec4746bcd4e3b0e1b1094ee15e5ae51641`
- Negative diagnostic source commit: `c8f674c`
- Source assets are separately pinned in both capture manifests and remain in
  the repository; the archive does not duplicate the temporary asset copies.
- The archived checker is the snapshot used before archive-checking was added.
  The current checker additionally pins this complete archive and verifies it.

The screenshots show the unseeded two-player level-1 bootstrap, not the seeded
motion cases or a paired C++ pixel comparison. These are bounded behavior-4
motion probes, not natural routes, natural actor constructors, damage/animation
parity or a complete actor/campaign comparison.
