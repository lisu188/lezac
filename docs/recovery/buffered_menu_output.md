# Repeated Buffered Menu Observations

PR #382's Linux CI run `38030183148` passed the early live keyboard checks,
then failed `buffered_menu_repeat_live_xvfb` in the full suite before launching
the game. Both invocations used `build/buffered-menu-live-checks`; the second
attempt raised `FileExistsError` while creating its `held-one` case directory.
This was output ownership failure, not evidence of a gameplay regression.

## Output Contract

`tools/test_buffered_menu_repeat_xdotool.py` now reserves its output directory
before observing any case. A new `--out` directory retains the existing layout:

```text
buffered-menu-live-checks/
  held-one/
  held-two/
  fresh-intro/
  result.json
```

If the requested directory already exists, the helper atomically reserves a
unique `run-*` child and puts all three cases and their summary there. It never
deletes or overwrites a previous observation, including an incomplete or failed
run. Concurrent invocations get distinct directories. An existing file or an
unrelated directory-creation error still fails; it is not treated as a passing
observation. Omitting `--out` still creates a unique system temporary directory.

The summary's `output` field and the success line identify the actual run path.
CI uploads the whole requested tree, so later runs are preserved alongside the
first run. The observation body, physical input sequence, frame checks and
dummy-audio environment are unchanged.

## Regression Scope

```sh
python3 -S -B tools/test_buffered_menu_output.py -v
```

These stdlib-only regressions cover the output allocator and repeated `main`
invocations with a mocked observer. They do not launch or validate the game.
CTest registers them as `buffered_menu_output_tools_contract` on both platforms.
Linux CI additionally invokes the real live test twice in its focused step,
using the same requested directory, before the full suite invokes it again.
Real live-run and full-suite results remain separate from the mocked tests.
