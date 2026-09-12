# Cooperative Worktree Agents

**Decentralized coordination for parallel Codex CLI agents using isolated Git worktrees, a shared engineering ledger, and intent-aware conflict resolution.**

Cooperative Worktree Agents is a Codex skill for running many independent Codex CLI sessions against the same Git repository at the same time — without requiring a central orchestrator.

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
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
          Codex A      Codex B      Codex C
             │            │            │
             ▼            ▼            ▼
        Worktree A   Worktree B   Worktree C
        task/auth    task/billing task/dashboard
             │            │            │
             └────────────┼────────────┘
                          │
                          ▼
               Shared Coordination Ledger
                          │
                          ▼
                  Integration Mutex
                          │
                          ▼
                 Candidate Integration
                          │
                          ▼
                  recorded target branch
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
- The branch currently checked out when a task starts is its normal integration target.
- `main`, `master`, feature branches, release branches, and other local branches are valid targets.

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
├── project.json
├── tasks/
├── agents/
├── claims/
├── decisions/
├── events/
└── locks/
```

All linked Git worktrees share the same common Git directory, so every agent can see this coordination state without adding it to application commits.

Each agent owns its journal. Everyone can read everyone else's journal.

Conceptually:

```text
agents/
├── A-001/
│   ├── status.json
│   └── journal.jsonl
├── A-002/
│   ├── status.json
│   └── journal.jsonl
└── A-003/
    ├── status.json
    └── journal.jsonl
```

This avoids having many agents concurrently append to one shared Markdown file.

## Requirements

- Git
- Python 3
- Codex CLI
- A Git repository with a local branch checked out for the work being coordinated

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
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── task-prompt-template.md
├── scripts/
│   ├── cwa.py
│   └── test_cwa.py
└── references/
    ├── architecture.md
    ├── claims-and-context.md
    ├── conflict-resolution.md
    ├── examples.md
    ├── integration-protocol.md
    ├── multi-terminal-usage.md
    ├── recovery-and-takeover.md
    ├── shared-ledger.md
    ├── task-lifecycle.md
    └── worktrees-and-branches.md
```

## Quick start

Initialize coordination state once from a checkout belonging to the repository:

```bash
python <skill-root>/scripts/cwa.py init
```

Then open as many terminals as you need.

### Terminal A

```text
Use cooperative-worktree-agents.

Implement Google OAuth authentication.
Integrate the completed task back into its recorded target branch.
```

### Terminal B

```text
Use cooperative-worktree-agents.

Implement subscription billing.
Integrate the completed task back into its recorded target branch.
```

### Terminal C

```text
Use cooperative-worktree-agents.

Redesign the dashboard navigation.
Integrate the completed task back into its recorded target branch.
```

Each Codex session follows the same protocol independently.

## Task lifecycle

A typical task looks like this:

```text
assigned
   │
   ▼
register task + agent
   │
   ▼
create task branch + worktree
   │
   ▼
read active peer context
   │
   ▼
claim expected areas
   │
   ▼
implement
   │
   ├── publish decisions
   ├── publish interface changes
   ├── publish warnings
   └── inspect peers before shared edits
   │
   ▼
test
   │
   ▼
commit
   │
   ▼
mark READY
   │
   ▼
acquire integration mutex
   │
   ▼
create candidate integration worktree
   │
   ▼
merge task into candidate
   │
   ├── clean merge ───────────────┐
   │                              │
   └── conflict                   │
         │                        │
         ▼                        │
   read peer manifests/journals   │
         │                        │
         ▼                        │
   resolve by intent              │
         │                        │
         └────────────────────────┘
                    │
                    ▼
             integration tests
                    │
                    ▼
             advance target
                    │
                    ▼
              release mutex
                    │
                    ▼
                INTEGRATED
```

## Starting a task manually

The bundled helper can register a new task and create its branch/worktree:

```bash
python <skill-root>/scripts/cwa.py start \
  --title "Add Google OAuth" \
  --objective "Allow users to authenticate with Google without breaking password login" \
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
├── OAuth provider identity
└── authorization role
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
└── Codex
    └── Google OAuth
        └── task/T001-google-oauth
            └── worktree T001

Terminal 2
└── Codex
    └── Billing retries
        └── task/T002-billing-retries
            └── worktree T002

Terminal 3
└── Codex
    └── Dashboard navigation
        └── task/T003-dashboard-navigation
            └── worktree T003

Terminal 4
└── Codex
    └── Email provider migration
        └── task/T004-email-provider
            └── worktree T004
```

All four agents implement concurrently.

When an agent finishes, it waits for or acquires the integration mutex, integrates its own task against the latest state of its recorded target branch, resolves any conflicts using the shared ledger, validates, and releases the mutex.

There is no mandatory global orchestrator.

## Branch model

The normal operational hierarchy is:

```text
active local target branch
    |
    +-- task/*
    |    +-- isolated task worktrees
    |
    +-- temporary candidate integration worktrees
```

A repository may coordinate work from any local branch, including `main`, `master`, feature branches, release branches, or other initiative branches. The branch currently checked out when `start` runs is selected by default; `--target <branch>` is an explicit override.

Each task records its target branch when it starts. Switching the primary checkout later does not silently retarget an existing task.

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
├── SKILL.md
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── agents/
│   └── openai.yaml
├── assets/
│   └── task-prompt-template.md
├── scripts/
│   ├── cwa.py
│   └── test_cwa.py
└── references/
    ├── architecture.md
    ├── claims-and-context.md
    ├── conflict-resolution.md
    ├── examples.md
    ├── integration-protocol.md
    ├── multi-terminal-usage.md
    ├── recovery-and-takeover.md
    ├── shared-ledger.md
    ├── task-lifecycle.md
    └── worktrees-and-branches.md
```

## Documentation

Detailed behavior is documented in:

- [`SKILL.md`](SKILL.md) — primary Codex instructions;
- [`references/architecture.md`](references/architecture.md) — architecture and invariants;
- [`references/task-lifecycle.md`](references/task-lifecycle.md) — task state machine;
- [`references/shared-ledger.md`](references/shared-ledger.md) — coordination-state model;
- [`references/claims-and-context.md`](references/claims-and-context.md) — advisory claims and peer awareness;
- [`references/worktrees-and-branches.md`](references/worktrees-and-branches.md) — ownership rules;
- [`references/integration-protocol.md`](references/integration-protocol.md) — mutex and candidate integration;
- [`references/conflict-resolution.md`](references/conflict-resolution.md) — intent-aware merges;
- [`references/recovery-and-takeover.md`](references/recovery-and-takeover.md) — crash recovery and task takeover;
- [`references/multi-terminal-usage.md`](references/multi-terminal-usage.md) — practical parallel workflows;
- [`references/examples.md`](references/examples.md) — end-to-end scenarios.

## Contributing

Contributions are welcome.

Please preserve the project's core properties:

- decentralized task ownership;
- isolated worktrees;
- durable cross-agent coordination;
- advisory claims instead of broad file locking;
- serialized integration;
- intent-aware conflict handling;
- local-target branch safety.

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT License. See [`LICENSE`](LICENSE).

## Primary checkout lifecycle

Task and candidate worktrees are temporary. The configured primary project folder is the authoritative location for the finished integrated target.

When integration starts with preexisting work in the primary folder, CWA preserves staged, unstaged, and non-tooling untracked state in a verified preservation worktree. It does not use stash and does not discard that work.

After candidate validation succeeds, CWA advances the target and returns that target branch and exact integrated SHA to the primary project folder. The agent must then run cleanup from the primary folder for the integrated task before reporting completion.

A task is not operationally finished when its code exists only in an isolated worktree.
