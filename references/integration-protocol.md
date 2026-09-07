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

`integrate-begin` performs these operations under the lock:

1. Verify the task is `READY_FOR_INTEGRATION`.
2. Acquire the mutex.
3. Verify the target is allowed and in the staging domain.
4. Locate an existing worktree with the target branch checked out, or create a dedicated one.
5. Verify that target worktree is clean.
6. Record the current target SHA as `target_sha_before`.
7. Create a unique candidate branch from that SHA.
8. Create a unique candidate worktree.
9. Merge the task branch into the candidate with a normal merge commit.
10. Record conflict files or successful merge state.

The target branch is not modified during this step.

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

`integrate-finish` checks:

- lock ownership;
- no unresolved files;
- no pending merge without a completed commit;
- candidate worktree clean;
- target checkout clean;
- current target SHA still equals `target_sha_before`;
- candidate descends from `target_sha_before`.

Then it fast-forwards the target checkout to the candidate branch.

This final fast-forward is intentionally simple. All complex merge work already occurred in the candidate.

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
