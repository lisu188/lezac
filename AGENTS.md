# Repository Agent Instructions

## Git workflow

- Never work directly on `main` or `master`.
- Before making code changes, create a new branch from the current default
  branch.
- Use a clear branch name that reflects the task.
- Keep all work isolated to that branch.
- Always rebase your branch onto the latest `main` before pushing or opening a
  pull request.

## Required delivery flow

- After finishing the task, review the diff.
- Run relevant tests, checks, or validation steps when available.
- Commit the changes with a clear, descriptive commit message.
- Push the branch to the remote.
- Create a pull request.

## Pull request expectations

- The pull request title should clearly describe the change.
- The pull request body should include:
  - what was changed
  - why it was changed
  - validation performed
  - any known limitations or follow-up work

## Safety rules

- Do not merge the pull request.
- Do not delete branches unless explicitly asked.
- Do not bypass failing checks unless explicitly asked.
- Do not make unrelated cleanup changes outside the task scope.

## Working style

- Prefer minimal, targeted changes over broad rewrites.
- Follow existing project patterns and conventions.
- Avoid introducing new dependencies unless necessary.
- Call out uncertainty instead of guessing.
- If the repository is missing a remote or PR creation is not possible, state
  that explicitly.

## DOSBox original-game observation

Use DOSBox as an oracle for original `LEZAC.EXE` behavior when disassembly is
unclear or runtime presentation matters. Prefer observing the original in a
temporary copy so `RECS.DAT`, setup files, or other shipped assets are not
modified in-place.

Create a temporary DOSBox run directory:

```sh
mkdir -p /tmp/lezac-dosbox
cp LEZAC.EXE *.DAT *.SPR *.PAL *.SCH *.SON *.MST *.CAR *.ZBG *.DOC /tmp/lezac-dosbox/
dosbox -c "mount c /tmp/lezac-dosbox" -c "c:" -c "LEZAC.EXE"
```

Run directly from the repository only when intentional file writes are
acceptable:

```sh
dosbox -c "mount c ." -c "c:" -c "LEZAC.EXE"
```

Use DOSBox to verify focused behavior questions, then encode the recovered rule
in deterministic C++ debug commands or tests. Useful observation targets
include:

- menu, help, records, setup, pause, quit, and level-transition flows
- player death, state-2 countdown, reentry, player-out, and game-over behavior
- two-player controls and shared-objective semantics
- bomb explosions, passable objects, debris/collapse playback, and damage
  timing
- monster movement, collision, rewards, and spawner lifecycle
- record-entry cursor behavior, accepted characters, typematic repeat, and save
  behavior

If automating DOSBox, keep it best-effort and document the exact command,
environment, input sequence, and any failure reason. SDL/Xvfb/xdotool tests for
the C++ port are generally more reliable for regression coverage than DOSBox
key injection.
