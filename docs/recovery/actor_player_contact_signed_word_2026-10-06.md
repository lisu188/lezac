# Actor/Player Signed-Word Contact

The player-contact path compares the absolute value of a **signed 16-bit
difference** against 10. Its ordinary domain is -9 through +9 on each axis.
The original also accepts the special word `0x8000`: the absolute-value
sequence overflows to the same negative word, and signed `JL` accepts it.
Differences must first wrap to 16 bits; a wide C++ subtraction and ordinary
range test do not preserve those outcomes.

## Original Opcode Evidence

`LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The MZ image starts at file offset `0x0770`.

| Player/Axis | Code Address | Stack Word | Reject Target |
| --- | --- | --- | --- |
| Player 1 X | `1000:63BE` | `BP-04` | `1000:645F` |
| Player 1 Y | `1000:63CE` | `BP-06` | `1000:645F` |
| Player 2 X | `1000:645F` | `BP-08` | `1000:6500` |
| Player 2 Y | `1000:646F` | `BP-0A` | `1000:6500` |

Each window is `MOV AX,[BP+disp]; CWD; XOR AX,DX; SUB AX,DX; CMP AX,10;
JL +3; JMP reject`. The accepted monster path increments the byte damage
counter at `DS:79E8` (`1000:63F0`) or `DS:79E9` (`1000:6491`). Actor Y is
already biased by actor byte `+0x14`; contact still precedes actor integration.

The input words are also pinned: player 1 X/Y subtraction at `1000:62F5`
and `1000:6301`, player 2 X/Y at `1000:6330` and `1000:633C`. Each loads a
player coordinate into AX, subtracts the actor's local coordinate and stores
AX into the corresponding stack word. This proves wrapping occurs before
the absolute-value comparison, rather than being a property of the C++ model.

## Recovery And Checks

`actorTouchesPlayer` now reproduces wrapped differences, word negation and
the signed comparison without C++ signed-overflow dependence. Neither update
order nor the contact caller's death gates change.

- `actor_player_contact_opcodes` pins all four word subtractions, four
  comparison windows and both
  counter increments, checks the original fingerprint, and derives the 20
  accepted word values from the original CWD/XOR/SUB/CMP/JL semantics.
- `actor_player_contact_opcode_selftest` rejects independent mutations of all
  122 pinned bytes, plus an original-file mutation outside those windows.
- `actor_player_contact_signed_word` exercises the actual production helper
  across every 16-bit difference on each axis at four origins: 524,288 axis
  checks and 225 mixed boundary corners.

These are static-original-backed arithmetic checks, not a new native runtime
capture of every boundary. The historical natural contact traces remain
separate evidence. Full actor-field equivalence, natural later-level routes,
sound, physical timing and whole-game completion are not claimed here.
