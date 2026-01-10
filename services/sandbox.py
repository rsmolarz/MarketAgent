import os
import subprocess
import tempfile
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False


def _limit_resources():
    """Set resource limits for sandbox execution (Linux only)."""
    if not HAS_RESOURCE:
        return
    
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10_000_000, 10_000_000))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_AS, (1_500_000_000, 1_500_000_000))
    except Exception as e:
        logger.warning(f"Could not set resource limits: {e}")


def run_in_sandbox(
    repo_dir: str,
    branch: str,
    command: list,
    timeout: int = 60,
    env_overrides: Optional[dict] = None
) -> Tuple[int, str, str]:
    """
    Run a command in a sandboxed copy of the repository.
    
    Copies repo to a temp dir, checks out branch, runs command with resource limits.
    Does not alter the working repo.
    
    Args:
        repo_dir: Path to the repository
        branch: Branch to checkout
        command: Command to run (as list of strings)
        timeout: Execution timeout in seconds
        env_overrides: Additional environment variables to set
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    tmp = tempfile.mkdtemp(prefix="sandbox_")
    try:
        shutil.copytree(repo_dir, os.path.join(tmp, "repo"), dirs_exist_ok=True)
        cwd = os.path.join(tmp, "repo")

        checkout_result = subprocess.run(
            ["git", "checkout", branch],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if checkout_result.returncode != 0:
            return checkout_result.returncode, "", f"Checkout failed: {checkout_result.stderr}"

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["ENVIRONMENT"] = "sandbox"
        
        sensitive_keys = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN",
            "SENDGRID_API_KEY", "DATABASE_URL", "SESSION_SECRET"
        ]
        for key in sensitive_keys:
            env.pop(key, None)
        
        if env_overrides:
            env.update(env_overrides)

        preexec_fn = _limit_resources if HAS_RESOURCE else None

        p = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            preexec_fn=preexec_fn
        )
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Sandbox command timed out after {timeout}s")
        return 124, "", "Sandbox command timed out"
    except Exception as e:
        logger.error(f"Sandbox error: {e}")
        return 1, "", f"Sandbox error: {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_tests_in_sandbox(
    repo_dir: str,
    branch: str,
    test_command: Optional[list] = None,
    timeout: int = 120
) -> Tuple[bool, str]:
    """
    Run tests in a sandboxed environment.
    
    Args:
        repo_dir: Path to the repository
        branch: Branch to test
        test_command: Custom test command (defaults to pytest)
        timeout: Test timeout in seconds
        
    Returns:
        Tuple of (passed: bool, report: str)
    """
    if test_command is None:
        test_command = ["pytest", "-q", "--tb=short"]
    
    rc, out, err = run_in_sandbox(repo_dir, branch, test_command, timeout)
    
    report = f"Exit code: {rc}\n\n"
    if out:
        report += f"=== STDOUT ===\n{out}\n"
    if err:
        report += f"=== STDERR ===\n{err}\n"
    
    report = report[:50000]
    
    return rc == 0, report


def validate_syntax_in_sandbox(
    repo_dir: str,
    branch: str,
    files: Optional[list] = None
) -> Tuple[bool, str]:
    """
    Validate Python syntax in sandbox.
    
    Args:
        repo_dir: Path to the repository
        branch: Branch to validate
        files: Specific files to check (defaults to all .py files)
        
    Returns:
        Tuple of (valid: bool, report: str)
    """
    if files:
        command = ["python", "-m", "py_compile"] + files
    else:
        command = ["sh", "-c", "find . -name '*.py' -not -path './.git/*' | xargs python -m py_compile"]
    
    rc, out, err = run_in_sandbox(repo_dir, branch, command, timeout=30)
    
    if rc == 0:
        return True, "All Python files have valid syntax"
    else:
        return False, f"Syntax errors found:\n{err}"
