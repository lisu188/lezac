#!/usr/bin/env python3
"""Check synthetic actor dispatch-gate sweep summary output."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(
    root: Path, manifest: Path, expect_success: bool = True
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_actor_dispatch_gate_sweep.py"),
        str(manifest),
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"sweep summary failed with {result.returncode}: {manifest}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"sweep summary unexpectedly passed: {manifest}\n{result.stdout}"
        )
    return result


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check actor dispatch-gate sweep summary behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-actor-dispatch-summary-") as tmp:
        base = Path(tmp)
        dispatch = base / "dispatch"
        gate5 = dispatch / "actor_update_gate5" / "manifest.txt"
        gate6 = dispatch / "actor_update_gate6" / "manifest.txt"
        write_text(
            gate5,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate5",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "capture_status_x2p00=actor_contact_procmem=ok mode=capture target=actor_update_gate5 ghidra=1000:65A2 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:65A2 freeze_observed=0 manifest=/tmp/gate5/manifest.txt raw_dump=/tmp/gate5/raw.txt candidate_fixture=/tmp/gate5/candidate_fixture.txt procmem_manifest=/tmp/gate5/procmem_manifest.txt",
                    "",
                ]
            ),
        )
        write_text(
            gate6,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x3p00",
                    "capture_status_x3p00=actor_contact_procmem=ok mode=capture target=actor_update_gate6 ghidra=1000:654E runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:654E freeze_observed=1 manifest=/tmp/gate6/manifest.txt raw_dump=/tmp/gate6/raw.txt candidate_fixture=/tmp/gate6/candidate_fixture.txt procmem_manifest=/tmp/gate6/procmem_manifest.txt",
                    "",
                ]
            ),
        )
        dispatch_manifest = dispatch / "manifest.txt"
        write_text(
            dispatch_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=actor_update_gate5,actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    f"sweep_manifest_actor_update_gate5={gate5}",
                    f"sweep_manifest_actor_update_gate6={gate6}",
                    "",
                ]
            ),
        )
        result = run_summary(root, dispatch_manifest).stdout
        for snippet in [
            "actor_dispatch_gate_sweep_summary=ok",
            "capture=actor_dispatch_gate_sweep",
            "mode=dispatch",
            "targets=2",
            "route_sweeps=2",
            "captures=2",
            "freezes=1",
            "observed_targets=actor_update_gate6",
            "missing_targets=actor_update_gate5",
            "candidate_fixtures=/tmp/gate6/candidate_fixture.txt",
            "freeze target=actor_update_gate6 route=x3p00 ghidra=1000:654E",
        ]:
            require(result, snippet, "dispatch_manifest")
        cases += 1

        direct_manifest = base / "direct" / "manifest.txt"
        write_text(
            direct_manifest,
            "\n".join(
                [
                    "capture=actor_contact_route_sweep",
                    "target=contact_scanner_callsite",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x1p50",
                    "capture_status_x1p50=actor_contact_procmem=ok mode=capture target=contact_scanner_callsite ghidra=1000:6555 runtime_cs=01ED runtime_ds=0F3C freeze_runtime=01ED:6555 freeze_observed=runtime_child_memory_freeze_observed raw_dump=/tmp/contact/raw.txt candidate_fixture=/tmp/contact/candidate_fixture.txt",
                    "",
                ]
            ),
        )
        direct = run_summary(root, direct_manifest.parent).stdout
        for snippet in [
            "capture=actor_contact_route_sweep",
            "mode=route",
            "targets=1",
            "route_sweeps=1",
            "captures=1",
            "freezes=1",
            "observed_targets=contact_scanner_callsite",
            "missing_targets=none",
            "candidate_fixtures=/tmp/contact/candidate_fixture.txt",
        ]:
            require(direct, snippet, "direct_route_manifest")
        cases += 1

        dry_manifest = base / "dry" / "manifest.txt"
        write_text(
            dry_manifest,
            "\n".join(
                [
                    "capture=actor_dispatch_gate_sweep",
                    "asset_dir=/repo",
                    "targets=actor_update_gate5,actor_update_gate6",
                    "timings=before_route",
                    "routes=1",
                    "route_labels=x2p00",
                    "",
                ]
            ),
        )
        dry = run_summary(root, dry_manifest).stdout
        for snippet in [
            "mode=dispatch",
            "targets=2",
            "route_sweeps=0",
            "captures=0",
            "freezes=0",
            "observed_targets=none",
            "missing_targets=actor_update_gate5,actor_update_gate6",
            "candidate_fixtures=none",
        ]:
            require(dry, snippet, "dry_manifest")
        cases += 1

        missing = run_summary(root, base / "missing" / "manifest.txt", False).stdout
        require(missing, "actor_dispatch_gate_sweep_summary=error", "missing_manifest")
        require(missing, "manifest not found", "missing_manifest")
        cases += 1

    print(f"actor_dispatch_gate_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
