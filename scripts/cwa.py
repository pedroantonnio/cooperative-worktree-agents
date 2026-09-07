#!/usr/bin/env python3
"""Cooperative Worktree Agents helper.

Cross-platform, stdlib-only helper for shared coordination state, task worktrees,
soft claims, per-agent journals, and serialized candidate integration.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_VERSION = 1
PROTECTED_BRANCHES = {"main", "master"}


class CWAError(RuntimeError):
    pass


def git_failure_guidance(cmd: List[str], detail: str) -> str:
    lower = detail.lower().replace(chr(92), "/")
    joined = " ".join(cmd).lower()

    permission_denied = (
        "permission denied" in lower
        or "access is denied" in lower
        or "operation not permitted" in lower
    )

    git_metadata_write = (
        "cannot lock ref" in lower
        or ".git/refs/" in lower
        or "refs/heads/" in lower
        or "worktree add" in joined
    )

    if permission_denied and git_metadata_write:
        return (
            detail
            + "\n\n"
            + "CWA diagnosis: the current execution context cannot write Git metadata. "
            + "This commonly happens in a managed Codex sandbox where project files are writable "
            + "but the repository common .git directory is read-only. "
            + "Do NOT bypass the cooperative protocol by editing the shared or target checkout. "
            + "Re-run the exact same CWA command using the host execution tool's elevated or "
            + "user-approved mode that permits Git metadata writes. "
            + "This is an execution-tool permission, not a cwa.py flag."
        )

    return detail


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def run_git(repo: Path, *args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo), *args]
    p = subprocess.run(cmd, text=True, capture_output=capture)
    if check and p.returncode != 0:
        detail = (p.stderr or p.stdout or "").strip()
        detail = git_failure_guidance(cmd, detail)
        raise CWAError(f"Git command failed ({' '.join(cmd)}): {detail}")
    return p


def git_out(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


def resolve_repo(path: Optional[str]) -> Path:
    repo = Path(path or os.getcwd()).resolve()
    try:
        top = git_out(repo, "rev-parse", "--show-toplevel")
    except CWAError as e:
        raise CWAError(f"Not inside a Git worktree: {repo}") from e
    return Path(top).resolve()


def common_git_dir(repo: Path) -> Path:
    raw = git_out(repo, "rev-parse", "--git-common-dir")
    p = Path(raw)
    if not p.is_absolute():
        p = (repo / p).resolve()
    return p.resolve()


def state_root(repo: Path) -> Path:
    return common_git_dir(repo) / "codex-team"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise CWAError(f"Missing state file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CWAError(f"Invalid JSON state file: {path}: {e}") from e


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def slugify(value: str, max_len: int = 48) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s or "task")[:max_len].rstrip("-")


def short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def list_worktrees(repo: Path) -> List[Dict[str, str]]:
    text = git_out(repo, "worktree", "list", "--porcelain")
    entries: List[Dict[str, str]] = []
    cur: Dict[str, str] = {}
    for line in text.splitlines() + [""]:
        if not line.strip():
            if cur:
                entries.append(cur)
                cur = {}
            continue
        key, _, value = line.partition(" ")
        cur[key] = value
    return entries


def primary_worktree(repo: Path) -> Path:
    entries = list_worktrees(repo)
    if not entries:
        return repo
    return Path(entries[0]["worktree"]).resolve()


def default_worktree_root(repo: Path) -> Path:
    primary = primary_worktree(repo)
    return (primary.parent / ".codex-worktrees" / primary.name).resolve()


def local_branch_exists(repo: Path, branch: str) -> bool:
    p = run_git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
    return p.returncode == 0


def rev(repo: Path, ref: str) -> str:
    return git_out(repo, "rev-parse", ref)


def ensure_safe_target(repo: Path, target: str) -> None:
    if target in PROTECTED_BRANCHES:
        raise CWAError(f"Protected target '{target}' is outside the normal staging domain.")
    if not local_branch_exists(repo, target):
        raise CWAError(f"Target branch does not exist locally: {target}")
    if target != "staging":
        if not local_branch_exists(repo, "staging"):
            raise CWAError("Local 'staging' branch is required to validate a staging-derived target.")
        p = run_git(repo, "merge-base", "--is-ancestor", "staging", target, check=False)
        if p.returncode != 0:
            raise CWAError(f"Target '{target}' is not derived from local 'staging'.")


def ensure_dirs(root: Path) -> None:
    for name in ["tasks", "agents", "integrations", "locks", "incidents"]:
        (root / name).mkdir(parents=True, exist_ok=True)


def project_path(repo: Path) -> Path:
    return state_root(repo) / "project.json"


def load_project(repo: Path) -> Dict[str, Any]:
    p = project_path(repo)
    if not p.exists():
        raise CWAError("Coordination state is not initialized. Run 'cwa.py init --target staging'.")
    return read_json(p)


def init_project(repo: Path, target: str, objective: Optional[str], worktree_root_arg: Optional[str]) -> Dict[str, Any]:
    ensure_safe_target(repo, target)
    root = state_root(repo)
    ensure_dirs(root)
    p = project_path(repo)
    if p.exists():
        project = read_json(p)
        if project.get("schema_version") != SCHEMA_VERSION:
            raise CWAError("Unsupported coordination-state schema version.")
        if target and project.get("default_target") != target:
            # Re-initialization should not silently mutate project policy.
            raise CWAError(
                f"Project already initialized with target '{project.get('default_target')}', not '{target}'."
            )
        return project

    wt_root = Path(worktree_root_arg).resolve() if worktree_root_arg else default_worktree_root(repo)
    project = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "default_target": target,
        "project_objective": objective or "",
        "worktree_root": str(wt_root),
        "primary_worktree": str(primary_worktree(repo)),
    }
    # Exclusive create protects concurrent first-time initialization.
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        return read_json(p)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return project


def marker_path(repo: Path) -> Path:
    return repo / ".codex-agent.json"


def ensure_marker_ignored(repo: Path) -> None:
    # info/exclude belongs to common repository state and applies to worktrees.
    exclude = Path(git_out(repo, "rev-parse", "--git-path", "info/exclude"))
    if not exclude.is_absolute():
        exclude = (repo / exclude).resolve()
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    line = ".codex-agent.json"
    if line not in {x.strip() for x in existing.splitlines()}:
        with exclude.open("a", encoding="utf-8", newline="\n") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(line + "\n")


def write_marker(repo: Path, agent_id: str, task_id: str, role: str = "task") -> None:
    ensure_marker_ignored(repo)
    marker = {"agent_id": agent_id, "task_id": task_id, "role": role}
    marker_path(repo).write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")


def identity(repo: Path) -> Tuple[str, str, Dict[str, Any]]:
    m = marker_path(repo)
    if not m.exists():
        raise CWAError(
            f"No .codex-agent.json marker in {repo}. Use the registered task/candidate worktree or pass --repo accordingly."
        )
    data = read_json(m)
    agent_id, task_id = data.get("agent_id"), data.get("task_id")
    if not agent_id or not task_id:
        raise CWAError(f"Invalid agent marker: {m}")
    return agent_id, task_id, data


def task_dir(repo: Path, task_id: str) -> Path:
    return state_root(repo) / "tasks" / task_id


def task_manifest_path(repo: Path, task_id: str) -> Path:
    return task_dir(repo, task_id) / "manifest.json"


def agent_dir(repo: Path, agent_id: str) -> Path:
    return state_root(repo) / "agents" / agent_id


def agent_status_path(repo: Path, agent_id: str) -> Path:
    return agent_dir(repo, agent_id) / "status.json"


def agent_journal_path(repo: Path, agent_id: str) -> Path:
    return agent_dir(repo, agent_id) / "journal.jsonl"


def load_task(repo: Path, task_id: str) -> Dict[str, Any]:
    return read_json(task_manifest_path(repo, task_id))


def save_task(repo: Path, task: Dict[str, Any]) -> None:
    task["updated_at"] = now_iso()
    atomic_write_json(task_manifest_path(repo, task["task_id"]), task)


def heartbeat(repo: Path, agent_id: str, task_id: str, status_override: Optional[str] = None) -> Dict[str, Any]:
    path = agent_status_path(repo, agent_id)
    current = read_json(path, default={}) if path.exists() else {}
    task = load_task(repo, task_id)
    current.update(
        {
            "agent_id": agent_id,
            "task_id": task_id,
            "status": status_override or task.get("status", "ACTIVE"),
            "heartbeat_at": now_iso(),
            "worktree_path": task.get("worktree_path"),
            "task_branch": task.get("task_branch"),
            "claims": task.get("claims", []),
        }
    )
    atomic_write_json(path, current)
    return current


def journal(repo: Path, agent_id: str, task_id: str, event_type: str, summary: str,
            files: Optional[List[str]] = None, contracts: Optional[List[str]] = None,
            risks: Optional[List[str]] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    event = {
        "timestamp": now_iso(),
        "agent_id": agent_id,
        "task_id": task_id,
        "type": event_type,
        "summary": summary,
        "files": files or [],
        "contracts": contracts or [],
        "risks": risks or [],
    }
    if extra:
        event.update(extra)
    append_jsonl(agent_journal_path(repo, agent_id), event)
    heartbeat(repo, agent_id, task_id)
    return event


def current_branch(repo: Path) -> str:
    return git_out(repo, "branch", "--show-current")


def external_helper_relpath(repo: Path) -> Optional[str]:
    """Return the untracked nested helper path when CWA lives inside this repository.

    A nested cooperative-worktree-agents repository is operational tooling,
    not task source. Its presence in the primary checkout must not make the
    integration target appear dirty forever.
    """
    primary = primary_worktree(repo)
    helper_root = Path(__file__).resolve().parent.parent
    try:
        rel = helper_root.relative_to(primary).as_posix().rstrip("/")
    except ValueError:
        return None

    tracked = run_git(primary, "ls-files", "--error-unmatch", "--", rel, check=False)
    if tracked.returncode == 0:
        return None

    if not helper_root.exists():
        return None

    return rel


def status_lines(repo: Path, ignore_marker: bool = True, ignore_external_helper: bool = True) -> List[str]:
    out = git_out(repo, "status", "--porcelain")
    if not out:
        return []

    lines = out.splitlines()

    if ignore_marker:
        lines = [ln for ln in lines if not ln.endswith(".codex-agent.json")]

    if ignore_external_helper:
        helper_rel = external_helper_relpath(repo)
        if helper_rel:
            kept = []
            for line in lines:
                if line.startswith("?? "):
                    path = line[3:].replace(chr(92), "/").rstrip("/")
                    if path == helper_rel or path.startswith(helper_rel + "/"):
                        continue
                kept.append(line)
            lines = kept

    return lines


def is_clean(repo: Path, ignore_marker: bool = True, ignore_external_helper: bool = True) -> bool:
    return not status_lines(
        repo,
        ignore_marker=ignore_marker,
        ignore_external_helper=ignore_external_helper,
    )


def dirty_target_error(repo: Path) -> CWAError:
    lines = status_lines(repo)
    detail = "\n".join(lines) if lines else "(no non-tooling changes detected)"
    return CWAError(
        f"Target worktree is dirty: {repo}\n"
        f"Blocking status:\n{detail}\n\n"
        "This is a recoverable integration block, not task completion or abandonment. "
        "The task remains ready for integration. Do not stash, reset, discard, or overwrite "
        "changes that may belong to the user or another agent. Once the target checkout is clean, "
        "rerun the same integrate-begin command and continue the normal candidate validation flow."
    )


def cmd_init(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    project = init_project(repo, args.target, args.objective, args.worktree_root)
    print(json.dumps({"state_root": str(state_root(repo)), **project}, indent=2))


def cmd_start(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    if not project_path(repo).exists():
        init_project(repo, args.target or "staging", None, None)
    project = load_project(repo)
    target = args.target or project["default_target"]
    ensure_safe_target(repo, target)

    task_id = short_id("T")
    agent_id = short_id("A")
    branch = f"task/{task_id.lower()}-{slugify(args.title)}"
    base_sha = rev(repo, target)
    wt_root = Path(project["worktree_root"]).resolve()
    wt_root.mkdir(parents=True, exist_ok=True)
    wt_path = (wt_root / task_id.lower()).resolve()
    if wt_path.exists():
        raise CWAError(f"Worktree path already exists: {wt_path}")

    run_git(repo, "worktree", "add", "-b", branch, str(wt_path), base_sha)
    write_marker(wt_path, agent_id, task_id, "task")

    task = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "owner_agent_id": agent_id,
        "owner_history": [agent_id],
        "title": args.title,
        "objective": args.objective,
        "acceptance_criteria": args.acceptance or [],
        "target_branch": target,
        "base_sha": base_sha,
        "task_branch": branch,
        "worktree_path": str(wt_path),
        "status": "ACTIVE",
        "claims": args.claim or [],
        "head_sha": None,
        "changed_files": [],
        "verification": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    task_dir(repo, task_id).mkdir(parents=True, exist_ok=False)
    atomic_write_json(task_manifest_path(repo, task_id), task)
    atomic_write_json(
        agent_status_path(repo, agent_id),
        {
            "agent_id": agent_id,
            "task_id": task_id,
            "status": "ACTIVE",
            "heartbeat_at": now_iso(),
            "worktree_path": str(wt_path),
            "task_branch": branch,
            "claims": task["claims"],
        },
    )
    journal(
        repo,
        agent_id,
        task_id,
        "intent",
        args.objective,
        extra={"acceptance_criteria": task["acceptance_criteria"], "target_branch": target, "base_sha": base_sha},
    )
    print(json.dumps({
        "agent_id": agent_id,
        "task_id": task_id,
        "task_branch": branch,
        "base_sha": base_sha,
        "target_branch": target,
        "worktree_path": str(wt_path),
        "helper_path": str(Path(__file__).resolve()),
        "skill_root": str(Path(__file__).resolve().parent.parent),
        "next": (
            f"Continue all implementation inside {wt_path}. "
            f"If the skill is absent there, invoke CWA with the absolute helper path "
            f"{Path(__file__).resolve()} and pass --repo for the task worktree."
        ),
    }, indent=2))


def cmd_event(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, _ = identity(repo)
    ev = journal(repo, agent_id, task_id, args.type, args.summary, args.file, args.contract, args.risk)
    print(json.dumps(ev, indent=2))


def cmd_claim(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, _ = identity(repo)
    task = load_task(repo, task_id)
    if task.get("owner_agent_id") != agent_id:
        raise CWAError("This agent does not own the task.")
    claims = list(task.get("claims", []))
    for p in args.pattern:
        if p not in claims:
            claims.append(p)
    task["claims"] = claims
    save_task(repo, task)
    heartbeat(repo, agent_id, task_id)
    journal(repo, agent_id, task_id, "scope_change", "Updated soft edit claims", extra={"claims": claims})
    print(json.dumps({"task_id": task_id, "claims": claims}, indent=2))


def iter_tasks(repo: Path) -> Iterable[Dict[str, Any]]:
    root = state_root(repo) / "tasks"
    if not root.exists():
        return []
    out = []
    for manifest in sorted(root.glob("*/manifest.json")):
        try:
            out.append(read_json(manifest))
        except CWAError:
            continue
    return out


def iter_journal(repo: Path, agent_id: str) -> Iterable[Dict[str, Any]]:
    p = agent_journal_path(repo, agent_id)
    if not p.exists():
        return []
    events = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def path_matches(pattern: str, path: str) -> bool:
    pattern = pattern.replace("\\", "/")
    path = path.replace("\\", "/")
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path + "/", pattern)


def cmd_status(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    project = load_project(repo)
    tasks = list(iter_tasks(repo))
    lock = read_lock(repo)
    if args.json:
        print(json.dumps({"project": project, "tasks": tasks, "integration_lock": lock}, indent=2))
        return
    print(f"Project target: {project['default_target']}")
    if project.get("project_objective"):
        print(f"Project objective: {project['project_objective']}")
    print(f"Integration lock: {lock if lock else 'FREE'}")
    if not tasks:
        print("No registered tasks.")
        return
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for t in tasks:
        groups.setdefault(t.get("status", "UNKNOWN"), []).append(t)
    for state in sorted(groups):
        print(f"\n{state}")
        for t in groups[state]:
            print(f"  {t['task_id']}  {t['title']}  owner={t.get('owner_agent_id')}  target={t.get('target_branch')}")
            if t.get("claims"):
                print(f"    claims: {', '.join(t['claims'])}")


def cmd_context(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    project = load_project(repo)
    try:
        self_agent, self_task, _ = identity(repo)
    except CWAError:
        self_agent = self_task = None
    paths = args.path or []
    tasks = list(iter_tasks(repo))
    relevant_tasks = []
    for t in tasks:
        if args.task and t["task_id"] != args.task:
            continue
        if t["task_id"] == self_task and not args.task:
            continue
        if not paths:
            if t.get("status") not in {"INTEGRATED", "ABANDONED"}:
                relevant_tasks.append(t)
            continue
        changed = t.get("changed_files", [])
        claims = t.get("claims", [])
        hit = any(any(path_matches(c, p) for c in claims) or p in changed for p in paths)
        if hit:
            relevant_tasks.append(t)

    relevant_events: List[Dict[str, Any]] = []
    for t in relevant_tasks:
        aid = t.get("owner_agent_id")
        if not aid:
            continue
        for ev in iter_journal(repo, aid):
            if not paths:
                if ev.get("type") in {"decision", "interface_change", "warning", "dependency", "scope_change", "conflict_resolution", "handoff"}:
                    relevant_events.append(ev)
                continue
            ev_files = ev.get("files", [])
            if any(p == f or path_matches(f, p) or path_matches(p, f) for p in paths for f in ev_files):
                relevant_events.append(ev)

    payload = {
        "project": project,
        "self": {"agent_id": self_agent, "task_id": self_task},
        "query_paths": paths,
        "tasks": relevant_tasks,
        "events": relevant_events[-100:],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_ready(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") != "task":
        raise CWAError("Run 'ready' from the task worktree, not an integration candidate.")
    task = load_task(repo, task_id)
    if task.get("owner_agent_id") != agent_id:
        raise CWAError("This agent does not own the task.")
    if current_branch(repo) != task["task_branch"]:
        raise CWAError(f"Expected branch {task['task_branch']}, found {current_branch(repo)}")
    if not is_clean(repo):
        raise CWAError("Task worktree is dirty. Commit or intentionally discard task-local changes before readiness.")
    head = rev(repo, "HEAD")
    files = [x for x in git_out(repo, "diff", "--name-only", f"{task['base_sha']}...{head}").splitlines() if x]
    if not files and not args.allow_no_changes:
        raise CWAError("Task has no changed files. Use --allow-no-changes only for a deliberate no-code task.")
    task["head_sha"] = head
    task["changed_files"] = files
    task["verification"] = args.test or []
    task["status"] = "READY_FOR_INTEGRATION"
    save_task(repo, task)
    journal(repo, agent_id, task_id, "test_result", "Task marked ready for integration", files=files,
            extra={"verification": task["verification"], "head_sha": head})
    print(json.dumps({"task_id": task_id, "status": task["status"], "head_sha": head, "changed_files": files,
                      "verification": task["verification"]}, indent=2))


def lock_dir(repo: Path) -> Path:
    return state_root(repo) / "locks" / "integration.lock"


def read_lock(repo: Path) -> Optional[Dict[str, Any]]:
    d = lock_dir(repo)
    if not d.exists():
        return None
    owner = d / "owner.json"
    if not owner.exists():
        return {"status": "LOCKED", "owner": "UNKNOWN", "path": str(d)}
    return read_json(owner)


def acquire_lock(repo: Path, agent_id: str, task_id: str, target: str) -> Dict[str, Any]:
    d = lock_dir(repo)
    try:
        d.mkdir(parents=False, exist_ok=False)
    except FileExistsError:
        raise CWAError(f"Integration lock is already held: {read_lock(repo)}")
    owner = {
        "agent_id": agent_id,
        "task_id": task_id,
        "target_branch": target,
        "acquired_at": now_iso(),
        "pid": os.getpid(),
    }
    atomic_write_json(d / "owner.json", owner)
    return owner


def assert_lock_owner(repo: Path, agent_id: str, task_id: str) -> Dict[str, Any]:
    owner = read_lock(repo)
    if not owner or owner.get("agent_id") != agent_id or owner.get("task_id") != task_id:
        raise CWAError(f"Integration lock is not owned by this agent/task. Current lock: {owner}")
    return owner


def release_lock(repo: Path, agent_id: str, task_id: str) -> None:
    assert_lock_owner(repo, agent_id, task_id)
    shutil.rmtree(lock_dir(repo))


def find_target_worktree(repo: Path, target: str) -> Optional[Path]:
    want = f"refs/heads/{target}"
    for e in list_worktrees(repo):
        if e.get("branch") == want:
            return Path(e["worktree"]).resolve()
    return None


def integration_record_path(repo: Path, task_id: str) -> Path:
    return state_root(repo) / "integrations" / f"{task_id}.json"


def get_or_create_target_worktree(repo: Path, project: Dict[str, Any], target: str) -> Path:
    existing = find_target_worktree(repo, target)
    if existing:
        return existing
    root = Path(project["worktree_root"]).resolve() / "_integration"
    root.mkdir(parents=True, exist_ok=True)
    path = (root / slugify(target, 64)).resolve()
    if path.exists() and any(path.iterdir()):
        raise CWAError(f"Integration path exists but is not a registered target worktree: {path}")
    run_git(repo, "worktree", "add", str(path), target)
    return path


def project_primary_worktree(repo: Path, project: Optional[Dict[str, Any]] = None) -> Path:
    if project is None and project_path(repo).exists():
        project = load_project(repo)
    if project and project.get("primary_worktree"):
        return Path(project["primary_worktree"]).resolve()
    return primary_worktree(repo)


def git_bytes(repo: Path, *args: str) -> bytes:
    cmd = ["git", "-C", str(repo), *args]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        detail = p.stderr.decode("utf-8", errors="replace").strip()
        detail = git_failure_guidance(cmd, detail)
        raise CWAError(f"Git command failed ({' '.join(cmd)}): {detail}")
    return p.stdout


def apply_git_patch(repo: Path, patch: bytes, index: bool) -> None:
    if not patch:
        return
    cmd = ["git", "-C", str(repo), "apply", "--binary"]
    if index:
        cmd.append("--index")
    cmd.append("-")
    p = subprocess.run(cmd, input=patch, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        detail = p.stderr.decode("utf-8", errors="replace").strip()
        raise CWAError(f"Could not reproduce preserved primary changes in {repo}: {detail}")


def untracked_files(repo: Path) -> List[str]:
    raw = git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z")
    values = raw.decode("utf-8", errors="surrogateescape").split(chr(0))
    helper_rel = external_helper_relpath(repo)
    result: List[str] = []
    for value in values:
        if not value:
            continue
        rel = value.replace(chr(92), "/")
        if rel == ".codex-agent.json":
            continue
        if helper_rel and (rel == helper_rel or rel.startswith(helper_rel + "/")):
            continue
        result.append(rel)
    return result


def copy_untracked_files(source: Path, destination: Path, paths: List[str]) -> None:
    for rel in paths:
        src = source / Path(rel)
        dst = destination / Path(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            target = os.readlink(src)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(target, dst)
        elif src.is_file():
            shutil.copy2(src, dst)


def remove_copied_untracked_files(source: Path, paths: List[str]) -> None:
    parents = set()
    for rel in paths:
        path = source / Path(rel)
        if path.is_file() or path.is_symlink():
            path.unlink()
        parent = path.parent
        while parent != source and source in parent.parents:
            parents.add(parent)
            parent = parent.parent
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        try:
            parent.rmdir()
        except OSError:
            pass


def park_primary_changes(
    repo: Path,
    project: Dict[str, Any],
    target: str,
    reason: str,
) -> Optional[Dict[str, Any]]:
    primary = project_primary_worktree(repo, project)
    dirty_before = status_lines(primary)
    if not dirty_before:
        return None

    original_branch = current_branch(primary)
    original_head = rev(primary, "HEAD")
    token = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    preserve_root = Path(project["worktree_root"]).resolve() / "_preserved"
    preserve_root.mkdir(parents=True, exist_ok=True)
    preserve_wt = (preserve_root / f"primary-{token}").resolve()

    created_branch = False
    if original_branch and original_branch != target:
        preserve_branch = original_branch
    else:
        preserve_branch = f"wip/cwa-preserved-primary-{token}"
        run_git(primary, "branch", preserve_branch, original_head)
        created_branch = True

    staged_patch = git_bytes(primary, "diff", "--cached", "--binary", "--no-ext-diff")
    unstaged_patch = git_bytes(primary, "diff", "--binary", "--no-ext-diff")
    untracked = untracked_files(primary)

    try:
        run_git(primary, "worktree", "add", "--detach", str(preserve_wt), original_head)
        apply_git_patch(preserve_wt, staged_patch, index=True)
        apply_git_patch(preserve_wt, unstaged_patch, index=False)
        copy_untracked_files(primary, preserve_wt, untracked)

        if git_bytes(preserve_wt, "diff", "--cached", "--binary", "--no-ext-diff") != staged_patch:
            raise CWAError("Preserved staged diff does not exactly match the primary staged diff.")
        if git_bytes(preserve_wt, "diff", "--binary", "--no-ext-diff") != unstaged_patch:
            raise CWAError("Preserved unstaged diff does not exactly match the primary unstaged diff.")
        if status_lines(preserve_wt) != dirty_before:
            raise CWAError(
                "Preserved primary status does not exactly match the original primary status. "
                "The primary checkout was not modified."
            )

        run_git(primary, "restore", "--staged", "--worktree", "--", ".")
        remove_copied_untracked_files(primary, untracked)

        if not is_clean(primary):
            raise CWAError(
                "Primary preservation copy succeeded, but the primary checkout still contains "
                "non-tooling changes. Refusing to continue automatically."
            )

        if not original_branch or original_branch == target:
            run_git(primary, "switch", preserve_branch)

        record = {
            "reason": reason,
            "original_branch": original_branch,
            "original_head": original_head,
            "preservation_branch": preserve_branch,
            "preservation_worktree": str(preserve_wt),
            "created_preservation_branch": created_branch,
            "status_snapshot": dirty_before,
            "preserved_at": now_iso(),
        }
        return record
    except Exception:
        if preserve_wt.exists():
            run_git(primary, "worktree", "remove", "--force", str(preserve_wt), check=False)
        if created_branch:
            run_git(primary, "branch", "-D", preserve_branch, check=False)
        raise


def attach_preserved_primary_worktrees(
    repo: Path,
    preservations: List[Dict[str, Any]],
) -> None:
    for item in preservations:
        path = Path(item["preservation_worktree"]).resolve()
        branch = item["preservation_branch"]
        if not path.exists():
            raise CWAError(f"Preserved primary worktree disappeared: {path}")
        if current_branch(path) != branch:
            run_git(path, "switch", branch)


def cwa_managed_integration_worktree(project: Dict[str, Any], path: Path) -> bool:
    root = (Path(project["worktree_root"]).resolve() / "_integration").resolve()
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def handoff_target_to_primary(
    repo: Path,
    project: Dict[str, Any],
    target: str,
    integrated_sha: str,
    record: Dict[str, Any],
) -> Dict[str, Any]:
    primary = project_primary_worktree(repo, project)
    preservations = list(record.get("primary_preservations") or [])

    if primary.resolve() != (find_target_worktree(repo, target) or primary).resolve():
        if not is_clean(primary):
            late = park_primary_changes(
                repo,
                project,
                target,
                "Changes appeared in the primary checkout while integration was running",
            )
            if late:
                preservations.append(late)
                record["primary_preservations"] = preservations
                atomic_write_json(integration_record_path(repo, record["task_id"]), record)

    active_target_wt = find_target_worktree(repo, target)

    if active_target_wt and active_target_wt.resolve() != primary.resolve():
        if not is_clean(active_target_wt):
            raise dirty_target_error(active_target_wt)
        run_git(active_target_wt, "switch", "--detach", integrated_sha)

    if current_branch(primary) != target:
        run_git(primary, "switch", target)

    if current_branch(primary) != target or rev(primary, "HEAD") != integrated_sha:
        raise CWAError(
            "Primary handoff failed: the configured primary project folder is not on the "
            "integrated target SHA. Integration is not complete and the mutex remains held."
        )

    attach_preserved_primary_worktrees(repo, preservations)

    if active_target_wt and active_target_wt.resolve() != primary.resolve():
        if cwa_managed_integration_worktree(project, active_target_wt) and active_target_wt.exists():
            run_git(primary, "worktree", "remove", str(active_target_wt))

    return {
        "primary_worktree": str(primary),
        "primary_branch": current_branch(primary),
        "primary_head": rev(primary, "HEAD"),
        "preservations": preservations,
    }


def unresolved_files(repo: Path) -> List[str]:
    return [x for x in git_out(repo, "diff", "--name-only", "--diff-filter=U").splitlines() if x]



def cmd_integrate_begin(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") != "task":
        raise CWAError("Begin integration from the task worktree.")
    task = load_task(repo, task_id)
    if task.get("status") != "READY_FOR_INTEGRATION":
        raise CWAError(f"Task must be READY_FOR_INTEGRATION, found {task.get('status')}")
    if task.get("owner_agent_id") != agent_id:
        raise CWAError("This agent does not own the task.")
    target = task["target_branch"]
    ensure_safe_target(repo, target)
    project = load_project(repo)
    acquire_lock(repo, agent_id, task_id, target)

    primary_preservations: List[Dict[str, Any]] = []
    try:
        parked = park_primary_changes(
            repo,
            project,
            target,
            "Primary checkout contained preexisting work when integration began",
        )
        if parked:
            primary_preservations.append(parked)

        target_wt = get_or_create_target_worktree(repo, project, target)
        if not is_clean(target_wt):
            raise dirty_target_error(target_wt)
        target_sha = rev(target_wt, "HEAD")
        if target_sha != rev(repo, target):
            raise CWAError("Target worktree HEAD does not match target branch ref.")

        suffix = uuid.uuid4().hex[:6]
        candidate_branch = f"integration/{task_id.lower()}-{suffix}"
        cand_root = Path(project["worktree_root"]).resolve() / "_candidates"
        cand_root.mkdir(parents=True, exist_ok=True)
        candidate_wt = (cand_root / f"{task_id.lower()}-{suffix}").resolve()
        run_git(repo, "worktree", "add", "-b", candidate_branch, str(candidate_wt), target_sha)
        write_marker(candidate_wt, agent_id, task_id, "candidate")

        record = {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "agent_id": agent_id,
            "target_branch": target,
            "target_sha_before": target_sha,
            "target_worktree": str(target_wt),
            "candidate_branch": candidate_branch,
            "candidate_worktree": str(candidate_wt),
            "task_branch": task["task_branch"],
            "primary_worktree": str(project_primary_worktree(repo, project)),
            "primary_preservations": primary_preservations,
            "started_at": now_iso(),
            "status": "MERGING",
            "conflict_files": [],
        }
        atomic_write_json(integration_record_path(repo, task_id), record)

        p = run_git(candidate_wt, "merge", "--no-ff", "--no-edit", task["task_branch"], check=False)
        conflicts = unresolved_files(candidate_wt)
        if conflicts:
            record["status"] = "CONFLICT"
            record["conflict_files"] = conflicts
            atomic_write_json(integration_record_path(repo, task_id), record)
            task["status"] = "CONFLICT"
            save_task(repo, task)
            journal(
                repo,
                agent_id,
                task_id,
                "warning",
                "Integration candidate has merge conflicts",
                files=conflicts,
                extra={"candidate_worktree": str(candidate_wt), "target_sha_before": target_sha},
            )
        elif p.returncode == 0:
            record["status"] = "INTEGRATION_VALIDATION"
            atomic_write_json(integration_record_path(repo, task_id), record)
            task["status"] = "INTEGRATION_VALIDATION"
            save_task(repo, task)
            journal(
                repo,
                agent_id,
                task_id,
                "integration_note",
                "Task merged cleanly into candidate; combined-state validation required",
                extra={"candidate_worktree": str(candidate_wt), "target_sha_before": target_sha},
            )
        else:
            record["status"] = "INTEGRATION_ERROR"
            record["merge_stderr"] = (p.stderr or "").strip()
            atomic_write_json(integration_record_path(repo, task_id), record)
            task["status"] = "INTEGRATION_ERROR"
            save_task(repo, task)
            journal(
                repo,
                agent_id,
                task_id,
                "warning",
                "Integration merge command failed outside normal conflict handling",
                extra={"candidate_worktree": str(candidate_wt), "stderr": record["merge_stderr"]},
            )

        print(json.dumps(record, indent=2))
    except Exception:
        rec_path = integration_record_path(repo, task_id)
        if not rec_path.exists():
            try:
                recovery_record = {
                    "task_id": task_id,
                    "primary_preservations": primary_preservations,
                }
                handoff_target_to_primary(
                    repo,
                    project,
                    target,
                    rev(repo, target),
                    recovery_record,
                )
            except Exception:
                pass
            try:
                release_lock(repo, agent_id, task_id)
            except Exception:
                pass
        raise


def merge_in_progress(repo: Path) -> bool:
    p = run_git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
    return p.returncode == 0



def cmd_integrate_finish(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") != "candidate":
        raise CWAError("Run integrate-finish from the candidate worktree.")
    assert_lock_owner(repo, agent_id, task_id)
    task = load_task(repo, task_id)
    record = read_json(integration_record_path(repo, task_id))
    if Path(record["candidate_worktree"]).resolve() != repo:
        raise CWAError("This is not the recorded candidate worktree.")

    if not args.test:
        raise CWAError(
            "integrate-finish requires at least one verified combined-state test result. "
            "Record PASS only after observing the native command exit code."
        )

    conflicts = unresolved_files(repo)
    if conflicts:
        raise CWAError(f"Unresolved conflict files remain: {conflicts}")
    if merge_in_progress(repo):
        p = run_git(repo, "commit", "--no-edit", check=False)
        if p.returncode != 0:
            raise CWAError(f"Resolved merge is not committed: {(p.stderr or p.stdout).strip()}")
    if not is_clean(repo):
        raise CWAError("Candidate worktree is dirty. Commit the intended conflict resolution before finishing.")

    project = load_project(repo)
    candidate_head = rev(repo, "HEAD")
    before = record["target_sha_before"]
    target = task["target_branch"]
    target_ref = rev(repo, target)

    p = run_git(repo, "merge-base", "--is-ancestor", before, candidate_head, check=False)
    if p.returncode != 0:
        raise CWAError("Candidate does not descend from recorded target SHA.")

    if target_ref == before:
        target_wt = Path(record["target_worktree"]).resolve()
        if not target_wt.exists():
            target_wt = get_or_create_target_worktree(repo, project, target)
            record["target_worktree"] = str(target_wt)
            atomic_write_json(integration_record_path(repo, task_id), record)

        if not is_clean(target_wt):
            raise dirty_target_error(target_wt)
        if rev(target_wt, "HEAD") != before or rev(target_wt, target) != before:
            raise CWAError(
                "Target moved after candidate creation. Do not force it. "
                "Abort this integration and retry from current target state."
            )
        run_git(target_wt, "merge", "--ff-only", record["candidate_branch"])
        target_ref = rev(repo, target)
    elif target_ref != candidate_head:
        raise CWAError(
            "Target moved after candidate creation. Do not force it. "
            "Abort this integration and retry from current target state."
        )

    if target_ref != candidate_head:
        raise CWAError("Target did not advance to the validated candidate HEAD.")

    handoff = handoff_target_to_primary(
        repo,
        project,
        target,
        candidate_head,
        record,
    )

    task["status"] = "INTEGRATED"
    task["integration_sha"] = candidate_head
    task["integration_verification"] = args.test
    task["integrated_at"] = now_iso()
    save_task(repo, task)

    record["status"] = "INTEGRATED"
    record["candidate_head"] = candidate_head
    record["integrated_sha"] = candidate_head
    record["verification"] = args.test
    record["primary_handoff"] = handoff
    record["finished_at"] = now_iso()
    atomic_write_json(integration_record_path(repo, task_id), record)

    journal(
        repo,
        agent_id,
        task_id,
        "integration_note",
        "Validated candidate advanced the target and the integrated target was returned to the primary project folder",
        files=task.get("changed_files", []),
        extra={
            "integrated_sha": candidate_head,
            "verification": args.test,
            "primary_worktree": handoff["primary_worktree"],
        },
    )
    release_lock(repo, agent_id, task_id)

    primary = handoff["primary_worktree"]
    helper = str(Path(__file__).resolve())
    print(
        json.dumps(
            {
                "task_id": task_id,
                "status": "INTEGRATED",
                "target_branch": target,
                "integrated_sha": candidate_head,
                "primary_worktree": primary,
                "primary_branch": handoff["primary_branch"],
                "primary_head": handoff["primary_head"],
                "preserved_preexisting_work": handoff["preservations"],
                "next": (
                    f"Integration is visible in the primary project folder {primary}. "
                    f"Before reporting completion, run cleanup from the primary folder with: "
                    f"python {helper} --repo {primary} cleanup --task {task_id}"
                ),
            },
            indent=2,
        )
    )


def cmd_integrate_abort(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") != "candidate":
        raise CWAError("Run integrate-abort from the candidate worktree.")
    assert_lock_owner(repo, agent_id, task_id)
    record = read_json(integration_record_path(repo, task_id))
    task = load_task(repo, task_id)
    candidate_wt = Path(record["candidate_worktree"]).resolve()
    candidate_branch = record["candidate_branch"]
    # Use another repository worktree as the command root before removing current candidate.
    anchor = primary_worktree(repo)
    if merge_in_progress(candidate_wt):
        run_git(candidate_wt, "merge", "--abort", check=False)
    run_git(anchor, "worktree", "remove", "--force", str(candidate_wt), check=False)
    run_git(anchor, "branch", "-D", candidate_branch, check=False)
    task["status"] = "READY_FOR_INTEGRATION"
    save_task(anchor, task)
    record["status"] = "ABORTED"
    record["aborted_at"] = now_iso()
    atomic_write_json(integration_record_path(anchor, task_id), record)
    journal(anchor, agent_id, task_id, "integration_note", "Integration candidate aborted; task returned to ready state")
    release_lock(anchor, agent_id, task_id)
    print(json.dumps({"task_id": task_id, "status": "READY_FOR_INTEGRATION", "candidate_removed": str(candidate_wt)}, indent=2))


def cmd_lock_break(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    owner = read_lock(repo)
    if not owner:
        raise CWAError("Integration lock is already free.")
    incident = {
        "timestamp": now_iso(),
        "type": "forced_lock_break",
        "reason": args.reason,
        "previous_owner": owner,
        "performed_from": str(repo),
    }
    incident_path = state_root(repo) / "incidents" / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.json"
    atomic_write_json(incident_path, incident)
    shutil.rmtree(lock_dir(repo))
    print(json.dumps({"lock": "BROKEN", "incident": str(incident_path), "previous_owner": owner}, indent=2))



def cmd_block(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") not in {"task", "candidate"}:
        raise CWAError("Unknown worktree role for task blocking.")
    task = load_task(repo, task_id)
    if task.get("owner_agent_id") != agent_id:
        raise CWAError("This agent does not own the task.")
    task["status"] = "BLOCKED_SEMANTIC_CONFLICT"
    task["blocked_reason"] = args.reason
    save_task(repo, task)
    journal(repo, agent_id, task_id, "warning", f"Semantic/product conflict requires user decision: {args.reason}")
    print(json.dumps({"task_id": task_id, "status": task["status"], "reason": args.reason}, indent=2))


def cmd_abandon(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    agent_id, task_id, marker = identity(repo)
    if marker.get("role") != "task":
        raise CWAError("Abandon from the task worktree.")
    task = load_task(repo, task_id)
    task["status"] = "ABANDONED"
    task["abandon_reason"] = args.reason
    save_task(repo, task)
    journal(repo, agent_id, task_id, "handoff", f"Task abandoned: {args.reason}")
    print(json.dumps({"task_id": task_id, "status": "ABANDONED", "reason": args.reason}, indent=2))



def cmd_cleanup(args: argparse.Namespace) -> None:
    repo = resolve_repo(args.repo)
    project = load_project(repo)
    anchor = project_primary_worktree(repo, project)

    if repo.resolve() != anchor.resolve():
        raise CWAError(
            f"Run cleanup from the configured primary project folder: {anchor}. "
            "This avoids deleting the worktree that owns the current shell."
        )

    task_id = args.task
    if not task_id:
        try:
            _, task_id, _ = identity(repo)
        except CWAError as e:
            raise CWAError("cleanup requires --task when run from the primary project folder.") from e

    task = load_task(repo, task_id)
    if task.get("status") != "INTEGRATED":
        raise CWAError("Task must be INTEGRATED before cleanup.")

    target = task["target_branch"]
    if current_branch(anchor) != target:
        raise CWAError(
            f"Primary folder must be on integrated target {target} before cleanup; "
            f"found {current_branch(anchor)}."
        )

    p = run_git(anchor, "merge-base", "--is-ancestor", task["task_branch"], target, check=False)
    if p.returncode != 0:
        raise CWAError("Task branch is not confirmed as integrated into target.")

    removed = []

    record_path = integration_record_path(anchor, task_id)
    if record_path.exists():
        record = read_json(record_path)
        candidate_wt = Path(record.get("candidate_worktree", "")).resolve()
        candidate_branch = record.get("candidate_branch")
        if candidate_wt.exists():
            if not is_clean(candidate_wt):
                raise CWAError(f"Candidate worktree is dirty; refusing cleanup: {candidate_wt}")
            if merge_in_progress(candidate_wt):
                raise CWAError(f"Candidate worktree still has a merge in progress: {candidate_wt}")
            run_git(anchor, "worktree", "remove", str(candidate_wt))
            removed.append(str(candidate_wt))
        if candidate_branch and local_branch_exists(anchor, candidate_branch):
            run_git(anchor, "branch", "-d", candidate_branch)

    task_wt = Path(task["worktree_path"]).resolve()
    if task_wt.exists():
        if not is_clean(task_wt):
            raise CWAError(f"Task worktree is dirty; refusing cleanup: {task_wt}")
        run_git(anchor, "worktree", "remove", str(task_wt))
        removed.append(str(task_wt))

    if local_branch_exists(anchor, task["task_branch"]):
        run_git(anchor, "branch", "-d", task["task_branch"])

    task["cleaned_at"] = now_iso()
    task["cleanup_complete"] = True
    save_task(anchor, task)

    print(
        json.dumps(
            {
                "task_id": task_id,
                "status": "INTEGRATED",
                "cleanup_complete": True,
                "primary_worktree": str(anchor),
                "target_branch": target,
                "target_head": rev(anchor, "HEAD"),
                "removed_worktrees": removed,
                "final": "Task lifecycle complete. Final integrated code is in the primary project folder.",
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cooperative Worktree Agents helper")
    p.add_argument("--repo", help="Repository/worktree path. Defaults to current directory.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="Initialize shared coordination state")
    s.add_argument("--target", default="staging")
    s.add_argument("--objective")
    s.add_argument("--worktree-root")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("start", help="Register a task and create its worktree")
    s.add_argument("--title", required=True)
    s.add_argument("--objective", required=True)
    s.add_argument("--target")
    s.add_argument("--claim", action="append", default=[])
    s.add_argument("--acceptance", action="append", default=[])
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("event", help="Append a durable event to this agent's journal")
    s.add_argument("--type", required=True)
    s.add_argument("--summary", required=True)
    s.add_argument("--file", action="append", default=[])
    s.add_argument("--contract", action="append", default=[])
    s.add_argument("--risk", action="append", default=[])
    s.set_defaults(func=cmd_event)

    s = sub.add_parser("claim", help="Add soft edit claims")
    s.add_argument("--pattern", action="append", required=True)
    s.set_defaults(func=cmd_claim)

    s = sub.add_parser("status", help="Show shared task/lock status")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("context", help="Show relevant peer tasks and journal events")
    s.add_argument("--path", action="append", default=[])
    s.add_argument("--task")
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("ready", help="Mark committed clean task ready for integration")
    s.add_argument("--test", action="append", default=[])
    s.add_argument("--allow-no-changes", action="store_true")
    s.set_defaults(func=cmd_ready)

    s = sub.add_parser("integrate-begin", help="Acquire mutex and merge task into a candidate worktree")
    s.set_defaults(func=cmd_integrate_begin)

    s = sub.add_parser("integrate-finish", help="Advance target, return it to primary, and require verified evidence")
    s.add_argument("--test", action="append", default=[])
    s.set_defaults(func=cmd_integrate_finish)

    s = sub.add_parser("integrate-abort", help="Abort/remove candidate and release mutex")
    s.set_defaults(func=cmd_integrate_abort)

    s = sub.add_parser("lock-break", help="Force-break a stale integration lock and record an incident")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_lock_break)

    s = sub.add_parser("block", help="Mark a genuine semantic/product conflict that requires user direction")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_block)

    s = sub.add_parser("abandon", help="Mark this task abandoned")
    s.add_argument("--reason", required=True)
    s.set_defaults(func=cmd_abandon)

    s = sub.add_parser("cleanup", help="Remove integrated task/candidate worktrees after primary handoff")
    s.add_argument("--task")
    s.set_defaults(func=cmd_cleanup)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
        return 0
    except CWAError as e:
        print(f"[CWA ERROR] {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[CWA ERROR] Interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
