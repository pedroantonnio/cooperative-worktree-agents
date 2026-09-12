#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
CWA = HERE / "cwa.py"


def load_cwa_module():
    spec = importlib.util.spec_from_file_location("cwa_under_test", CWA)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(cmd, cwd=None, check=True):
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
    )
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
        # init defaults to the branch currently checked out.
        p, init = cwa(root, "init")
        assert init["default_target"] == "master"
        assert Path(init["state_root"]).exists()

        # Task A edits independent file and integrates cleanly.
        p, a = cwa(root, "start", "--title", "Task A", "--objective", "Change independent file",
                   "--claim", "independent.txt", "--acceptance", "independent file updated")
        wt_a = Path(a["worktree_path"])
        commit_file(wt_a, "independent.txt", "A\n", "task A")
        cwa(wt_a, "ready", "--test", "unit: PASS")
        target_before_a = git(root, "rev-parse", "master").stdout.strip()
        _, ia = cwa(wt_a, "integrate-begin")
        candidate_a = Path(ia["candidate_worktree"])
        # target must still be unchanged while candidate exists.
        assert git(root, "rev-parse", "master").stdout.strip() == target_before_a
        cwa(candidate_a, "integrate-finish", "--test", "integration: PASS")
        target_after_a = git(root, "rev-parse", "master").stdout.strip()
        assert target_after_a != target_before_a
        assert git(root, "show", "master:independent.txt").stdout == "A\n"

        # Start B and C from the same current target state; both edit shared.txt.
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
        assert git(root, "show", "master:shared.txt").stdout == "base\nB\n"

        # C must now conflict against B in candidate, without damaging the target.
        target_before_c = git(root, "rev-parse", "master").stdout.strip()
        _, ic = cwa(wt_c, "integrate-begin")
        cand_c = Path(ic["candidate_worktree"])
        assert ic["status"] == "CONFLICT"
        assert "shared.txt" in ic["conflict_files"]
        assert git(root, "rev-parse", "master").stdout.strip() == target_before_c
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
        assert git(root, "show", "master:shared.txt").stdout == "base\nB\nC\n"

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


def test_git_metadata_permission_guidance():
    module = load_cwa_module()
    detail = (
        "fatal: cannot lock ref "
        "'refs/heads/task/t-test': Unable to create "
        "'C:/repo/.git/refs/heads/task/t-test.lock': Permission denied"
    )
    guided = module.git_failure_guidance(
        ["git", "-C", "C:/repo", "worktree", "add", "-b", "task/t-test"],
        detail,
    )
    assert "managed Codex sandbox" in guided
    assert "Do NOT bypass" in guided
    assert "user-approved mode" in guided
    assert "not a cwa.py flag" in guided

    ordinary = "fatal: branch missing not found"
    assert module.git_failure_guidance(["git", "show", "missing"], ordinary) == ordinary


def test_status_preserves_utf8_and_supports_task_filters():
    with tempfile.TemporaryDirectory(prefix="cwa-utf8-status-") as td:
        root = Path(td) / "repo"
        root.mkdir()
        git(root, "init", "-b", "master")
        git(root, "config", "user.name", "CWA Test")
        git(root, "config", "user.email", "cwa@example.invalid")
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        git(root, "branch", "feature/current")

        cwa(root, "init", "--target", "feature/current")
        git(root, "switch", "master")
        _, task = cwa(
            root,
            "start",
            "--title",
            "Tarefa de revisão — UTF-8",
            "--objective",
            "Preservar informação acentuada no ledger",
            "--claim",
            "base.txt",
        )

        assert task["target_branch"] == "master"

        human = run(
            [sys.executable, str(CWA), "--repo", str(root), "status"],
            check=True,
        )
        assert "Tarefa de revisão — UTF-8" in human.stdout

        _, by_task = cwa(root, "status", "--json", "--task", task["task_id"])
        assert [item["task_id"] for item in by_task["tasks"]] == [task["task_id"]]

        _, by_target = cwa(root, "status", "--json", "--target", "master")
        assert [item["task_id"] for item in by_target["tasks"]] == [task["task_id"]]

        _, active = cwa(root, "status", "--json", "--active")
        assert [item["task_id"] for item in active["tasks"]] == [task["task_id"]]



def test_dirty_primary_is_parked_and_final_code_returns_to_primary():
    with tempfile.TemporaryDirectory(prefix="cwa-primary-handoff-") as td:
        root = Path(td) / "repo"
        root.mkdir()
        git(root, "init", "-b", "master")
        git(root, "config", "user.name", "CWA Test")
        git(root, "config", "user.email", "cwa@example.invalid")
        (root / "base.txt").write_text("base\n", encoding="utf-8")
        git(root, "add", ".")
        git(root, "commit", "-m", "initial")
        git(root, "branch", "feature/current")
        git(root, "switch", "feature/current")

        _, init = cwa(root, "init", "--target", "feature/current")
        assert Path(init["primary_worktree"]).resolve() == root.resolve()

        _, task = cwa(
            root,
            "start",
            "--title",
            "Primary handoff",
            "--objective",
            "Verify final code returns to primary",
            "--claim",
            "feature.txt",
            "--acceptance",
            "feature exists in primary",
        )
        task_wt = Path(task["worktree_path"])
        commit_file(task_wt, "feature.txt", "integrated\n", "feature")
        cwa(task_wt, "ready", "--test", "task verification: PASS")

        (root / "base.txt").write_text("user staged change\n", encoding="utf-8")
        git(root, "add", "base.txt")
        (root / "notes.local").write_text("keep me\n", encoding="utf-8")

        source_cached = git(root, "diff", "--cached", "--binary").stdout
        source_status = git(root, "status", "--porcelain").stdout

        _, begin = cwa(task_wt, "integrate-begin")
        assert begin["status"] == "INTEGRATION_VALIDATION"
        assert len(begin["primary_preservations"]) == 1

        preserved_info = begin["primary_preservations"][0]
        preserved = Path(preserved_info["preservation_worktree"])
        preserved_branch = preserved_info["preservation_branch"]

        assert preserved.exists()
        assert git(preserved, "diff", "--cached", "--binary").stdout == source_cached
        assert git(preserved, "status", "--porcelain").stdout == source_status
        assert (preserved / "notes.local").read_text(encoding="utf-8") == "keep me\n"

        candidate = Path(begin["candidate_worktree"])

        missing_evidence, _ = cwa(candidate, "integrate-finish", check=False)
        assert missing_evidence.returncode != 0
        assert "requires at least one verified combined-state test result" in missing_evidence.stderr

        _, finish = cwa(
            candidate,
            "integrate-finish",
            "--test",
            "combined validation native exit code 0: PASS",
        )

        assert finish["status"] == "INTEGRATED"
        assert Path(finish["primary_worktree"]).resolve() == root.resolve()
        assert git(root, "branch", "--show-current").stdout.strip() == "feature/current"
        assert git(root, "rev-parse", "HEAD").stdout.strip() == finish["integrated_sha"]
        assert git(root, "show", "HEAD:feature.txt").stdout == "integrated\n"
        assert git(root, "status", "--porcelain").stdout == ""

        assert git(preserved, "branch", "--show-current").stdout.strip() == preserved_branch
        assert git(preserved, "diff", "--cached", "--binary").stdout == source_cached
        assert git(preserved, "status", "--porcelain").stdout == source_status
        assert (preserved / "notes.local").read_text(encoding="utf-8") == "keep me\n"

        wrong_cleanup, _ = cwa(task_wt, "cleanup", "--task", task["task_id"], check=False)
        assert wrong_cleanup.returncode != 0
        assert "configured primary project folder" in wrong_cleanup.stderr

        _, cleaned = cwa(root, "cleanup", "--task", task["task_id"])
        assert cleaned["cleanup_complete"] is True
        assert len(cleaned["removed_worktrees"]) == 2
        assert cleaned["removed_branches"]
        assert cleaned["integration_lock"] is None
        assert not task_wt.exists()
        assert not candidate.exists()
        assert git(root, "branch", "--show-current").stdout.strip() == "feature/current"
        assert git(root, "show", "HEAD:feature.txt").stdout == "integrated\n"


def main():
    test_git_metadata_permission_guidance()
    test_full_flow_and_conflict()
    test_status_preserves_utf8_and_supports_task_filters()
    test_dirty_primary_is_parked_and_final_code_returns_to_primary()
    print(
        "PASS: cooperative worktree flow, primary handoff, dirty-work preservation, "
        "mandatory cleanup, protected target, transactional integration, and conflict resolution"
    )

if __name__ == "__main__":
    main()
