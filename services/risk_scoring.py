import re
from collections import defaultdict
from typing import Dict, Tuple, List


RISK_TIERS = {
    "LOW": (0, 24),
    "MED": (25, 59),
    "HIGH": (60, 100)
}


def get_risk_tier(score: int) -> str:
    """Convert a risk score (0-100) to tier name."""
    if score <= 24:
        return "LOW"
    elif score <= 59:
        return "MED"
    else:
        return "HIGH"


def score_correctness_bias(diff_text: str, file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Category A: Correctness & Bias (0-40)
    - +0-10: Introduces or increases false positives / untested assumptions
    - +0-15: Any sign of look-ahead bias or future leakage (hard block if confirmed)
    - +0-10: Uses data that may not be available at decision time
    - +0-5: Strategy logic changes without backtest harness update
    """
    score = 0
    reasons = []
    diff_lower = diff_text.lower()
    
    look_ahead_patterns = [
        r"\.shift\s*\(\s*-",
        r"future_",
        r"next_day",
        r"tomorrow",
        r"\.iloc\s*\[\s*i\s*\+\s*\d",
    ]
    for pattern in look_ahead_patterns:
        if re.search(pattern, diff_lower):
            score += 15
            reasons.append("Potential look-ahead bias detected")
            break
    
    data_leakage_terms = ["train", "test", "split", "fit_transform", "y_train"]
    leakage_count = sum(1 for term in data_leakage_terms if term in diff_lower)
    if leakage_count >= 2:
        score += 10
        reasons.append("Possible data leakage in train/test handling")
    
    strategy_files = ["strategy", "signal", "predictor", "analyzer"]
    changes_strategy = any(sf in fp.lower() for fp in file_paths for sf in strategy_files)
    has_backtest_update = "backtest" in diff_lower or "test_" in diff_lower
    if changes_strategy and not has_backtest_update:
        score += 5
        reasons.append("Strategy changes without backtest updates")
    
    return min(40, score), reasons


def score_operational_risk(diff_text: str, file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Category B: Operational Risk (0-20)
    - +0-10: Performance regression (O(n^2), large memory, unbounded loops)
    - +0-5: Adds new external dependencies or fragile integrations
    - +0-5: Adds cron/scheduler tasks without idempotency / locking
    """
    score = 0
    reasons = []
    diff_lower = diff_text.lower()
    
    perf_patterns = [
        (r"for\s+\w+\s+in\s+.*:\s*\n.*for\s+\w+\s+in", 8, "Nested loops detected"),
        (r"\.append\s*\(.*\)\s*\n.*for", 5, "Append in loop pattern"),
        (r"while\s+True", 7, "Unbounded while loop"),
    ]
    for pattern, points, reason in perf_patterns:
        if re.search(pattern, diff_text):
            score += points
            reasons.append(reason)
            break
    
    new_imports = re.findall(r"^\+\s*import\s+(\w+)", diff_text, re.MULTILINE)
    new_imports += re.findall(r"^\+\s*from\s+(\w+)", diff_text, re.MULTILINE)
    external_deps = [imp for imp in new_imports if imp not in 
                     ["os", "sys", "re", "json", "datetime", "logging", "typing", "flask"]]
    if len(external_deps) > 2:
        score += 5
        reasons.append(f"New external dependencies: {', '.join(external_deps[:3])}")
    
    scheduler_terms = ["apscheduler", "cron", "interval", "add_job"]
    has_scheduler = any(term in diff_lower for term in scheduler_terms)
    has_locking = "lock" in diff_lower or "idempotent" in diff_lower
    if has_scheduler and not has_locking:
        score += 5
        reasons.append("Scheduler task without apparent locking")
    
    return min(20, score), reasons


def score_security_secrets(diff_text: str, file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Category C: Security & Secrets (0-15)
    - +0-10: New code touches auth/session/permissions/admin routes
    - +0-5: Potential exposure of secrets/logging sensitive data
    """
    score = 0
    reasons = []
    diff_lower = diff_text.lower()
    
    auth_patterns = ["login", "logout", "session", "token", "password", "auth", "permission", "admin"]
    auth_touched = sum(1 for pat in auth_patterns if pat in diff_lower)
    if auth_touched >= 2:
        score += min(10, auth_touched * 2)
        reasons.append("Modifies authentication/authorization code")
    
    secret_patterns = [
        r"api_key\s*=",
        r"secret\s*=",
        r"password\s*=",
        r"\.log\(.*password",
        r"print\(.*secret",
    ]
    for pattern in secret_patterns:
        if re.search(pattern, diff_lower):
            score += 5
            reasons.append("Potential secret exposure in code")
            break
    
    return min(15, score), reasons


def score_test_coverage(diff_text: str, file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Category D: Test Coverage & Regression Risk (0-15)
    - +0-10: Insufficient unit tests for changed behavior
    - +0-5: Removes or weakens tests / snapshots / guards (hard block)
    """
    score = 0
    reasons = []
    
    test_files = [fp for fp in file_paths if "test" in fp.lower()]
    code_files = [fp for fp in file_paths if "test" not in fp.lower() and fp.endswith(".py")]
    
    if len(code_files) > 0 and len(test_files) == 0:
        score += 8
        reasons.append("Code changes without corresponding test updates")
    
    removed_tests = re.findall(r"^-\s*def test_\w+", diff_text, re.MULTILINE)
    removed_asserts = re.findall(r"^-\s*assert\s+", diff_text, re.MULTILINE)
    if len(removed_tests) > 0:
        score += 5
        reasons.append(f"Removed {len(removed_tests)} test function(s)")
    if len(removed_asserts) > len(re.findall(r"^\+\s*assert\s+", diff_text, re.MULTILINE)):
        score += 3
        reasons.append("Net reduction in assertions")
    
    return min(15, score), reasons


def score_maintainability(diff_text: str, file_paths: List[str]) -> Tuple[int, List[str]]:
    """
    Category E: Maintainability (0-10)
    - +0-5: Large refactor without clear benefit
    - +0-5: Inconsistent patterns / unclear interfaces
    """
    score = 0
    reasons = []
    
    adds = len(re.findall(r"^\+(?!\+\+).*$", diff_text, re.MULTILINE))
    removes = len(re.findall(r"^-(?!\-\-).*$", diff_text, re.MULTILINE))
    total_changes = adds + removes
    
    if total_changes > 500:
        score += 5
        reasons.append("Large change set (500+ lines)")
    elif total_changes > 200:
        score += 2
        reasons.append("Medium-sized change set")
    
    if len(file_paths) > 10:
        score += 3
        reasons.append(f"Changes span {len(file_paths)} files")
    
    return min(10, score), reasons


def score_proposal(diff_text: str) -> Tuple[int, str, Dict[str, int]]:
    """
    Score a proposal using the tiered rubric.
    
    Returns: (overall_score: 0-100, tier: LOW/MED/HIGH, category_scores: dict)
    """
    file_headers = re.findall(r"^\+\+\+ b/(.+)$", diff_text, flags=re.MULTILINE)
    
    all_reasons = []
    category_scores = {}
    
    correctness_score, correctness_reasons = score_correctness_bias(diff_text, file_headers)
    category_scores["correctness_bias"] = correctness_score
    all_reasons.extend(correctness_reasons)
    
    operational_score, operational_reasons = score_operational_risk(diff_text, file_headers)
    category_scores["operational_risk"] = operational_score
    all_reasons.extend(operational_reasons)
    
    security_score, security_reasons = score_security_secrets(diff_text, file_headers)
    category_scores["security_secrets"] = security_score
    all_reasons.extend(security_reasons)
    
    test_score, test_reasons = score_test_coverage(diff_text, file_headers)
    category_scores["test_coverage"] = test_score
    all_reasons.extend(test_reasons)
    
    maint_score, maint_reasons = score_maintainability(diff_text, file_headers)
    category_scores["maintainability"] = maint_score
    all_reasons.extend(maint_reasons)
    
    base_score = sum(category_scores.values())
    
    breadth_bump = min(10, 2 * len(file_headers))
    
    overall_score = min(100, base_score + breadth_bump)
    tier = get_risk_tier(overall_score)
    
    reason_text = "; ".join(all_reasons) if all_reasons else "No significant risks identified"
    
    return overall_score, tier, category_scores, reason_text


def score_diff(unified_diff: str) -> Tuple[Dict[str, float], float]:
    """
    Legacy interface for backwards compatibility.
    Returns: (per_file_risk, overall_risk) where risk is 0-1.
    """
    RISK_FILE_WEIGHTS = {
        "requirements": 0.9,
        "Dockerfile": 0.8,
        "migrations": 0.8,
        "models.py": 0.7,
        "auth": 0.7,
        "billing": 0.8,
        "templates/": 0.4,
        "static/": 0.3,
        "tests/": 0.2,
    }
    
    def _file_weight(path: str) -> float:
        for k, w in RISK_FILE_WEIGHTS.items():
            if k in path:
                return w
        return 0.5
    
    per_file = defaultdict(float)
    file_headers = re.findall(r"^\+\+\+ b/(.+)$", unified_diff, flags=re.MULTILINE)
    chunks = re.split(r"^\+\+\+ b/.+$", unified_diff, flags=re.MULTILINE)

    for i, path in enumerate(file_headers):
        body = chunks[i + 1] if i + 1 < len(chunks) else ""
        add = len(re.findall(r"^\+(?!\+\+).*$", body, flags=re.MULTILINE))
        rem = len(re.findall(r"^-(?!\-\-).*$", body, flags=re.MULTILINE))
        changes = add + rem

        magnitude = min(1.0, changes / 200.0)

        keywords = 0
        for kw in ["payment", "auth", "token", "enforce", "lawsuit", "default", "judgment", "stripe", "secret"]:
            if kw in body.lower():
                keywords += 1
        keyword_risk = min(0.4, keywords * 0.08)

        per_file[path] = min(1.0, 0.2 + magnitude * 0.6 + keyword_risk + _file_weight(path) * 0.2)

    overall = 0.0
    if per_file:
        overall = sum(per_file.values()) / len(per_file)
    return dict(per_file), float(min(1.0, overall))
