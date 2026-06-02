# Private Validation Replay

Status: LP-ready public-safe replay derived from a closed validation run on
2026-06-01.

This is not a terminal transcript. It is the public-safe version of a real
validation run where Knudg was checked before broad local investigation. Raw
prompt text, private paths, identifiers, command lines, and card details are
intentionally omitted.

## Observed Flow

1. The turn-start check decided Knudg should be considered for the task.
2. The check did not call Knudg directly.
3. A sanitized task summary was sent through the live nudge path.
4. Knudg returned a low-risk suggestion that prior experience may be relevant.
5. The agent still had to verify the clue in the current workspace.

## LP Copy

Task starts.
: An agent begins a recurring developer-tooling failure.

Knudg checks for prior experience.
: A related clue is available, but it is not treated as an answer.

The agent verifies locally.
: The current workspace still decides whether the clue applies.

Private material stays out.
: No raw transcript, private path, identifier, or command is shown here.

## Safety Boundary

This replay is safe for the landing page because it does not expose internal
routes, schemas, state names, card IDs, exact card contents, private paths,
raw transcript text, command text, tokens, or backend details.
