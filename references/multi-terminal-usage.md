# Multi-terminal usage

## Intended workflow

The user opens multiple terminals and starts one Codex CLI session per task.

Example:

```text
Terminal 1 -> "Implement Google OAuth"
Terminal 2 -> "Implement billing webhooks"
Terminal 3 -> "Redesign the dashboard"
Terminal 4 -> "Move email delivery to Resend"
```

Each Codex uses this skill independently.

## What each terminal does

Each agent:

1. registers its task;
2. creates its own branch/worktree;
3. reads active peer context;
4. implements independently;
5. publishes durable coordination events;
6. commits and tests;
7. waits only for the integration mutex, not for unrelated implementation;
8. integrates itself;
9. resolves integration conflicts using peer context;
10. verifies that the integrated target has been handed back to the configured primary project folder;
11. runs mandatory cleanup for its task and candidate worktrees from the primary folder;
12. only then reports final completion.

## No central scheduler

Agents do not need permission from a root agent to start ordinary independent tasks.

The user can decide what to launch and when. The ledger provides enough shared state for each agent to cooperate locally.

## Recommended task prompts

Good task prompt:

```text
Use cooperative-worktree-agents. Implement Google OAuth end-to-end while preserving existing password login. Own this task completely: create your worktree, coordinate with active peer agents, test, commit, and integrate into staging. Resolve compatible conflicts yourself using the shared ledger.
```

Another:

```text
Use cooperative-worktree-agents. Replace our email delivery adapter with Resend. Work independently in your own worktree, publish decisions/interfaces that can affect peers, and integrate the finished task into staging.
```

## Terminal that starts outside a task worktree

A Codex session can call `start` from the repository checkout. The helper returns a task worktree path.

From that point the agent must treat that path as the only implementation root. Shell commands should use `cd <path>` or helper `--repo <path>`. Editing tools should target files under that worktree, not the original checkout.

If the user's Codex CLI setup supports starting with a working-directory option, an alternative is to bootstrap the task/worktree first and launch Codex directly in the returned worktree.

If the generated worktree does not contain the cooperative skill because the installation is untracked or a nested repository, continue invoking the helper from the absolute helper_path returned by start and pass --repo with the task worktree.

If cwa.py start fails with cannot lock ref, a refs/heads lock path, and Permission denied, the Codex sandbox is blocking Git metadata writes. Request elevated or user-approved execution for that exact CWA operation. Never fall back to implementing in the shared checkout.

To see what cooperative agents are doing and where they are working, run:

python ABSOLUTE_CWA_PATH --repo PRIMARY_CHECKOUT status

For machine-readable owner, branch, worktree and claims, run:

python ABSOLUTE_CWA_PATH --repo PRIMARY_CHECKOUT status --json

This is the preferred source of truth instead of inferring task ownership from process IDs.

## Dirty primary checkout is not a reason to stop

An integration refusal is not permission for the terminal to give up.

The nested cooperative skill is ignored as local tooling when appropriate.

Preexisting work in the configured primary project folder is automatically copied into a preservation worktree and verified before the primary folder is cleared for integration. CWA does not stash or commit that work.

After the candidate is validated and integrated, the target is handed back to the primary folder. The agent then runs cleanup from that primary folder and only after cleanup reports completion.

Unknown dirty changes in a separate non-primary target worktree remain a safety block and must be reported rather than discarded.

## Watching peers

Agents do not need to continuously poll each other. Query context at meaningful coordination points:

- before touching a central file;
- after discovering a new shared interface;
- before marking ready;
- when integration conflicts occur;
- when the target changed substantially since task start.

## Integration contention

If another agent owns the mutex, do not spin destructively. Continue task-local checks/documentation if useful, then retry later.

The mutex serializes only integration, so implementation throughput remains high.
