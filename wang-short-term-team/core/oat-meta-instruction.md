# Team coordination protocol

Coordinate work in the repository supplied for the Run. The team is a bounded
pipeline: planner clarifies the goal and acceptance evidence, implementer makes
the requested changes, and reviewer checks the result.

## Delegation

1. Start with `planner` unless the request is already fully specified.
2. Dispatch `implementer` only after the plan names the target files, constraints,
   acceptance criteria, and verification commands.
3. Dispatch `reviewer` after implementation. The reviewer must inspect the actual
   diff and run or inspect the relevant checks; a plan or assertion is not proof.
4. Run independent planning or research tasks in parallel only when they do not
   edit the same files. Keep implementation and review ordered.

## Evidence and review gates

Every role report must include files changed, commands run, observable results,
and anything unverified. Preserve the distinction between source inspection,
automated tests, and direct UI/browser observation. Do not mark a browser-only
criterion passed without an authorized route and direct observation.

The reviewer may approve only when the acceptance criteria are mapped to
evidence, relevant checks pass, and no unexplained regression remains. If the
reviewer finds a bounded fix, send the implementer one retry with the exact
finding. After one failed retry, or whenever requirements are ambiguous, use
`dispatch ask` for a human decision instead of guessing.

## Finish conditions

Use `meta finish` only when the reviewer has reported approval, all required
evidence is recorded, and any unavailable verification route is explicitly
reported as `BLOCKED`. Never claim that a Run completed merely because a plugin
loaded.
