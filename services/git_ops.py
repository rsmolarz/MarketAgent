import subprocess
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def run_git(args: list, cwd: str = ".", timeout: int = 20) -> Tuple[int, str, str]:
    """Execute a git command and return (returncode, stdout, stderr)."""
    p = subprocess.Popen(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        logger.error(f"Git command timed out: git {' '.join(args)}")
        return 124, out, err
    return p.returncode, out, err


def get_diff_against_main(branch_name: str) -> str:
    """Get the diff between main and the specified branch."""
    rc, out, err = run_git(["diff", f"main...{branch_name}"], timeout=30)
    if rc != 0:
        raise RuntimeError(f"git diff failed: {err.strip()}")
    return out


def get_current_branch() -> str:
    """Get the name of the current branch."""
    rc, out, err = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if rc != 0:
        raise RuntimeError(f"Failed to get current branch: {err.strip()}")
    return out.strip()


def branch_exists(branch_name: str) -> bool:
    """Check if a branch exists."""
    rc, _, _ = run_git(["rev-parse", "--verify", branch_name])
    return rc == 0


def create_branch(branch_name: str, from_ref: str = "main") -> None:
    """Create a new branch from the specified ref."""
    rc, out, err = run_git(["checkout", "-b", branch_name, from_ref])
    if rc != 0:
        raise RuntimeError(f"Failed to create branch {branch_name}: {err.strip()}")


def checkout_branch(branch_name: str) -> None:
    """Checkout an existing branch."""
    rc, out, err = run_git(["checkout", branch_name])
    if rc != 0:
        raise RuntimeError(f"Failed to checkout {branch_name}: {err.strip()}")


def merge_branch_to_main(branch_name: str, push: bool = False) -> None:
    """
    Merge a branch into main.
    
    SAFETY: This should only be called after admin approval.
    """
    steps = [
        (["checkout", "main"], "checkout main"),
        (["pull", "--ff-only"], "pull latest main"),
        (["merge", "--no-ff", branch_name, "-m", f"Merge {branch_name}"], f"merge {branch_name}")
    ]
    
    for args, desc in steps:
        rc, out, err = run_git(args, timeout=60)
        if rc != 0:
            raise RuntimeError(f"Failed to {desc}: {err.strip()}")
    
    if push:
        rc, out, err = run_git(["push", "origin", "main"], timeout=60)
        if rc != 0:
            raise RuntimeError(f"Failed to push to main: {err.strip()}")


def get_staged_diff() -> str:
    """Get the diff of staged changes."""
    rc, out, err = run_git(["diff", "--cached"])
    if rc != 0:
        raise RuntimeError(f"Failed to get staged diff: {err.strip()}")
    return out


def get_unstaged_diff() -> str:
    """Get the diff of unstaged changes."""
    rc, out, err = run_git(["diff"])
    if rc != 0:
        raise RuntimeError(f"Failed to get unstaged diff: {err.strip()}")
    return out


def stage_all() -> None:
    """Stage all changes."""
    rc, out, err = run_git(["add", "-A"])
    if rc != 0:
        raise RuntimeError(f"Failed to stage changes: {err.strip()}")


def commit(message: str) -> None:
    """Create a commit with the given message."""
    rc, out, err = run_git(["commit", "-m", message])
    if rc != 0:
        raise RuntimeError(f"Failed to commit: {err.strip()}")


def reset_hard(ref: str = "HEAD") -> None:
    """Hard reset to the specified ref."""
    rc, out, err = run_git(["reset", "--hard", ref])
    if rc != 0:
        raise RuntimeError(f"Failed to reset: {err.strip()}")


def delete_branch(branch_name: str, force: bool = False) -> None:
    """Delete a branch."""
    flag = "-D" if force else "-d"
    rc, out, err = run_git(["branch", flag, branch_name])
    if rc != 0:
        raise RuntimeError(f"Failed to delete branch {branch_name}: {err.strip()}")
