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

## Never implement in the target checkout

The target checkout exists for serialized integration only. It must remain clean between integrations.

If the user is manually editing the checkout where `staging` is checked out, integration must stop until that working tree is clean or the user establishes a dedicated integration checkout.

## Do not switch branches inside an owned worktree

The task worktree stays on its task branch. The candidate worktree stays on its candidate branch. The integration checkout stays on the target branch.

Avoiding branch switching makes ownership visible and reduces accidental cross-task edits.

## Do not synchronize by merging peers into task branches

Do not routinely merge or rebase other active task branches into your branch. That distributes integration decisions across agents and makes later conflict provenance harder to understand.

Let isolated tasks diverge. Reconcile them under the integration mutex against the current target.

## Remote synchronization

The skill governs local cooperative development. Fetching is safe when needed. Pushing task or target branches is repository-policy dependent and should follow the user's explicit workflow.

Do not assume that every local integration must immediately push to a remote.
