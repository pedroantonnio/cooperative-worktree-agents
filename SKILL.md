---
name: cooperative-worktree-agents
description: Coordinate many independent Codex CLI agents working concurrently in the same Git repository. Use when the user wants multiple terminals or agents to execute separate coding tasks in parallel, each in its own Git worktree and task branch, while sharing a cross-agent coordination ledger, soft file/area claims, decision and intent logs, serialized integration, and intent-aware merge-conflict resolution back into each task's recorded target branch. Also use when an agent must safely take over, inspect, integrate, or resolve conflicts with work produced by other independent agents.
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
- each new task normally uses the branch currently checked out when the task starts as its integration target;
- `main`, `master`, feature branches, release branches, and other local branches are all valid targets.

The user's explicit instructions take precedence over this skill. Do not let a generic skill rule override a clear task-specific instruction from the user.

## Required behavior

When assigned a coding task in a repository where other Codex agents may be active:

1. Discover the Git repository and shared coordination state.
2. Read the project objective, active tasks, relevant claims, and peer notes before making broad or shared changes.
3. Register yourself as an independent agent and register the task.
4. Create a dedicated task branch and worktree from the branch currently checked out when the task starts, unless the user explicitly selected another target.
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
python <skill-root>/scripts/cwa.py init
```

Initialization records shared coordination state. At task start, the default integration target is the branch currently checked out. Use `--target <branch>` only for an intentional override.

To start a task:

```bash
python <skill-root>/scripts/cwa.py start \
  --title "Add Google OAuth" \
  --objective "Allow users to authenticate with Google without breaking password login" \
  --claim "src/auth/**" \
  --claim "src/pages/login/**" \
  --acceptance "Google sign-in works end to end" \
  --acceptance "Existing password login still works"
```

The command returns a unique agent_id, task_id, task branch, base SHA, worktree path, helper_path, and skill_root.

After task registration, treat the returned worktree as your execution root. If the current Codex process cannot change its own workspace root, use absolute paths under that worktree and prefix shell commands by changing directory to the worktree or use the helper with --repo pointing to the worktree. Never edit the original checkout for task implementation.

### Codex managed sandbox Git permission errors

Creating a task branch and worktree requires writes inside the repository common Git directory, including refs/heads lock files and worktree administration metadata.

Some Codex managed sandboxes allow ordinary source-file writes but expose the common .git directory as read-only.

The characteristic error contains all of the following:

fatal: cannot lock ref refs/heads/...
Unable to create a .git/refs/heads/...lock file
Permission denied

When this happens:

1. Do not implement in the shared or target checkout.
2. Do not bypass CWA with ad-hoc Git branch or worktree commands.
3. Re-run the exact same cwa.py start command using the Codex execution tool elevated or user-approved mode that permits Git metadata writes.
4. Elevation is a permission of the execution tool, not a cwa.py command-line flag.
5. Once start succeeds, continue exclusively inside the returned task worktree.

The helper emits explicit recovery guidance when this failure signature is detected.

### Windows encoding and Git metadata preflight

The helper's coordination files, diagnostics, and JSON output are UTF-8. Preserve
that invariant when invoking it from PowerShell or another terminal:

- do not copy status, titles, paths, or event text after accented characters have
  been corrupted;
- if the terminal displays corrupted text, stop and correct the execution
  encoding before publishing a ledger event;
- if Git metadata is denied by a managed sandbox, rerun the exact CWA command in
  the elevated/user-approved execution context described above; never replace
  `cwa.py` with ad-hoc `git worktree` or direct-checkout operations.

The helper's regression suite includes a non-ASCII task title and must be run
after changes to its subprocess or output handling.

### Primary checkout preservation and automatic recovery

The configured primary project folder is the authoritative finished checkout. Task worktrees and candidate worktrees are temporary implementation and integration areas.

If the primary folder contains preexisting tracked or untracked user work when integration begins, the helper must not abandon the task and must not require the user to manually clean the folder first.

The helper automatically:

1. snapshots staged changes, unstaged changes, and non-tooling untracked files;
2. reproduces them in a dedicated preserved worktree under the configured worktree root;
3. verifies the preserved staged diff, unstaged diff, and status before changing the primary folder;
4. clears only the exact changes that were successfully reproduced;
5. continues integration against a clean target checkout;
6. after successful validation, returns the integrated target branch and exact integrated SHA to the configured primary project folder;
7. attaches the preserved worktree to its preservation branch so the previous user work remains available separately.

No automatic stash is used. Unknown work is never discarded. A preservation mismatch fails closed before the primary checkout is cleared.

A task is not complete merely because a task branch or candidate contains the code. Successful integration must end with the primary project folder on the target branch at the integrated SHA.

### Skill directory can be absent from a generated task worktree

A Git worktree contains files committed in the selected target revision.

If cooperative-worktree-agents is installed in the primary checkout as an untracked directory or as a nested Git repository, the generated task worktree will not contain the skill directory. That is expected.

Use the absolute helper_path returned by start and pass --repo with the task worktree path.

Example:

python C:/Programacao/Uncuty/.agents/SKILLS/cooperative-worktree-agents/scripts/cwa.py --repo C:/path/to/task-worktree status

The shared ledger still works because it lives in the repository common Git directory.

Read `references/task-lifecycle.md` for the full state machine.

## Before editing

Read the task context and active peers:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> status
python <skill-root>/scripts/cwa.py --repo <task-worktree> context
```

When the ledger contains historical or completed tasks, narrow the view before
making decisions:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> status --active
python <skill-root>/scripts/cwa.py --repo <task-worktree> status --target <target-branch> --json
python <skill-root>/scripts/cwa.py --repo <task-worktree> status --task <task-id> --json
```

`--active` excludes terminal tasks (`INTEGRATED` and `ABANDONED`), while
`--target` and `--task` are exact filters. Use the filtered output when the
unfiltered ledger is too large to review safely.

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

`--test` records evidence; it does not execute the command. Include the exact
command, its observed native exit code, and the result in each entry, for example:

```text
command=node --test tests/auth.test.mjs; exit_code=0; result=PASS
```

Do not use a bare `PASS`, a copied log fragment, or a command that was only
planned as verification. Record `FAIL` or `BLOCKED` when that is what the
observed exit code or external dependency produced.

For native commands, observe the real process exit code. In PowerShell, ErrorActionPreference does not by itself turn a failing native executable into a terminating PowerShell error. Agents must inspect the native exit status or use an execution wrapper that fails on a nonzero native exit code. Output text that merely contains a command invocation is not PASS evidence.

integrate-finish requires at least one combined-state verification entry.

The helper records the task HEAD and changed files. A dirty worktree cannot become ready.

## Integration protocol

Integration is the only serialized part of the workflow.

Begin integration:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> integrate-begin
```

This command:

- acquires the integration mutex atomically;
- verifies the recorded target is an existing local branch;
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

After successful integration, the task may be reported complete only when:

- the target contains the validated candidate;
- the configured primary project folder is on that target branch at the exact integrated SHA;
- any preexisting primary work was preserved in its recorded preservation worktree;
- required verification is recorded from commands whose real native exit codes were observed;
- the task status is INTEGRATED;
- the integration mutex has been released;
- important cross-agent decisions and conflict resolutions are in the ledger;
- task and candidate worktrees have been cleaned with the cleanup command.

Required cleanup from the primary project folder:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> cleanup
```

Cleanup is required before the agent reports final completion. Run it from the configured primary project folder with the task ID. It removes the integrated task and candidate worktrees and their temporary branches only after ancestry and cleanliness checks pass.

Keep the cleanup result as evidence. A successful cleanup reports
`cleanup_complete: true`, the removed worktrees and branches, the final target
HEAD, and a free integration lock (`integration_lock: null`). If the command
does not produce that confirmation, inspect the exit code and CWA status before
reporting completion.

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
