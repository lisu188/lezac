# CI Compression and Artifact Budget Repair

Run `41586862741`, at PR #478 head
`38d72978608861bf8a59da284cfdcff32f0abf41`, exposed two independent failures:

- Linux completed all 1222 CTests with zero failures (one display test skipped),
  but the job reached its three-hour limit while preserving final artifacts.
- Windows completed 1181 CTests with one failure:
  `original_debris_phase_fixture`, specifically the byte-for-byte gzip
  reproduction assertion. All other Windows tests passed.

The frozen debris phase fixture is a 14564-byte gzip member produced at
compression level 9. Explicit level 9 reproduces its exact bytes; level 6
produces a different 17286-byte member with the same decoded payload. Python
3.15 changed the default gzip compression level to 6. The reproduction test
now requests level 9 explicitly, with a level-6 negative control. The four
Linux/Windows Python 3.12/3.15 compatibility jobs run this suite as well.

Original fixtures, capture producers and their provenance hashes remain
unchanged. This repairs reproduction of already-frozen evidence, not the
historical capture. No C++ behavior or fidelity claim changes.

The Linux job budget is now four hours, leaving room for the observed test
duration and artifact uploads. Windows retains its existing three-hour budget.
No test command, assertion, failure handling or artifact step is removed.

Local validation passes on Linux Python 3.12.3 and native Windows Python
3.12.14, using verified RAM scratch: eight debris fixture tests and six
existing compatibility tests on each host. Emulating only the Python 3.15
`GzipFile` default reproduces the old assertion failure and passes all eight
fixed tests. This emulation is not a native Python 3.15 execution; the hosted
matrix provides that separate lane. Parsed workflow comparison confirms all
existing test and artifact steps are unchanged.

Official Python documentation:
https://docs.python.org/3.15/library/gzip.html#gzip.GzipFile
