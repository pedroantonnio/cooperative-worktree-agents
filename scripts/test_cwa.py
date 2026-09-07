#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CWA = HERE / "cwa.py"


def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise AssertionError(f"Command failed: {cmd}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p


def git(repo: Path, *args: str, check=True):
    return run(["git", "-C", str(repo), *args], check=check)


def cwa(repo: Path, *args: str, check=True):
    p = run([sys.executable, str(CWA), "--repo", str(repo), *args], check=check)
    if p.returncode == 0 and p.stdout.strip().startswith("{"):
        return p, json.loads(p.stdout)
    return p, None


def commit_file(repo: Path, path: str, content: str, message: str):
    f = repo / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    git(repo, "add", path)
    git(repo, "commit", "-m", message)


def test_full_flow_and_conflict():
    with tempfile.TemporaryDirectory(prefix="cwa-test-") as td:
        root = Path(td) / "repo"
        root.mkdir()
        git(root, "init", "-b", "master")
        git(root, "config", "user.name", "CWA Test")
        git(root, "config", "user.email", "cwa@example.invalid")
        (root / "shared.txt").write_text("base\n", encoding="utf-8")
        (root / "independent.txt").write_text("base\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        git(root, "branch", "staging")
        master_before = git(root, "rev-parse", "master").stdout.strip()

        # Protected target must be rejected.
        p, _ = cwa(root, "init", "--target", "master", check=False)
        assert p.returncode != 0

        # Initialize staging coordination.
        p, init = cwa(root, "init", "--target", "staging")
        assert init["default_target"] == "staging"
        assert Path(init["state_root"]).exists()

        # Task A edits independent file and integrates cleanly.
        p, a = cwa(root, "start", "--title", "Task A", "--objective", "Change independent file",
                   "--claim", "independent.txt", "--acceptance", "independent file updated")
        wt_a = Path(a["worktree_path"])
        commit_file(wt_a, "independent.txt", "A\n", "task A")
        cwa(wt_a, "ready", "--test", "unit: PASS")
        staging_before_a = git(root, "rev-parse", "staging").stdout.strip()
        _, ia = cwa(wt_a, "integrate-begin")
        candidate_a = Path(ia["candidate_worktree"])
        # staging must still be unchanged while candidate exists.
        assert git(root, "rev-parse", "staging").stdout.strip() == staging_before_a
        cwa(candidate_a, "integrate-finish", "--test", "integration: PASS")
        staging_after_a = git(root, "rev-parse", "staging").stdout.strip()
        assert staging_after_a != staging_before_a
        assert git(root, "show", "staging:independent.txt").stdout == "A\n"
        assert git(root, "rev-parse", "master").stdout.strip() == master_before

        # Start B and C from the same current staging state; both edit shared.txt.
        _, b = cwa(root, "start", "--title", "Task B", "--objective", "Add B behavior",
                   "--claim", "shared.txt", "--acceptance", "B behavior present")
        _, c = cwa(root, "start", "--title", "Task C", "--objective", "Add C behavior",
                   "--claim", "shared.txt", "--acceptance", "C behavior present")
        wt_b = Path(b["worktree_path"])
        wt_c = Path(c["worktree_path"])
        commit_file(wt_b, "shared.txt", "base\nB\n", "task B")
        commit_file(wt_c, "shared.txt", "base\nC\n", "task C")
        cwa(wt_b, "event", "--type", "interface_change", "--summary", "B adds durable B behavior", "--file", "shared.txt")
        cwa(wt_c, "event", "--type", "interface_change", "--summary", "C adds durable C behavior", "--file", "shared.txt")
        cwa(wt_b, "ready", "--test", "B test: PASS")
        cwa(wt_c, "ready", "--test", "C test: PASS")

        # Integrate B first.
        _, ib = cwa(wt_b, "integrate-begin")
        cand_b = Path(ib["candidate_worktree"])
        cwa(cand_b, "integrate-finish", "--test", "B integration: PASS")
        assert git(root, "show", "staging:shared.txt").stdout == "base\nB\n"

        # C must now conflict against B in candidate, without damaging staging.
        staging_before_c = git(root, "rev-parse", "staging").stdout.strip()
        _, ic = cwa(wt_c, "integrate-begin")
        cand_c = Path(ic["candidate_worktree"])
        assert ic["status"] == "CONFLICT"
        assert "shared.txt" in ic["conflict_files"]
        assert git(root, "rev-parse", "staging").stdout.strip() == staging_before_c
        # Context should surface B's work.
        p, ctx = cwa(cand_c, "context", "--path", "shared.txt")
        assert any(t["task_id"] == b["task_id"] for t in ctx["tasks"])

        # Resolve semantically by preserving both behaviors.
        (cand_c / "shared.txt").write_text("base\nB\nC\n", encoding="utf-8")
        git(cand_c, "add", "shared.txt")
        cwa(cand_c, "event", "--type", "conflict_resolution", "--summary",
            "Preserved B behavior while adding C behavior", "--file", "shared.txt")
        # integrate-finish auto-completes MERGE_HEAD commit.
        cwa(cand_c, "integrate-finish", "--test", "B+C integration: PASS")
        assert git(root, "show", "staging:shared.txt").stdout == "base\nB\nC\n"
        assert git(root, "rev-parse", "master").stdout.strip() == master_before

        # Mutex must be free.
        _, st = cwa(root, "status", "--json")
        assert st["integration_lock"] is None
        task_states = {t["task_id"]: t["status"] for t in st["tasks"]}
        assert task_states[a["task_id"]] == "INTEGRATED"
        assert task_states[b["task_id"]] == "INTEGRATED"
        assert task_states[c["task_id"]] == "INTEGRATED"

        # Hard integration mutex: a second ready task cannot begin while D owns it.
        _, d = cwa(root, "start", "--title", "Task D", "--objective", "Add D file")
        _, e = cwa(root, "start", "--title", "Task E", "--objective", "Add E file")
        wt_d, wt_e = Path(d["worktree_path"]), Path(e["worktree_path"])
        commit_file(wt_d, "d.txt", "D\n", "task D")
        commit_file(wt_e, "e.txt", "E\n", "task E")
        cwa(wt_d, "ready", "--test", "D: PASS")
        cwa(wt_e, "ready", "--test", "E: PASS")
        _, id_ = cwa(wt_d, "integrate-begin")
        cand_d = Path(id_["candidate_worktree"])
        p, _ = cwa(wt_e, "integrate-begin", check=False)
        assert p.returncode != 0 and "lock" in p.stderr.lower()
        cwa(cand_d, "integrate-abort")
        _, st2 = cwa(root, "status", "--json")
        assert st2["integration_lock"] is None


def main():
    test_full_flow_and_conflict()
    print("PASS: cooperative worktree flow, protected target, transactional integration, and conflict resolution")


if __name__ == "__main__":
    main()
