# Cooperative Worktree Agents

**Decentralized coordination for parallel Codex CLI agents using isolated Git worktrees, a shared engineering ledger, and intent-aware conflict resolution.**

Cooperative Worktree Agents is a Codex skill for running many independent Codex CLI sessions against the same Git repository at the same time â€” without requiring a central orchestrator.

Each terminal owns one task. Each task gets its own branch and Git worktree. Agents work in parallel, publish durable engineering context for one another, and integrate their own completed work through a serialized integration protocol.

The result is a cooperative multi-agent development model where agents remain independent during implementation but share enough context to safely handle overlapping files, evolving interfaces, and merge conflicts.

> This project is independent and community-maintained. It is not an official OpenAI or Codex project.

## Why this exists

Running several coding agents in parallel is easy until two of them touch related code.

Without coordination, independent agents can:

- overwrite or undo another agent's work;
- make incompatible architectural decisions;
- unknowingly change the same shared contract;
- resolve merge conflicts mechanically with `ours` or `theirs`;
- duplicate work already being performed elsewhere;
- integrate simultaneously and race on the shared branch;
- lose useful context when a terminal crashes.

Cooperative Worktree Agents addresses these problems without introducing a mandatory central scheduler.

```text
                         USER
                          â”‚
             â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
             â”‚            â”‚            â”‚
             â–¼            â–¼            â–¼
          Codex A      Codex B      Codex C
             â”‚            â”‚            â”‚
             â–¼            â–¼            â–¼
        Worktree A   Worktree B   Worktree C
        task/auth    task/billing task/dashboard
             â”‚            â”‚            â”‚
             â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                          â”‚
                          â–¼
               Shared Coordination Ledger
                          â”‚
                          â–¼
                  Integration Mutex
                          â”‚
                          â–¼
                 Candidate Integration
                          â”‚
                          â–¼
                       staging
```

## Core principles

- **One task = one agent = one branch = one worktree.**
- Implementation is parallel.
- Coordination is decentralized.
- Every agent can read the shared coordination state.
- Each agent appends only to its own journal.
- File and area claims are advisory, not exclusive locks.
- Durable intent and engineering decisions are shared; private chain-of-thought is not.
- Integration is serialized through a single mutex.
- Integration happens through a candidate worktree before the authoritative target advances.
- Merge conflicts are resolved from the intent of both tasks, not conflict markers alone.
- Semantically compatible objectives should both survive a conflict resolution.
- True requirement conflicts are escalated rather than guessed.
- `staging`, or a branch derived from `staging`, is the normal operational integration domain.
- `main` and `master` are outside the normal development workflow unless the user explicitly overrides that repository policy.

## What agents share

The coordination system records durable information another agent can act on:

- task objective;
- acceptance criteria;
- assigned agent;
- task branch and worktree;
- base and current commit SHAs;
- claimed files or areas;
- decisions;
- interface and contract changes;
- warnings and known risks;
- touched files;
- verification results;
- integration status;
- conflict-resolution notes;
- takeover and recovery events.

It intentionally does **not** require agents to publish hidden chain-of-thought or private scratch reasoning.

## Shared coordination ledger

Runtime coordination state is stored in the Git common directory:

```text
<git-common-dir>/codex-team/
â”œâ”€â”€ project.json
â”œâ”€â”€ tasks/
â”œâ”€â”€ agents/
â”œâ”€â”€ claims/
â”œâ”€â”€ decisions/
â”œâ”€â”€ events/
â””â”€â”€ locks/
```

All linked Git worktrees share the same common Git directory, so every agent can see this coordination state without adding it to application commits.

Each agent owns its journal. Everyone can read everyone else's journal.

Conceptually:

```text
agents/
â”œâ”€â”€ A-001/
â”‚   â”œâ”€â”€ status.json
â”‚   â””â”€â”€ journal.jsonl
â”œâ”€â”€ A-002/
â”‚   â”œâ”€â”€ status.json
â”‚   â””â”€â”€ journal.jsonl
â””â”€â”€ A-003/
    â”œâ”€â”€ status.json
    â””â”€â”€ journal.jsonl
```

This avoids having many agents concurrently append to one shared Markdown file.

## Requirements

- Git
- Python 3
- Codex CLI
- A repository with a `staging` branch, or another staging-derived integration target explicitly selected for the task

The helper is cross-platform and is intended to work on Windows, macOS, and Linux.

## Installation

Place this skill in a Codex-compatible skills directory.

Example:

```text
.agents/skills/cooperative-worktree-agents/
```

The directory should contain:

```text
cooperative-worktree-agents/
â”œâ”€â”€ SKILL.md
â”œâ”€â”€ agents/
â”‚   â””â”€â”€ openai.yaml
â”œâ”€â”€ assets/
â”‚   â””â”€â”€ task-prompt-template.md
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ cwa.py
â”‚   â””â”€â”€ test_cwa.py
â””â”€â”€ references/
    â”œâ”€â”€ architecture.md
    â”œâ”€â”€ claims-and-context.md
    â”œâ”€â”€ conflict-resolution.md
    â”œâ”€â”€ examples.md
    â”œâ”€â”€ integration-protocol.md
    â”œâ”€â”€ multi-terminal-usage.md
    â”œâ”€â”€ recovery-and-takeover.md
    â”œâ”€â”€ shared-ledger.md
    â”œâ”€â”€ task-lifecycle.md
    â””â”€â”€ worktrees-and-branches.md
```

## Quick start

Initialize coordination state once from a checkout belonging to the repository:

```bash
python <skill-root>/scripts/cwa.py init --target staging
```

Then open as many terminals as you need.

### Terminal A

```text
Use cooperative-worktree-agents.

Implement Google OAuth authentication.
Integrate the completed task into staging.
```

### Terminal B

```text
Use cooperative-worktree-agents.

Implement subscription billing.
Integrate the completed task into staging.
```

### Terminal C

```text
Use cooperative-worktree-agents.

Redesign the dashboard navigation.
Integrate the completed task into staging.
```

Each Codex session follows the same protocol independently.

## Task lifecycle

A typical task looks like this:

```text
assigned
   â”‚
   â–¼
register task + agent
   â”‚
   â–¼
create task branch + worktree
   â”‚
   â–¼
read active peer context
   â”‚
   â–¼
claim expected areas
   â”‚
   â–¼
implement
   â”‚
   â”œâ”€â”€ publish decisions
   â”œâ”€â”€ publish interface changes
   â”œâ”€â”€ publish warnings
   â””â”€â”€ inspect peers before shared edits
   â”‚
   â–¼
test
   â”‚
   â–¼
commit
   â”‚
   â–¼
mark READY
   â”‚
   â–¼
acquire integration mutex
   â”‚
   â–¼
create candidate integration worktree
   â”‚
   â–¼
merge task into candidate
   â”‚
   â”œâ”€â”€ clean merge â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
   â”‚                              â”‚
   â””â”€â”€ conflict                   â”‚
         â”‚                        â”‚
         â–¼                        â”‚
   read peer manifests/journals   â”‚
         â”‚                        â”‚
         â–¼                        â”‚
   resolve by intent              â”‚
         â”‚                        â”‚
         â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                    â”‚
                    â–¼
             integration tests
                    â”‚
                    â–¼
             advance target
                    â”‚
                    â–¼
              release mutex
                    â”‚
                    â–¼
                INTEGRATED
```

## Starting a task manually

The bundled helper can register a new task and create its branch/worktree:

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

The command returns values such as:

- `agent_id`;
- `task_id`;
- task branch;
- base SHA;
- task worktree path.

The agent performs implementation only inside that task worktree.

## Peer awareness before editing

Before broad or shared changes, inspect active work:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> status
```

Then load relevant context:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> context
```

For a specific file:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> context \
  --path src/auth/UserIdentity.ts
```

This lets an agent discover that another task is already modifying the same domain and understand what contracts or assumptions need to be preserved.

## Soft claims

Agents can declare areas they expect to modify:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> claim \
  --pattern "src/auth/**"
```

A claim means:

> Another agent is actively changing this area. Read its context before making overlapping changes.

A claim does **not** mean:

> Other agents are forbidden from touching this area.

This keeps the system cooperative instead of unnecessarily blocking parallelism.

## Publishing engineering context

Agents publish concise, durable events.

### Decision

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type decision \
  --summary "Reuse SessionService for OAuth sessions instead of adding a parallel session abstraction" \
  --file src/auth/SessionService.ts
```

### Interface change

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type interface_change \
  --summary "User identity now supports providerType and providerId" \
  --file src/auth/UserIdentity.ts \
  --contract "UserIdentity(providerType, providerId)"
```

### Warning

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> event \
  --type warning \
  --summary "Other tasks touching UserIdentity must preserve OAuth provider fields" \
  --file src/auth/UserIdentity.ts \
  --risk "Dropping provider fields breaks OAuth account lookup"
```

These records are designed to help another agent understand the implementation without requiring a central coordinator.

## Ready for integration

After implementation:

1. run the task-level tests;
2. commit all intended changes;
3. leave the task worktree clean;
4. record observed verification.

Example:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> ready \
  --test "pytest tests/auth -q: PASS" \
  --test "npm run typecheck: PASS"
```

A dirty task worktree cannot be marked ready.

## Serialized integration

Agents may implement concurrently, but only one agent integrates at a time.

Begin integration:

```bash
python <skill-root>/scripts/cwa.py --repo <task-worktree> integrate-begin
```

This operation:

- atomically acquires the integration mutex;
- reads the latest integration target;
- checks that the target checkout is clean;
- snapshots the current target SHA;
- creates a temporary candidate branch/worktree;
- merges the task branch into the candidate;
- leaves merge conflicts in the candidate for the agent to resolve;
- leaves the authoritative target unchanged while validation is pending.

This is the key separation:

```text
parallel implementation
+
serialized integration
```

## Intent-aware merge conflicts

When two agents modify the same file, the integrating agent should not resolve the conflict purely from:

```text
<<<<<<<
=======
>>>>>>>
```

Instead, it reconstructs both tasks' durable intent.

Read:

- the conflicting task manifests;
- both agents' journals;
- acceptance criteria;
- interface/contract changes;
- relevant commits;
- relevant diffs;
- verification evidence.

Then preserve both objectives whenever they are compatible.

Example:

```text
Task A:
Add Google OAuth identities.

Task B:
Add admin role information.

Conflict:
src/auth/UserIdentity.ts
```

A correct resolution might preserve both:

```text
UserIdentity
â”œâ”€â”€ OAuth provider identity
â””â”€â”€ authorization role
```

rather than simply choosing one side.

After resolving, record the resolution:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> event \
  --type conflict_resolution \
  --summary "Preserved OAuth provider fields from T-A while adding role fields required by T-B" \
  --file src/auth/UserIdentity.ts
```

Then run tests covering both concerns.

## Semantic conflicts

Not every conflict can be solved automatically.

Example:

```text
Task A:
Remove password authentication completely.

Task B:
Add password reset.
```

These requirements are logically incompatible.

The correct behavior is to block and ask for a product decision rather than inventing a winner.

## Finish integration

After the candidate is clean and validation succeeds:

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> integrate-finish \
  --test "pytest tests/auth tests/permissions -q: PASS"
```

The helper protects against several unsafe conditions, including:

- integration lock ownership mismatch;
- unresolved merge conflicts;
- dirty candidate state;
- dirty target checkout;
- target branch movement after candidate creation.

If the target unexpectedly moved, the agent aborts the candidate, refreshes context, and retries from the new target state.

## Abort integration safely

```bash
python <skill-root>/scripts/cwa.py --repo <candidate-worktree> integrate-abort
```

This removes the failed candidate state and releases integration ownership safely.

## Crash recovery

If an integrating terminal crashes, another agent should **not** immediately bypass the integration lock.

First inspect:

- lock owner metadata;
- task status;
- candidate worktree;
- agent journal;
- latest task commit;
- whether an integration process is actually still alive.

Only break a stale lock when there is evidence the previous integration is no longer active:

```bash
python <skill-root>/scripts/cwa.py lock-break \
  --reason "Previous integrating terminal crashed and no active integration process remains"
```

Forced lock breaks are recorded as recovery incidents.

## Agent takeover

If a task owner disappears, a new Codex session should inspect the existing branch, worktree, task manifest, journal, and commits before restarting anything.

Whenever safe, continue from the durable task state rather than duplicating the task.

## Helper commands

The main helper is:

```text
scripts/cwa.py
```

Important commands include:

| Command | Purpose |
| --- | --- |
| `init` | Initialize shared coordination state |
| `start` | Register an agent/task and create its isolated worktree |
| `status` | Show active/shared task state |
| `context` | Read relevant peer/task context |
| `event` | Publish a durable coordination event |
| `claim` | Declare an advisory file/area claim |
| `ready` | Mark a clean, tested task as ready |
| `integrate-begin` | Acquire the mutex and create the integration candidate |
| `integrate-finish` | Validate ownership and advance the target |
| `integrate-abort` | Abort a candidate safely |
| `lock-break` | Recover a proven stale integration lock |
| `block` | Mark a task blocked |
| `abandon` | Mark an abandoned task/agent |
| `cleanup` | Remove safe post-integration task resources |

Use:

```bash
python scripts/cwa.py --help
```

for command-level options.

## Multi-terminal workflow

A typical development session might look like:

```text
Terminal 1
â””â”€â”€ Codex
    â””â”€â”€ Google OAuth
        â””â”€â”€ task/T001-google-oauth
            â””â”€â”€ worktree T001

Terminal 2
â””â”€â”€ Codex
    â””â”€â”€ Billing retries
        â””â”€â”€ task/T002-billing-retries
            â””â”€â”€ worktree T002

Terminal 3
â””â”€â”€ Codex
    â””â”€â”€ Dashboard navigation
        â””â”€â”€ task/T003-dashboard-navigation
            â””â”€â”€ worktree T003

Terminal 4
â””â”€â”€ Codex
    â””â”€â”€ Email provider migration
        â””â”€â”€ task/T004-email-provider
            â””â”€â”€ worktree T004
```

All four agents implement concurrently.

When an agent finishes, it waits for or acquires the integration mutex, integrates its own task against the latest staging state, resolves any conflicts using the shared ledger, validates, and releases the mutex.

There is no mandatory global orchestrator.

## Branch model

The normal operational hierarchy is:

```text
main/master
    â†‘
    â”‚ outside normal agent development flow
    â”‚
staging
    â†‘
    â”‚
feature/* or other staging-derived integration targets
    â†‘
    â”‚
task/*
    â†‘
    â”‚
task worktrees
```

A repository may use a staging-derived target for a specific initiative:

```text
staging
â””â”€â”€ feature/billing
    â”œâ”€â”€ task/T001-schema
    â”œâ”€â”€ task/T002-provider
    â””â”€â”€ task/T003-dashboard
```

The task's target must remain in the authorized staging domain unless the user explicitly overrides that policy.

## Why not one central orchestrator?

A central orchestrator can be useful, but it creates a single coordination authority and can become a bottleneck.

This skill intentionally uses a cooperative distributed model:

```text
no central scheduler
+
isolated writers
+
shared durable context
+
one integration mutex
```

That means:

- the user can open many terminals and assign tasks directly;
- agents remain independent;
- one crashed agent does not stop unrelated work;
- integration still remains deterministic enough to protect the shared branch;
- new agents can recover context from durable state.

## Testing

The repository includes integration tests for the helper.

Run:

```bash
python scripts/test_cwa.py
```

The test suite uses disposable temporary Git repositories and does not modify your application repository.

It covers scenarios including:

- independent task worktrees;
- protected branch policy;
- candidate integration;
- authoritative target remaining unchanged before validation;
- successful integration;
- real merge conflicts;
- intent-aware conflict context;
- integration mutex behavior;
- safe mutex release.

## Repository structure

```text
cooperative-worktree-agents/
â”œâ”€â”€ SKILL.md
â”œâ”€â”€ README.md
â”œâ”€â”€ LICENSE
â”œâ”€â”€ CONTRIBUTING.md
â”œâ”€â”€ agents/
â”‚   â””â”€â”€ openai.yaml
â”œâ”€â”€ assets/
â”‚   â””â”€â”€ task-prompt-template.md
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ cwa.py
â”‚   â””â”€â”€ test_cwa.py
â””â”€â”€ references/
    â”œâ”€â”€ architecture.md
    â”œâ”€â”€ claims-and-context.md
    â”œâ”€â”€ conflict-resolution.md
    â”œâ”€â”€ examples.md
    â”œâ”€â”€ integration-protocol.md
    â”œâ”€â”€ multi-terminal-usage.md
    â”œâ”€â”€ recovery-and-takeover.md
    â”œâ”€â”€ shared-ledger.md
    â”œâ”€â”€ task-lifecycle.md
    â””â”€â”€ worktrees-and-branches.md
```

## Documentation

Detailed behavior is documented in:

- [`SKILL.md`](SKILL.md) â€” primary Codex instructions;
- [`references/architecture.md`](references/architecture.md) â€” architecture and invariants;
- [`references/task-lifecycle.md`](references/task-lifecycle.md) â€” task state machine;
- [`references/shared-ledger.md`](references/shared-ledger.md) â€” coordination-state model;
- [`references/claims-and-context.md`](references/claims-and-context.md) â€” advisory claims and peer awareness;
- [`references/worktrees-and-branches.md`](references/worktrees-and-branches.md) â€” ownership rules;
- [`references/integration-protocol.md`](references/integration-protocol.md) â€” mutex and candidate integration;
- [`references/conflict-resolution.md`](references/conflict-resolution.md) â€” intent-aware merges;
- [`references/recovery-and-takeover.md`](references/recovery-and-takeover.md) â€” crash recovery and task takeover;
- [`references/multi-terminal-usage.md`](references/multi-terminal-usage.md) â€” practical parallel workflows;
- [`references/examples.md`](references/examples.md) â€” end-to-end scenarios.

## Contributing

Contributions are welcome.

Please preserve the project's core properties:

- decentralized task ownership;
- isolated worktrees;
- durable cross-agent coordination;
- advisory claims instead of broad file locking;
- serialized integration;
- intent-aware conflict handling;
- staging-domain safety.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT License. See [`LICENSE`](LICENSE).
