# Shared coordination ledger

## Location

The helper stores state at:

```text
<git-common-dir>/codex-team/
```

Example:

```text
.git/codex-team/
├── project.json
├── tasks/
│   └── T-4f82a13c/
│       └── manifest.json
├── agents/
│   └── A-3c90e1f2/
│       ├── status.json
│       └── journal.jsonl
├── integrations/
│   └── T-4f82a13c.json
├── locks/
│   └── integration.lock/
│       └── owner.json
└── incidents/
    └── ...json
```

## Project record

`project.json` contains stable repository-wide coordination defaults such as:

- schema version;
- default integration target;
- optional project objective;
- default worktree root;
- creation time.

The first agent normally creates it. Later agents reuse it.

## Task manifest

A task manifest is durable shared truth about one task. Typical fields:

```json
{
  "task_id": "T-4f82a13c",
  "owner_agent_id": "A-3c90e1f2",
  "title": "Add Google OAuth",
  "objective": "Allow Google sign-in without breaking password login",
  "acceptance_criteria": [
    "Google sign-in works end to end",
    "Password login still works"
  ],
  "target_branch": "feature/current",
  "base_sha": "...",
  "task_branch": "task/t-4f82a13c-add-google-oauth",
  "worktree_path": "...",
  "status": "ACTIVE",
  "claims": ["src/auth/**"],
  "head_sha": null,
  "changed_files": [],
  "verification": []
}
```

## Agent status

Each agent owns its own `status.json`. It contains:

- current task;
- status;
- heartbeat timestamp;
- claims;
- worktree path;
- branch;
- latest summary where useful.

Any helper command executed by the agent refreshes the heartbeat.

A heartbeat is evidence, not a guarantee that a process is alive. Do not automatically steal tasks solely because a timestamp is old.

## Per-agent journal

Each agent writes only its own `journal.jsonl`.

Each line is one JSON object. Example:

```json
{"timestamp":"...","type":"decision","summary":"Reuse SessionService for OAuth sessions","files":["src/auth/SessionService.ts"],"contracts":[],"risks":[]}
```

### Good journal content

Record:

- objective refinements;
- durable engineering decisions;
- public rationale for those decisions;
- changed interfaces/contracts;
- external dependencies;
- migrations or schema assumptions;
- files/areas another task must preserve;
- test outcomes;
- known risks;
- integration concerns;
- conflict resolutions;
- handoff state.

### Do not record

Do not record:

- hidden chain-of-thought;
- private scratchpad content;
- long speculative reasoning transcripts;
- secrets, credentials, tokens, or private user data;
- irrelevant command-by-command narration.

Use concise engineering rationale such as:

> Chose the existing SessionService because it already owns session rotation and avoids a second session lifecycle.

Do not write a transcript of every alternative considered internally.

## Integration sessions

An integration session records:

- task/agent owner;
- target branch;
- target SHA at start;
- candidate branch;
- candidate worktree;
- conflict files;
- integration status;
- start time.

This supports crash recovery and prevents ambiguous stale locks.

## Incidents

Forced recovery actions such as breaking an integration lock produce immutable incident files with unique names. This avoids a shared mutable incident log.
