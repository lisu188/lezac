# Original Evidence Blocker: Windows WSL Distro Missing

This note records a local evidence-capture blocker observed on 2026-05-23 in
the Windows workspace. It is not original gameplay evidence and must not be
used to promote any visual claim.

```text
original_evidence_blocker=windows_no_default_wsl_distro
date=2026-05-23
host=windows
assets=ok
wsl=found
wsl_probe=ok
wsl_bash_probe=error_4294967295
wsl_bash_reason=no_default_distro
missing_required=bash,dosbox,xvfb-run,xdotool
environment_preflight=error
not_original_evidence=1
visual_claim=0
```

The local shell has `wsl.exe`, but no default Linux distribution is installed.
It also has no native `bash`, `dosbox`, `dosbox-debug`, `xvfb-run`, or
`xdotool`, so original DOSBox/Xvfb frame capture cannot run on this host.

The direct WSL `dosbox-debug` probe was retried on 2026-06-16 and failed for
the same host-level reason before any Linux command could run:

```text
original_evidence_blocker=windows_wsl_dosbox_debug_probe_failed
date=2026-06-16
command=wsl -- bash -lc 'set -e; command -v dosbox-debug; dosbox-debug -version'
wsl_dosbox_debug_probe=error
wsl_error=WSL_E_DEFAULT_DISTRO_NOT_FOUND
not_original_evidence=1
visual_claim=0
```

The observed preflight command was:

```powershell
python tools/preflight_original_evidence_environment.py . --require-assets --require-frame-capture --probe-wsl --require-wsl-bash-on-windows
```

The meaningful preflight result was:

```text
original_evidence_environment=error reason=wsl_bash_not_usable wsl_bash_probe=error_4294967295 wsl_bash_reason=no_default_distro missing_required=bash,dosbox,xvfb-run,xdotool
```

Rerun this sequence on the next WSL/cloud host before attempting to promote
frame evidence:

```sh
python tools/preflight_original_evidence_environment.py . --require-assets --require-frame-capture --probe-wsl --require-wsl-bash-on-windows
wsl -- bash -lc 'set -e; command -v dosbox-debug; dosbox-debug -version'
tools/compare_original_cpp_frames.sh /tmp/lezac-frame-compare . level1_bomb_route
tools/summarize_frame_compare_bundle.py /tmp/lezac-frame-compare --require-promotion-ready
```

If the comparison succeeds, inspect the original frames, C++ frames,
`frame_compare_summary.txt`, `manifest.txt`, and the recorded
`environment_preflight.log` before creating or updating any promoted
`visual_claim=1` fixture or ledger entry.
