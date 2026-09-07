---
name: cooperative-worktree-agents
description: Coordinate many independent Codex CLI agents working concurrently in the same Git repository. Use when the user wants multiple terminals or agents to execute separate coding tasks in parallel, each in its own Git worktree and task branch, while sharing a cross-agent coordination ledger, soft file/area claims, decision and intent logs, serialized integration, and intent-aware merge-conflict resolution into staging or staging-derived branches. Also use when an agent must safely take over, inspect, integrate, or resolve conflicts with work produced by other independent agents.
---

# Cooperative Worktree Agents

Use this skill when multiple independent Codex CLI sessions are working on the same repository at the same time without a central orchestrator.

The core operating model is:

- one user task -> one agent -> one task branch -> one worktree;
- implementation is parallel;
- coordination is shared but decentralized;
- each agent owns and appends only to its own journal;
- file/area claims are advisory, not exclusive;
- integration into the shared target is serialized by one integration mutex;
- merge conflicts are resolved from both tasks' intent, contracts, diffs, and acceptance criteria, not from conflict markers alone;
- the shared operational target is `staging` or a branch derived from `staging`;
- `main` and `master` are outside the normal operational domain unless the user explicitly overrides that repository policy.

The user's explicit instructions take precedence over this skill. Do not let a generic skill rule override a clear task-specific instruction from the user.

## Required behavior

When assigned a coding task in a repository where other Codex agents may be active:

1. Discover the Git repository and shared coordination state.
2. Read the project objective, active tasks, relevant claims, and peer notes before making broad or shared changes.
3. Register yourself as an independent agent and register the task.
4. Create a dedicated task branch and worktree from the correct staging-domain target.
5. Do all implementation work only in that task worktree.
6. Publish concise operational context while working: intent, decisions, interfaces/contracts, touched areas, risks, tests, and integration concerns.
7. Never publish hidden chain-of-thought or private scratch reasoning. Record only durable engineering rationale and facts useful to another agent.
8. Test and commit the task branch.
9. Mark the task ready for integration only when the worktree is clean and verification evidence is recorded.
10. Acquire the shared integration mutex before touching the target branch or its integration checkout.
11. Integrate through a candidate worktree.
12. If conflicts occur, read the peer task manifests and journals that explain the conflicting work before resolving them.
13. Preserve both tasks' objectives whenever they are semantically compatible.
14. Validate the merged candidate.
15. Advance the target branch only after the candidate is clean and validated.
16. Release the mutex even when aborting integration.
17. Mark the task integrated and optionally clean up the task/candidate worktrees.

Do not turn yourself into a global scheduler for unrelated agents. Each terminal owns its assigned task and cooperates through the shared protocol.

## Shared state location

Store coordination state in the Git common directory so all linked worktrees see the same data without adding coordination files to project commits:

```text
<git-common-dir>/codex-team/
```

The helper script in `scripts/cwa.py` implements this layout. Read `references/shared-ledger.md` for the data model.

The ledger is public to peer agents in the same repository, not necessarily public on GitHub.

## Bootstrap

Prefer the deterministic helper script bundled with this skill.

From any checkout/worktree belonging to the repository, initialize the team state if it does not already exist:

```bash
python <skill-root>/scripts/cwa.py init --target staging
```

If the repository uses a staging-derived integration target for the current initiative, keep the project root target as `staging` and pass the more specific target when starting the task.

To start a task:

```bash
python <skill-root>/scripts/cwa.py start \
  --title "Add Google OAuth" \
  --objective "Allow users to authenticate with Google without breaking password login" \
  --target staging \
  --claim "src/auth/**" \
  --claim "src/pages/login/**" \
  --acceptance "Google sign-in works end to end" \
  --acceptance "Existing password login still works"
```

The command returns a unique `agent_id`, `task_id`, task branch, base SHA, and worktree path.

After task registration, treat the returned worktree as your execution root. If the current Codex process cannot change its own workspace root, use absolute paths under that worktree and prefix shell commands with `cd <worktree>` or use the helper's `--repo <worktree>` option. Never edit the original checkout for task implementation.

Read `references/task-lifecycle.md` for the full state machine.

## Before editing

Read the task context and active peers:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> status
python <skill-root>/scripts/cwa.py --repo <task-worktree> context
```

When you are about to modify a central/shared file or a path another agent may claim, query it explicitly:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> context \
  --path src/auth/UserIdentity.ts
```

Treat claims as warnings. They do not prohibit editing. If overlap exists, read the relevant peer journal and task manifest and adapt your implementation to known interfaces/decisions.

Read `references/shared-ledger.md` and `references/claims-and-context.md`.

## Publish useful coordination events

Append durable events while working. Examples:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type decision \
  --summary "Reuse SessionService for OAuth sessions instead of adding a parallel session abstraction" \
  --file src/auth/SessionService.ts
```

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type interface_change \
  --summary "User identity now supports providerType and providerId" \
  --file src/auth/UserIdentity.ts \
  --contract "UserIdentity(providerType, providerId)"
```

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type warning \
  --summary "Other tasks touching UserIdentity must preserve OAuth provider fields" \
  --file src/auth/UserIdentity.ts \
  --risk "Dropping provider fields breaks OAuth account lookup"
```

Record summaries that a peer can act on. Do not log private chain-of-thought, token-by-token reasoning, or speculative internal deliberation.

## Claims

Declare expected areas during `start`, and update them when scope changes:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> claim \
  --pattern "src/auth/**"
```

A claim means: "I am actively changing this area; read my context before making overlapping changes."

It does not mean: "other agents are forbidden from touching this area."

Only the integration mutex is a hard lock by default.

## Implementation discipline

Inside the task worktree:

- stay on the registered task branch;
- do not switch to the target branch;
- do not merge another task into your task branch merely to reduce anxiety about future conflicts;
- do not reset, clean, revert, or discard peer work;
- keep unrelated refactors out of the task;
- prefer explicit contracts when other active tasks depend on your work;
- check peer context before changing central registries, schemas, shared types, lockfiles, generated indexes, migrations, auth primitives, routing roots, or other high-collision files;
- commit only the assigned task's changes.

Read `references/worktrees-and-branches.md`.

## Ready for integration

After implementation and task-level verification, commit all intended changes and leave the task worktree clean.

Then record readiness:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> ready \
  --test "pytest tests/auth -q: PASS" \
  --test "npm run typecheck: PASS"
```

Do not claim a test passed unless you observed it pass.

The helper records the task HEAD and changed files. A dirty worktree cannot become ready.

## Integration protocol

Integration is the only serialized part of the workflow.

Begin integration:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> integrate-begin
```

This command:

- acquires the integration mutex atomically;
- verifies the target is in the staging domain;
- finds or creates a dedicated checkout for the target branch;
- refuses to proceed if the target checkout is dirty;
- snapshots the current target SHA;
- creates a temporary candidate branch/worktree from that exact SHA;
- merges the task branch into the candidate;
- leaves conflicts in the candidate worktree for the agent to resolve;
- keeps the authoritative target unchanged while validation is pending.

Do all conflict resolution and integration validation in the candidate worktree.

If there is no conflict, still run tests appropriate to the combined change before advancing the target.

Read `references/integration-protocol.md`.

## Conflict resolution

When `integrate-begin` reports conflicts:

1. Identify the conflicting files.
2. Query shared context for every conflicting file.
3. Read the manifests and journals of tasks whose work touched those files.
4. Inspect the relevant commits and diffs.
5. Reconstruct the durable intent of both sides from objective, acceptance criteria, decisions, contracts, and tests.
6. Resolve the conflict so both objectives survive when compatible.
7. Do not mechanically choose `ours` or `theirs` for a semantic conflict.
8. Record a `conflict_resolution` event explaining what was preserved from each side.
9. Run verification that covers both concerns.

Example:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> context \
  --path src/auth/UserIdentity.ts
```

Then record the resolution:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> event \
  --type conflict_resolution \
  --summary "Preserved OAuth provider identity fields from T-A while adding role fields required by this task" \
  --file src/auth/UserIdentity.ts
```

Read `references/conflict-resolution.md` before resolving non-trivial conflicts.

If the objectives themselves are incompatible, do not invent a product decision. Mark the task blocked and report the semantic conflict to the user.

## Finish integration

After conflicts are resolved, the candidate worktree is clean, and integration tests pass:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> integrate-finish \
  --test "pytest tests/auth tests/permissions -q: PASS"
```

The helper refuses to advance the target if:

- the integration lock is not owned by this task/agent;
- the candidate contains unresolved conflicts or uncommitted changes;
- the target checkout is dirty;
- the target SHA moved after the candidate was created.

If the target moved despite the lock, do not force it. Abort this candidate, re-read shared context, and retry from the new target state.

To abandon a candidate safely:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> integrate-abort
```

## Lock policy

The integration mutex is an atomic directory under the common coordination state.

Never bypass an active lock merely because another integration is inconvenient.

If a lock appears stale because an agent crashed, inspect its owner metadata and peer status first. Break a stale lock only when you have evidence that no integration process is active:

```bash
python <skill-root>/scripts/cwa.py lock-break \
  --reason "Agent A-1234 crashed; candidate worktree no longer has a live process and user requested recovery"
```

Every forced lock break is recorded as a recovery incident.

Read `references/integration-protocol.md` and `references/recovery-and-takeover.md`.

## Task takeover and abandoned agents

If an agent disappears, do not immediately duplicate its task. Inspect its task branch, worktree, status, journal, and latest commit first.

Use the takeover workflow only when the old agent is clearly abandoned or the user explicitly assigns the task to a new terminal.

The new agent should preserve the existing branch/worktree when safe, append a takeover event, and continue from durable state rather than restarting blindly.

Read `references/recovery-and-takeover.md`.

## Completion and cleanup

After successful integration, the task is complete when:

- the target contains the integrated task commit/candidate commit;
- required verification is recorded;
- the task status is `INTEGRATED`;
- the integration mutex has been released;
- important cross-agent decisions/conflict resolutions are in the ledger.

Optional cleanup:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> cleanup
```

Cleanup is allowed only after the task branch is confirmed integrated and the task worktree is clean.

## What to read when

Load references only as needed:

- `references/architecture.md` — mental model and invariants.
- `references/task-lifecycle.md` — task/agent state transitions.
- `references/shared-ledger.md` — storage layout and journal schema.
- `references/claims-and-context.md` — soft claims and peer awareness.
- `references/worktrees-and-branches.md` — branch/worktree ownership rules.
- `references/integration-protocol.md` — mutex, candidate worktree, target advancement.
- `references/conflict-resolution.md` — intent-aware conflict resolution.
- `references/recovery-and-takeover.md` — crash recovery, stale locks, handoff.
- `references/multi-terminal-usage.md` — practical workflows for many Codex terminals.
- `references/examples.md` — end-to-end examples.

## Helper script

`scripts/cwa.py` is a cross-platform Python 3 helper for deterministic coordination-state and Git operations. Prefer using it rather than recreating the same locking/state logic ad hoc.

Before relying on a modified copy of the helper, run:

```bash
python <skill-root>/scripts/test_cwa.py
```

The tests use disposable temporary Git repositories and do not touch the user's repository.
