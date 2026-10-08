# Original Actor Constructor Velocity

The complete original `1000:2F9F..30A3` constructor was executed for all 65,536
signed WORD inputs on X and then Y, with the other axis zero: 131,072 calls.
The MZ executable, constructor bytes, native-observed descriptor fixture and
capture generator are hash-pinned. Original calls are not stubbed, code is not
patched, hardware I/O is forbidden, and every near-return CS/IP/SP is checked.
The fixture stores only velocity WORDs at actor offsets +6/+8, not full actors.
Descriptor-text provenance uses canonical LF bytes on both host platforms.

The original clamps to +/-2047 except that -32768 passes unchanged. Its WORD
absolute value overflows to a negative value, satisfying the signed JLE test.
122,880 of the 131,072 axis inputs change. A fresh capture reproduces the prior
analysis vector exactly, SHA-256
`8d1cf2ab4126b1f9f67604ab763541d037aab549b6ba5aa2c7e91fe588890fe8`.

`clampConstructedActorVelocity8` now supplies this rule to transient creation
and existing bomb launch construction. Bomb multiplication/subtraction still
wrap before signed division; its existing 524,288-constructor compiled scan is
retained. Monster motion assigned after construction and other update writes
are not changed. No ordinary-gameplay out-of-range transient input is proved.

`--debug-original-actor-constructor-velocity OUTPUT` executes 131,072 real
`spawnTransientActor` calls. Its Y axis compares actual transient creation for
all signed inputs. Transient creation has no X argument; X therefore compares
the shared compiled helper, not a nonexistent transient-X constructor path.
The probe receives no expected fixture values. The independent pinned original
vector is compared outside the executable, word-for-word and length-for-length.

The contract rejects eight source/routing mutations and twelve comparison
mutations, with an explicit positive vector control. Eight mocked runner tests
check retained expected/actual outputs,
stdout, stderr and failure metadata across success, nonzero exit, truncation,
missing output, wrong coverage banner, timeout, corrupted output and a directory
in place of output. Read errors cannot suppress the failure report. Each real compiled invocation
retains its own directory; an earlier focused run cannot supply stale output.
Windows/Linux CI runs constructor and bomb regressions early and always uploads
diagnostics, including failure logs, both before and after the full suite so its
rerun evidence is retained as well. Full suites, extracted packages and exact-
head review are still required before merge. Local heavy builds/native captures
remain capacity-blocked; source-only checks are not compiled parity evidence.

This is controlled constructor evidence. Natural reachability, stale-slot and
mixed-pool behavior, other actor fields, later motion, rendered pixels, sound
and whole-game fidelity are not established. No broad completion flag changes.
