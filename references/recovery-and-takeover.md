# Recovery and takeover

## Agent crash

A crashed terminal should not damage other tasks because implementation work is isolated by branch/worktree.

When an agent disappears, durable recovery sources are:

- task manifest;
- task branch;
- task worktree;
- agent journal;
- agent status/heartbeat;
- integration session, if any;
- Git commits.

## Determine task state

Before taking over:

1. Inspect task status.
2. Inspect worktree cleanliness.
3. Inspect task branch HEAD.
4. Read the last journal events.
5. Check whether the old agent owns the integration mutex.
6. Check whether a candidate worktree exists.

Do not create a duplicate implementation branch unless there is a concrete reason.

## Takeover

A takeover should:

- preserve the existing task ID;
- record the prior owner in owner history;
- assign a new agent ID;
- keep the task branch/worktree when safe;
- append a `handoff` or `takeover` event;
- re-run relevant verification before integration if the old agent's state is uncertain.

The helper focuses on normal single-owner execution. A takeover may require updating the task manifest manually or via a future helper extension. Follow the same single-owner invariant.

## Crash while holding integration lock

This is the most sensitive recovery case.

Inspect:

```text
locks/integration.lock/owner.json
integrations/<task-id>.json
candidate worktree
owner agent journal/status
```

Possible situations:

### Candidate has unresolved conflicts

Preserve it. Either reopen that worktree in a new Codex terminal or abort it intentionally.

### Candidate is validated but target not advanced

Re-check target SHA and tests before completing. Do not assume the old process had finished validation merely because the tree is clean.

### Candidate is corrupt/unwanted

Abort/remove it and return the task to ready.

## Breaking a stale lock

Use `lock-break` only with evidence. The command records an incident but deliberately does not pretend to know whether candidate cleanup is safe.

After a forced break, inspect all candidate worktrees before starting another integration.

## User interruption

If the user changes requirements while a task is active:

- if the change belongs to this task, update the task's objective/acceptance criteria and journal it;
- if it is a separate task, let another terminal own it;
- if it invalidates your task, stop and mark the task abandoned/superseded rather than integrating obsolete work.
