# Frame Export Alias Repair

The review of PR #426 at `8203da3` identified a hardlink alias that could
overwrite a successful render export with its JSON report. The same defect
was reproduced in the already merged camera and world-raster checkers:

| Exporter | Valid corpus bytes | Bytes after aliased report write |
| --- | --- | --- |
| Camera | 8,918,494 | 159 |
| World raster | 8,119,240 | 157 |
| Render | 14,783,106 | 158 |

All three reproductions returned `passed` despite destroying the requested
export. Their isolated RAM outputs and counterexample metadata were retained.
No canonical fixture was modified. The view-copy checker had already been
repaired for both resolved-path and existing-inode aliases.

The camera/raster repair is applied upstream, and the corresponding render
repair is applied on its dependent branch. The guards now reject resolved
aliases and two existing paths for the same inode before authentication or
report writing. They preserve file bytes and modification times on rejection.

`test_frame_export_aliases.py` defines one shared contract: missing/existing
identical paths, normalized aliases, hardlinks, symbolic links and distinct
output/report success. Camera, raster and view-copy are mandatory families;
render is included whenever its fixture family is present. A missing checker
for an existing family is an error. This supports the smaller parent branch
without silently omitting any exporter available in the integrated tree.

The repair changes only export safety, tests and their CMake registration.
Original fixture bytes and recovered C++ runtime behavior remain unchanged.
The natural continuous-frame proof retains its original CPU/clock/memory
results and is not redefined by this exporter repair.
