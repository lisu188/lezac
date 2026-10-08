# Live Sound Deadline Review Repair

PR324 review finding:
<https://github.com/lisu188/lezac/pull/324#discussion_r4216230283>.

The governed loop checks its stop predicate before processing events. If a
runner stalls across the diagnostic's 600 ms deadline, the previous sound
service may be too early, or an intervening service may exceed the former
12,000..18,000 sample and 10..14 interrupt windows. Those windows incorrectly
treated host scheduling as a sound-model invariant.

The live diagnostic now services the production sound clock once after the
interactive loop returns. Two SDL tick samples bracket that service, and its
stored timestamp must fall inside the bracket, including unsigned tick wrap.
The baseline retains the clock's sample count, interrupt count, PIT remainder
and fractional millisecond-to-sample remainder after the initial request.
Expected sample advancement is computed from actual serviced milliseconds;
interrupt advancement and the final PIT remainder must match that sample count.
There is no fixed upper elapsed-time or interrupt limit. The sweep must still
finish, gameplay must stay frozen, and the dummy audio queue must remain bounded.

`clocked_sound_live_menu_stalled` and `clocked_sound_live_pause_stalled` inject
an 850 ms delay in the first stop-predicate call, before any loop event service.
This deliberately crosses both the deadline and the old sample window. Missing
final servicing leaves stale state and fails the same diagnostic. These tests
use the actual `runInteractive`, `pumpGovernedLoop` and `serviceSoundClock` paths,
not a duplicate loop. Normal menu/pause cases remain enabled. Stalled frames
have distinct filenames and are retained by the existing always-upload CI step.
The upload also preserves CTest's last-test and failure logs, including the
observed/expected samples, interrupts, PIT remainder and timestamp bracket in
the diagnostic's failure message. Failures before frame creation stay visible.

`clocked_sound_deadline_contract` rejects twelve source/wiring mutations.
That check is not compiled execution evidence. Windows/Linux hosted compiled
regressions and full suites must pass on the delivered head before merging.
Local heavy builds and native captures remain capacity-blocked. No production
gameplay/sound algorithm is changed by this deadline-diagnostic repair. Original
hardware timing, native cadence and whole-game sound fidelity remain unproved.
