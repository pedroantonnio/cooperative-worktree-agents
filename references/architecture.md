# Architecture

## Purpose

This skill implements decentralized cooperation among many independent Codex CLI sessions working in one Git repository.

There is no permanent root orchestrator. The user may open many terminals and assign one task to each Codex. Every agent owns its task from registration through integration.

The system separates three concerns:

1. **Parallel implementation** — each task has its own branch and worktree.
2. **Shared awareness** — agents publish durable context into a common ledger stored in the Git common directory.
3. **Serialized integration** — only one task at a time may advance a shared target branch.

## Mental model

```text
                    USER
          ┌──────────┼──────────┐
          │          │          │
          ▼          ▼          ▼
       Agent A    Agent B    Agent C
          │          │          │
          ▼          ▼          ▼
       WT/task-A  WT/task-B  WT/task-C
          │          │          │
          └──────┬───┴───┬──────┘
                 │       │
                 ▼       ▼
           shared coordination
                 ledger
                 │
                 ▼
          integration mutex
                 │
                 ▼
          target branch
```

## Invariants

### I1. One task has one owner at a time

One active agent owns one task branch/worktree. A takeover must be explicit and recorded.

### I2. Writers are isolated

An implementation agent edits only its own task worktree. It does not use the target branch worktree for ordinary implementation.

### I3. Coordination state is not project state

Coordination data lives under the Git common directory and is visible across worktrees without appearing in normal project commits.

### I4. Journals are single-writer

Each agent appends only to its own journal. Other agents may read it. This avoids concurrent writes to one global Markdown log.

### I5. Claims are soft

Claims communicate expected edit scope. They warn peers but do not block them.

### I6. Integration is hard-serialized

Only one agent may own the integration mutex at a time.

### I7. Integration is transactional

A task is first merged into a temporary candidate branch/worktree. The target branch advances only after conflicts are resolved and validation completes.

### I8. Conflict resolution is intent-aware

Conflict markers are insufficient evidence. Resolve from task objectives, acceptance criteria, decisions, interfaces, diffs, and tests.

### I9. No silent product arbitration

If two tasks encode incompatible user requirements, the agent must not invent which requirement wins. Report the semantic conflict.

### I10. The active branch is the default target

When a task starts, the helper records the local branch currently checked out as that task's integration target unless `--target` explicitly selects another local branch. `main`, `master`, feature branches, release branches, and other local branches are treated uniformly. An already-running task keeps its recorded target even if the primary checkout later switches branches.

## Why a common Git directory

Linked worktrees have separate working directories but share the repository's common Git metadata. Storing the ledger beneath that common directory gives every agent the same coordination state regardless of which worktree it currently uses.

Typical layout:

```text
repo/.git/codex-team/
```

or, for unusual Git layouts, the absolute path returned by:

```bash
git rev-parse --git-common-dir
```

## Why not one shared log file

One shared append-only file looks simple but becomes its own concurrency hotspot. Separate per-agent journals provide:

- one writer per file;
- lower corruption/interleaving risk;
- clear provenance;
- easy recovery after a terminal dies;
- simple filtering by task or agent.

## Why candidate integration

Merging directly into the target branch means a conflict can leave the authoritative integration checkout in an unresolved state. A candidate worktree isolates that risk.

The protocol is:

```text
current target SHA
      │
      ▼
candidate branch/worktree
      │
      + merge task branch
      │
      + resolve conflicts
      │
      + integration tests
      │
      ▼
validated candidate
      │
      ▼
fast-forward target while lock is held
```

If anything fails, the target remains unchanged.

## Human authority

The user remains the product authority. Agents autonomously resolve implementation conflicts when the requirements are compatible. They escalate incompatible requirements, destructive choices, or decisions that require product intent not present in the task context.
