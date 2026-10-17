# Foreground Observation

This isolated observer captures the original `game:7903..7A13` foreground
fragment: adaptive pacing, HUD prelude and BIOS keyboard drain. It records
predecode boundaries, RGB32 renderer palettes, native SDL color mappings,
clock inputs and 272 indexed HUD pixels. Guest instructions and state are not
patched. Every game process uses dummy audio.

`build.py` creates a separate configured observation host in RAM.
`rebuild.py` reuses an owned previous host and retains its prior binary, API,
getter fragments, metadata and SDL GUI source before replacing observation
code. The frozen fixture also retains the exact incremental rebuild receipt
used after a failed first compile. This is not a clean-build claim.

`capture.py` follows ordinary one-player input. It defers the scripted Z hold
until the initial palette observation finishes, because tracing changes host
execution speed. It neither pauses the guest nor writes guest memory.
`project.py` verifies the retained executable and RAM sample hashes, then
projects the two complete observed windows. Only entry state seeds C++ replay;
later observations are comparison targets.

`build_palette_oracle.py` extracts unchanged `Check_Palette` and `GFX_GetRGB`
functions from pinned DOSBox 0.74-3 sources. The 96 controlled RGB32 profiles
execute native SDL mapping; they are function-level evidence, not whole-host
or gameplay evidence. Non-RGB32, locked, blit, inactive and incoherent backend
profiles are unsupported and rejected by the recovered clock.

The oracle process uses an explicit SDK loader path and a complete environment
without inherited loader overrides. Its driver reports the actual SDL image
containing `SDL_MapRGB` through `dladdr`; the producer verifies that resolved
path and its bytes against the expected SDK image before accepting a report.
`check_sdl_runtime.py` retains a real external-SDK loader counterexample and
verifies that the corrected run selects the intended image.

The natural fixture has no timer IRQ deliveries and no changed-HUD glyph
copies. Those paths retain their earlier subsystem fixtures. This work is not
wired into the App loop and does not establish full-frame or whole-game parity.
