# Complete Actor Calls

Controlled original executions from 6053, plus actual caller cases from 7EBB,
through the real actor RET 4 at 7780. Runtime and divide faults stop before
their handlers.

- 7,188 cases; 7,180 real returns, six runtime errors and two divide faults.
- 28 actual player CALLs and 74 actual nonplayer CALLs execute.
- 7,723,202 register states and 1,411,439 ordered memory writes.
- Eight mode-3 initial animation states execute the actual seven-byte Move.
- Observed/unobserved complete memory and endpoint registers match. Ordered
  writes reconstruct every change; all 43,552 original code bytes stay unchanged.
- The corpus contains compact initial differences and traces, not full RAM.

Initial data/stack are controlled, not natural gameplay. There is no production
App integration, captured original IRQ schedule or whole-frame/pixel claim.
Post-return player health, life-loss and HUD caller instructions remain outside
this actor-call boundary.
