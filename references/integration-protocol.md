# Integration protocol

## Goal

Allow many agents to implement concurrently while guaranteeing that only one agent at a time mutates the shared integration target.

## The mutex

The mutex is represented by an atomically created directory:

```text
<git-common-dir>/codex-team/locks/integration.lock/
```

Directory creation is used because it is atomic on normal local filesystems and works across platforms.

The lock contains `owner.json` with:

- task ID;
- agent ID;
- target branch;
- timestamp;
- process information when available.

## Begin

integrate-begin performs these operations under the lock:

1. Verify the task is READY_FOR_INTEGRATION.
2. Acquire the mutex.
3. Verify the recorded target is an existing local branch.
4. Inspect the configured primary project folder.
5. If that primary folder contains preexisting work, reproduce staged, unstaged, and non-tooling untracked state in a preserved worktree and verify the reproduction before clearing the primary folder.
6. Locate or create the temporary target integration checkout.
7. Record the current target SHA.
8. Create the candidate branch and candidate worktree.
9. Merge the task branch into the candidate.
10. Record conflicts or successful merge state.

The target branch is not advanced during candidate creation. The primary folder is never used as an implementation worktree.

## Candidate validation

The candidate is the only place where integration conflicts are resolved and combined-state tests are run.

Do not run destructive cleanup in the target checkout while a candidate exists.

If the merge has conflicts:

- read cross-agent context;
- resolve files;
- stage changes;
- complete the merge commit;
- run integration tests;
- record the resolution.

If the merge has no textual conflicts, still consider semantic conflicts caused by target changes since the task's base SHA.

Useful inspection:

```bash
git log --oneline <task-base>..<current-target>
git diff <task-base>...<task-head>
git diff <task-base>...<current-target>
```

## Finish

integrate-finish requires real combined-state verification evidence and checks the candidate, mutex, ancestry, target state, and verification results supplied by the agent.

After the target is advanced to the validated candidate, integration is still not complete until the helper performs the primary handoff.

The primary handoff guarantees:

- the configured primary project folder ends on the target branch;
- its HEAD equals the integrated candidate SHA;
- temporary dedicated target worktrees are detached and removed when CWA created them;
- preserved preexisting work is attached to its preservation branch in a separate worktree;
- a handoff failure keeps the integration incomplete instead of falsely reporting success.

The operation is retry-safe when the target ref already equals the validated candidate HEAD after a partially completed finish.

After integrate-finish, the agent must run cleanup from the primary project folder with the task ID before reporting final completion.

## Target moved unexpectedly

If the target changed after candidate creation, another process violated the mutex or the user changed the target externally.

Do not force-push, reset, or overwrite the target.

Abort the candidate, release the lock, inspect the new target, and retry integration from the new SHA.

## Abort

`integrate-abort` removes the candidate worktree/branch where safe, returns the task to `READY_FOR_INTEGRATION`, and releases the mutex.

Use it when:

- target moved;
- conflict resolution becomes unclear;
- verification fails and the fix belongs on the task branch;
- a user asks to change the task before integration;
- the integration attempt is otherwise no longer valid.

## Lock recovery

A stale lock must be handled carefully.

Before breaking it:

1. inspect `owner.json`;
2. inspect the recorded integration session;
3. inspect the candidate worktree;
4. inspect the owner agent heartbeat/journal;
5. determine whether an integration process is still active;
6. prefer user confirmation when evidence is ambiguous.

`lock-break` records an incident. It does not automatically delete candidate worktrees because those may contain valuable conflict resolution work.

## Dirty primary and target recovery

A dirty primary checkout is handled by preservation, not abandonment.

The helper copies and verifies staged, unstaged, and non-tooling untracked work into a dedicated preservation worktree before clearing the primary checkout. It does not use stash and does not discard unknown files.

If exact preservation cannot be verified, integration fails closed before destructive cleanup.

A genuinely dirty target integration checkout that is not the configured primary folder still blocks integration because its ownership is ambiguous. That block is recoverable and must never be treated as task abandonment.
