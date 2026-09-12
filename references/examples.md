# Examples

## Example 1: independent tasks with no conflict

Three terminals start from the same currently active target branch:

```text
A -> Google OAuth
B -> Billing webhook retries
C -> Dashboard charts
```

All create separate worktrees and work concurrently.

C finishes first, acquires the integration mutex, creates a candidate, validates, and advances the recorded target branch.

A finishes next. Its candidate starts from the newer target branch containing C. No overlapping files exist, so integration succeeds.

B integrates last.

No agent needed a central orchestrator.

## Example 2: overlapping auth tasks

A owns:

```text
objective: Google OAuth
claim: src/auth/**
```

B owns:

```text
objective: Admin roles
claim: src/auth/**
```

A records:

```text
interface_change:
UserIdentity gains providerType/providerId.
```

A integrates first.

When B integrates, `UserIdentity.ts` conflicts. B queries context for the file and sees A's interface change.

B resolves the file to retain OAuth identity fields and add role fields. B runs both auth and permissions tests and records a conflict-resolution event.

## Example 3: lockfile conflict

A adds package `openid-client`.
B adds package `resend`.

Both change `package.json` and `package-lock.json`.

A integrates first.

B's candidate conflicts in the manifests/lockfile. B combines both manifest dependencies and regenerates the lockfile with the repository's package manager rather than hand-splicing the generated lockfile.

## Example 4: semantic conflict

A task objective says:

```text
Remove password authentication.
```

An older active task says:

```text
Add password reset.
```

The later integrating agent identifies that both outcomes cannot make sense simultaneously. It records `BLOCKED_SEMANTIC_CONFLICT` and asks the user which requirement supersedes the other.

## Example 5: crashed integrator

Agent A acquires the mutex and encounters conflicts, then its terminal crashes.

Agent B sees the lock and does not bypass it. The user starts a recovery terminal. It reads the lock owner, A's integration session and journal, then resumes or aborts A's candidate. Only after that state is made explicit is the mutex released/broken.
