# Task lifecycle

## States

The helper uses these principal states:

- `ACTIVE` — agent is implementing the task.
- `READY_FOR_INTEGRATION` — implementation is committed, worktree is clean, verification evidence has been recorded.
- `INTEGRATION_VALIDATION` — candidate merge succeeded and awaits merged-state validation.
- `CONFLICT` — candidate merge produced Git conflicts.
- `INTEGRATION_ERROR` — integration command encountered a non-conflict failure that requires inspection.
- `INTEGRATED` — target branch contains the validated candidate.
- `ABANDONED` — agent intentionally stopped without integration.
- `BLOCKED_SEMANTIC_CONFLICT` — task conflicts with another task at the requirement/product-intent level.

## Normal state path

```text
ACTIVE
  ↓
READY_FOR_INTEGRATION
  ↓
INTEGRATION_VALIDATION
  ↓
INTEGRATED
```

Conflict path:

```text
READY_FOR_INTEGRATION
  ↓
CONFLICT
  ↓ resolve + commit
INTEGRATION_VALIDATION
  ↓
INTEGRATED
```

Abort/retry path:

```text
CONFLICT / INTEGRATION_ERROR / INTEGRATION_VALIDATION
  ↓ integrate-abort
READY_FOR_INTEGRATION
  ↓ re-read target/context
integrate-begin again
```

## Registration

A task registration captures:

- task ID;
- owner agent ID;
- title;
- objective;
- acceptance criteria;
- recorded target branch;
- exact base SHA;
- task branch;
- worktree path;
- soft claims;
- timestamps.

The exact base SHA matters. When integration happens later, the agent can reason about what changed on the target since implementation started.

## During implementation

The agent should update durable context when information becomes relevant to peers, not after every command.

Useful event types include:

- `intent`;
- `decision`;
- `interface_change`;
- `dependency`;
- `warning`;
- `scope_change`;
- `test_result`;
- `conflict_resolution`;
- `handoff`;
- `integration_note`.

## Ready transition

A task may become ready only when:

- the current worktree is the registered task worktree;
- the current branch is the registered task branch;
- there are no unresolved or uncommitted changes;
- the task HEAD is recorded;
- changed files can be determined from `base_sha...HEAD`;
- relevant tests/checks have been run, or the agent explicitly records why no additional verification is necessary.

## Integration transition

`integrate-begin` acquires the integration mutex and creates an integration session. The lock remains held until `integrate-finish` or `integrate-abort`.

Do not leave a terminal after `integrate-begin` without either finishing or aborting, unless a crash makes that impossible.

## Completion

A task is complete when the target contains the candidate commit and the shared task record is `INTEGRATED`.

The task worktree and branch can then be removed if desired. Cleanup is a separate operation because retaining the worktree for inspection can be useful.
