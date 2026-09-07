# Claims and peer context

## Soft claims

A claim communicates expected edit scope. Examples:

```text
src/auth/**
src/pages/login/**
packages/db/schema/**
package-lock.json
```

Claims are deliberately advisory. Strict file locks would serialize too much ordinary development and cause agents to block on harmless overlap.

## When to query context

Always query peer context before changing high-collision artifacts such as:

- authentication/user primitives;
- database schemas and migrations;
- dependency manifests and lockfiles;
- generated schemas or central generated indexes;
- root routing tables;
- service registries;
- global configuration;
- shared domain types;
- API contracts used by multiple active tasks;
- central state-management stores;
- files already claimed by another active agent.

## Context algorithm

For a path you intend to modify:

1. Scan active task claims.
2. Find integrated tasks that recently changed the same path.
3. Find journal events that explicitly name the path.
4. Read the relevant task objective and acceptance criteria.
5. Preserve known contracts unless your task explicitly supersedes them.
6. Publish a scope/interface event if your own change will affect peers.

The helper performs the discovery step:

```bash
python <skill-root>/scripts/cwa.py --repo <worktree> context --path path/to/file
```

## Claim overlap is not a conflict by itself

Two agents may legitimately edit the same subsystem. A claim overlap means coordination cost is higher, not that one agent must stop.

Example:

```text
A: src/auth/** — Google OAuth
B: src/auth/** — Admin roles
```

Both tasks can proceed in isolated worktrees. They should publish interface changes and expect an intent-aware integration conflict if they touch the same lines.

## Scope changes

If your implementation expands into a new area, update your claims and emit a `scope_change` event before making broad edits there when practical.

## Central files

For highly centralized files, consider minimizing the duration of divergence. A task can defer the central registration edit until the end of its implementation, after re-reading peer context. Do not merge peer branches into the task branch merely to synchronize; integration remains the place where histories meet.
