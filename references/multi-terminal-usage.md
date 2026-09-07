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
10. marks itself integrated.

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
