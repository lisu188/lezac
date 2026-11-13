# Level Export Denominator Metadata

The JSON exporter and committed `src/LIVELS.SCH.json` retained the older
glyph-based `startingDestructibleTiles` calculation after the recovered
runtime loader switched to physical word tags. The metadata did not describe
the denominator actually used by either raw or JSON gameplay loading.

`tools/export_resources_to_json.py` now counts words `1..0x3fff`, matching
`countPhysicalDamageProgressCells` in `src/core/progress.cpp`. Zero words,
deferred/debris words and damaged words are excluded. The glyph and objective
tile do not determine eligibility.

The original shipped `LIVELS.SCH` is unchanged and has SHA-256
`d8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2`.
All seven corrected metadata values equal its parsed `fieldB` values:

| Level | Previous Metadata | Physical Word Count / fieldB |
| --- | ---: | ---: |
| 1 | 573 | 66 |
| 2 | 809 | 393 |
| 3 | 3600 | 739 |
| 4 | 1295 | 435 |
| 5 | 1398 | 988 |
| 6 | 3511 | 2724 |
| 7 | 1675 | 330 |

Only these seven JSON numbers change; the level planes, original header
fields, spawners, portals and triggers are unchanged. Level 3 still requires
seven objectives and integer-floor destruction of at least 20 percent of 739
cells, or 148 destroyed cells.

`tools/check_level_exporter_counts.py`, registered as `level_exporter_counts`,
checks the pinned original bank, all seven counts, exact semantic regeneration
of the committed bank, and eight boundary words with deliberately independent
glyphs. The test failed against the older exporter for both shipped counts and
the synthetic word-domain case, then passed after this correction. Export
output is intercepted in memory, so the test writes no generated resource files.

This is an exporter/data consistency correction, not a recovered gameplay
change. The runtime loader already used the correct word-domain denominator.
It does not prove natural Level 3 completion, later-level progression, all actor
fields, sound parity, physical presentation timing or whole-game fidelity.
The broad completion and fidelity flags remain false.
