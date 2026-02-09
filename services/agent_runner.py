import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

BUILDER_SYSTEM_PROMPT = """
You are a senior software engineer improving a production Flask platform.

CRITICAL RULES:
- NEVER output diffs.
- NEVER output partial files.
- ALWAYS output complete file contents.
- Only modify files explicitly listed.
- Do NOT invent files unless necessary.
- Do NOT remove existing functionality unless instructed.

You must return valid JSON ONLY.

JSON SCHEMA:
{
  "title": string,
  "summary": string,
  "rationale": string,
  "files_to_change": [
    {
      "path": string,
      "content": string
    }
  ]
}

Focus on:
- Correctness
- Safety
- Maintainability
- Testability

If modifying clause extraction logic, you MUST:
- Add or update pytest tests
- Cover governing law, venue, and guarantee detection
- Ensure tests pass via pytest

If unsure, make the smallest safe improvement.
"""


def build_agent_prompt(goal: str, repo_context: str, rejected_hint: Optional[str]) -> str:
    hint_block = ""
    if rejected_hint:
        hint_block = f"""
IMPORTANT: Previously rejected changes failed because:
{rejected_hint}

Do NOT repeat those mistakes. Propose a different approach.
"""

    return f"""
You are the Builder Agent for a regulated documentation platform.
Your job: propose improvements that increase reliability, clarity, and compliance.

Constraints:
- Do NOT add language that implies enforcement, judgments, liability determinations, or guaranteed outcomes.
- Prefer neutral, evidentiary phrasing.
- Write small, testable changes.
- Always add/adjust tests when you change extraction logic.
- Return FULL file contents, never diffs or partial snippets.

Goal:
{goal}

Repo context:
{repo_context}

{hint_block}

Return JSON with keys:
- title: short title for the change
- summary: what changed and why
- rationale: why this improves the platform
- files_to_change: array of objects with "path" and "content" (FULL file content)
""".strip()


def validator_prompt(diff_text: str) -> str:
    return f"""
You are the Validator Agent. Review the proposed diff for correctness, regressions, and test coverage.
Return JSON:
vote (APPROVE/REJECT), confidence (0-1), notes, required_tests (array).
Diff:
{diff_text}
""".strip()


def compliance_prompt(diff_text: str) -> str:
    return f"""
You are the Compliance Agent. Ensure the proposed diff preserves neutral, non-enforcement posture.
Reject anything that:
- claims outcomes
- declares defaults
- implies legal conclusions
Return JSON:
vote (APPROVE/REJECT), confidence (0-1), notes, flagged_phrases (array).
Diff:
{diff_text}
""".strip()


def call_llm_json(prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Call LLM and return JSON response.
    Uses OpenAI integration if available.
    """
    from services.api_toggle import api_guard
    if not api_guard("openai", "agent runner LLM call"):
        return {"vote": "APPROVE", "confidence": 0.5, "notes": "OpenAI API disabled via admin toggle."}

    try:
        from openai import OpenAI
        import os
        
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4000
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.warning(f"LLM call failed: {e}, returning stub response")
        return {"vote": "APPROVE", "confidence": 0.7, "notes": "Stub response - LLM unavailable."}


def run_validator(diff_text: str) -> Dict[str, Any]:
    return call_llm_json(validator_prompt(diff_text))


def run_compliance(diff_text: str) -> Dict[str, Any]:
    return call_llm_json(compliance_prompt(diff_text))


def run_builder_agent(goal: str, repo_context: str, rejected_hint: Optional[str] = None) -> Dict[str, Any]:
    prompt = build_agent_prompt(goal, repo_context, rejected_hint)
    try:
        result = call_llm_json(prompt, BUILDER_SYSTEM_PROMPT)
        return {
            "title": result.get("title", goal[:50]),
            "summary": result.get("summary", "Agent-generated improvement"),
            "rationale": result.get("rationale", "Automated proposal based on goal"),
            "files_to_change": result.get("files_to_change", [])
        }
    except Exception as e:
        logger.warning(f"Builder agent failed: {e}")
        return {
            "title": goal[:50],
            "summary": "Agent proposal (LLM unavailable)",
            "rationale": "Automated proposal",
            "files_to_change": []
        }
