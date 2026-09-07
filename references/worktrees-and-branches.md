# Worktrees and branches

## Ownership

Each active task owns exactly one task branch and one primary task worktree.

Example:

```text
staging
├── task/t-001-google-oauth      -> worktree A
├── task/t-002-billing-webhooks  -> worktree B
└── task/t-003-dashboard         -> worktree C
```

## Base selection

The task base must be the integration target relevant to that task.

Allowed normal targets:

- `staging`;
- `feature/*`, `integration/*`, or another local branch whose history descends from `staging`.

The helper rejects `main` and `master` as normal targets.

A staging-derived target is valid only if:

```bash
git merge-base --is-ancestor staging <target>
```

succeeds.

## Exact base SHA

Task creation records the exact target SHA. Do not silently rewrite it later.

This lets the integrating agent distinguish:

- changes made by the task;
- changes that landed on the target while the task was active.

## Worktree root

By default, the helper keeps task worktrees outside the project checkout under a sibling directory similar to:

```text
<repo-parent>/.codex-worktrees/<repo-name>/
```

This prevents task worktrees from appearing as untracked project directories.

A task worktree contains only files present in the selected target commit. If the cooperative skill is installed in the primary checkout as an untracked directory or nested Git repository, it will not appear inside the generated task worktree. This is expected.

The start command returns absolute helper_path and skill_root values so the task can continue using the same helper with --repo pointing at its worktree.

## Git metadata permissions

git worktree add must create a task branch ref and worktree administration metadata inside the repository common Git directory.

In a managed sandbox, write permission to normal project files does not imply write permission to .git.

If task creation fails with cannot lock ref, a refs/heads lock path, and Permission denied, request elevated or user-approved execution for the exact cooperative helper command.

Do not bypass the failure by editing the target checkout, inventing a branch outside the ledger, or disabling the one-task one-worktree invariant.

## Primary folder is the final authoritative checkout

Never implement directly in the target checkout. Task and candidate worktrees are temporary.

The configured primary project folder is different: it is the location where the final integrated target must be visible after integration finishes.

If that primary folder contains preexisting work, CWA parks and verifies that work in a preservation worktree, performs integration separately, then returns the integrated target to the primary folder.

Therefore a finished task must never leave the newest product state only inside a task, candidate, or temporary integration worktree.

A non-primary target worktree with unknown dirty changes still blocks integration until ownership is resolved.

## Do not switch branches inside an owned worktree

The task worktree stays on its task branch. The candidate worktree stays on its candidate branch. The integration checkout stays on the target branch.

Avoiding branch switching makes ownership visible and reduces accidental cross-task edits.

## Do not synchronize by merging peers into task branches

Do not routinely merge or rebase other active task branches into your branch. That distributes integration decisions across agents and makes later conflict provenance harder to understand.

Let isolated tasks diverge. Reconcile them under the integration mutex against the current target.

## Remote synchronization

The skill governs local cooperative development. Fetching is safe when needed. Pushing task or target branches is repository-policy dependent and should follow the user's explicit workflow.

Do not assume that every local integration must immediately push to a remote.
