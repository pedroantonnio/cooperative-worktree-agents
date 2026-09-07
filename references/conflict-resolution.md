# Intent-aware conflict resolution

## Principle

A Git conflict is a collision between textual histories. The correct resolution depends on the intended behavior of both tasks.

Do not reduce conflict resolution to choosing one side.

## Evidence hierarchy

Use this evidence, in order:

1. Latest explicit user instruction.
2. Task objectives and acceptance criteria.
3. Durable architectural/interface decisions recorded by the agents.
4. Current target behavior and contracts.
5. Task commits/diffs.
6. Tests that encode intended behavior.
7. Conflict markers as the mechanical location of the collision.

## Procedure

For each conflicting file:

### 1. Identify participating intents

Read:

- this task manifest;
- peer task manifests that changed or claimed the file;
- relevant peer journal events;
- changed-files records for already integrated tasks.

### 2. Inspect code history

Compare the task's base, task head, and current target.

Understand which side introduced each behavior.

### 3. Classify the conflict

Common classes:

- **additive** — both behaviors can coexist;
- **structural** — both tasks moved/refactored the same code and need a combined structure;
- **contract evolution** — one or both tasks changed an interface;
- **generated/lockfile** — regenerate from combined source-of-truth changes when possible;
- **migration ordering** — preserve both migrations with valid ordering/identifiers;
- **semantic incompatibility** — requirements cannot both be true.

### 4. Resolve

For additive/structural/contract conflicts, implement the combined behavior.

For generated files, prefer regenerating from the merged sources instead of manually splicing generated output.

For dependency lockfiles, merge the manifests first and regenerate the lockfile using the project's package manager when possible.

For migrations, never silently renumber or delete a migration without understanding repository conventions and whether it may already have been applied elsewhere.

### 5. Verify both concerns

Run tests that cover this task and the conflicting integrated task where practical.

### 6. Publish the resolution

Record a `conflict_resolution` event containing:

- conflicting task(s);
- affected files;
- behavior preserved from each side;
- tests run;
- any remaining risk.

## Semantic conflict

Example:

```text
Task A: Remove password authentication entirely.
Task B: Add password-reset functionality.
```

These requirements are incompatible without a product decision.

Do not decide based on which branch merged first. Mark the task `BLOCKED_SEMANTIC_CONFLICT` and ask the user which objective supersedes the other.

## Avoid `ours` / `theirs` shortcuts

Using `git checkout --ours` or `--theirs` for an entire conflict is acceptable only when evidence clearly says one side is intentionally obsolete. Record that decision and why.
