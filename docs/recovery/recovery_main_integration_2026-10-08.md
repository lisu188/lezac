# Current-main recovery integration

This batch integrates already-reviewed, successful heads without amending or
restarting them:

- PR322, `398ac9a580440e3f59c96b27cdf581be3e051947`: complete original-backed
  debris and collapse update probes, collapse contact probes, original record
  initialization, and retained contact failure diagnostics.
- PR309, `18bb982051b680a7057b90e20739beafdfcec0a1`: the original flame contact
  signed-WORD blend, with all 1,376,256 controlled original instruction records.
- PR319, `0bbf55b7cb2ecfd2d3a2f046719d14c9324b53ba`: PPM raster separator and
  whitespace fixes with 1,551 valid and 12 malformed image cases.

The integration starts at main `5541147d97b997630daaef5b0fc6249c568b930b`.
It preserves PR320's raw lane-word fix and PR315's historical review repairs.
Overlapping CMake registrations, CI steps, and binary fixture attributes retain
both sides. Production flame blending remains routed through the shared helper;
no updater ordering, fixture protocol, or expected original bytes are changed.

CI retains the existing early focused checks and uploads. An additional
`if: always()` upload after each full suite preserves failures produced by the
second invocation, plus `LastTest.log` and `LastTestsFailed.log`. Artifact names
are distinct between platforms and from earlier uploads.

Historical review dispositions:

- PR36's P1 binary PPM raster issue is fixed by the integrated PR319 patch.
- PR318's P2 lost contact probe diagnostics is fixed by the integrated PR322
  checker and its ten mocked runner modes / twelve direct comparison cases.
- PR112's P1 collapsed-record classification is already fixed on the base by
  PR320; its exhaustive lane-word checks remain enabled.
- PR308's sound catch-up and PR324's live-deadline findings are tracked by
  PR325, not claimed fixed by this integration.
- PR243's diagnostic live-tick adapter finding concerns its unmerged
  modularization branch; it is not introduced or dismissed here.

Earlier green results establish only their individual heads. This combined
tree requires its own full Linux and Windows CI, extracted-package checks,
and exact-head review before merging. No local full build or native capture
was attempted while the existing disk/reserve guards were closed.

The controlled updater/contact/arithmetic probes do not prove natural Level4
progression, full actor-pool equivalence, visual or sound parity, or the complete
seven-level campaign. All broad completion and fidelity claims remain false;
there is still no defensible aggregate completion percentage.
