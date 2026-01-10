"""
Builder Agent - Proposes safe, testable code improvements.

This agent is responsible for generating code proposals that:
1. Never modify main/master directly (all changes on proposal branches)
2. Always include tests
3. Avoid look-ahead bias and data leakage
4. Include rollback strategies
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


BUILDER_SYSTEM_PROMPT = """You are the Builder Agent for a Market Inefficiency Detection Platform.
Your job is to propose safe, testable code improvements that increase robustness and correctness.

NON-NEGOTIABLE SAFETY RULES:
1) You MUST NOT modify main/master directly. All changes are made on a proposal branch only.
2) You MUST NOT remove or weaken guardrails, approvals, risk scoring, or tests.
3) You MUST add or update tests for every behavior change.
4) You MUST avoid look-ahead bias, data leakage, and post-event data contamination.
5) You MUST NOT introduce network calls in unit tests.
6) If a change is risky, propose a safer alternative or add mitigation.

OUTPUT CONTRACT:
Return a single JSON object with:
- "title": short title
- "summary": what changed and why
- "files_changed": list of files you changed/added
- "risk_notes": bullet list of potential risks and mitigations
- "test_plan": exact commands to run
- "patch": unified diff (git diff format) for all changes

If you cannot produce a diff, return:
- "blocking_reason": why
- "suggested_next_steps": list
"""

BUILDER_DEVELOPER_PROMPT = """CONTEXT:
This platform detects market inefficiencies (crypto, equities, FX, etc.) and must remain robust and defensible.
The platform uses a multi-agent workflow:
- Builder proposes changes
- Validator runs tests / checks correctness
- Risk agent assigns risk scores
- Human approves merges

GOALS (in priority order):
A) Robustness: correctness, tests, reliability, no regressions
B) Clarity: readable code, clear interfaces, consistent patterns
C) Measurable value: improves detection signal quality or reduces false positives
D) Observability: logs/metrics for new features

REPO CONVENTIONS:
- All new logic must be behind feature flags or low-risk defaults when possible.
- Strategy code must have deterministic unit tests (use fixtures / static samples).
- Any LLM usage must be optional and mocked in tests.

WHAT YOU MUST PRODUCE EACH TIME:
1) A proposal branch name suggestion (e.g. "proposal/ineff-cds-signal-v2")
2) A unified diff patch with code + tests
3) A short "why this change" rationale
4) A risk self-assessment (LOW/MED/HIGH) with justification
5) A rollback note (how to disable / revert)
6) A list of files changed

{rejection_context}

TASK:
{task_description}
"""


class BuilderAgent:
    """
    Agent that proposes code changes in a safe, branch-based workflow.
    """
    
    def __init__(self, openai_client=None):
        self.openai_client = openai_client
        self.model = "gpt-4o"
    
    def _get_openai_client(self):
        """Lazy load OpenAI client using Replit's modelfarm integration."""
        if self.openai_client is None:
            try:
                import os
                from openai import OpenAI
                
                api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
                base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
                
                if not api_key:
                    logger.error("No OpenAI API key found in OPENAI_API_KEY or AI_INTEGRATIONS_OPENAI_API_KEY")
                    return None
                
                if base_url:
                    self.openai_client = OpenAI(api_key=api_key, base_url=base_url)
                    logger.info(f"BuilderAgent initialized with modelfarm base_url")
                else:
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("BuilderAgent initialized with default OpenAI endpoint")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                return None
        return self.openai_client
    
    def _get_rejection_context(self) -> str:
        """Get recent rejection reasons to inject into prompt."""
        try:
            from services.agent_memory import get_recent_builder_rejections, format_rejection_context
            rejections = get_recent_builder_rejections(limit=5)
            return format_rejection_context(rejections)
        except Exception as e:
            logger.warning(f"Could not load rejection context: {e}")
            return ""
    
    def propose_change(
        self,
        task_description: str,
        context_files: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a code proposal for the given task.
        
        Args:
            task_description: What change is needed
            context_files: Optional dict of {filepath: content} for context
            
        Returns:
            Dict with proposal details or error info
        """
        client = self._get_openai_client()
        if client is None:
            return {
                "blocking_reason": "OpenAI client not available",
                "suggested_next_steps": ["Check API key configuration"]
            }
        
        rejection_context = self._get_rejection_context()
        
        developer_prompt = BUILDER_DEVELOPER_PROMPT.format(
            rejection_context=rejection_context,
            task_description=task_description
        )
        
        if context_files:
            files_context = "\n\nRELEVANT FILES:\n"
            for path, content in context_files.items():
                truncated = content[:2000] + "..." if len(content) > 2000 else content
                files_context += f"\n--- {path} ---\n{truncated}\n"
            developer_prompt += files_context
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": BUILDER_SYSTEM_PROMPT},
                    {"role": "user", "content": developer_prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            
            try:
                json_match = content
                if "```json" in content:
                    json_match = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    json_match = content.split("```")[1].split("```")[0]
                
                proposal = json.loads(json_match.strip())
                return proposal
            except json.JSONDecodeError:
                return {
                    "title": "Unparseable response",
                    "summary": content[:500],
                    "raw_response": content,
                    "blocking_reason": "Response was not valid JSON"
                }
                
        except Exception as e:
            logger.error(f"Builder agent error: {e}")
            return {
                "blocking_reason": str(e),
                "suggested_next_steps": ["Check API connectivity", "Review error logs"]
            }
    
    def create_proposal_record(
        self,
        proposal_data: Dict[str, Any],
        branch_name: str
    ) -> Optional[int]:
        """
        Create a Proposal record in the database.
        
        Returns the proposal ID if successful, None otherwise.
        """
        try:
            from app import db
            from models import Proposal
            from services.risk_scoring import score_proposal
            
            diff_text = proposal_data.get("patch", "")
            
            risk_score, risk_tier, _, risk_reason = score_proposal(diff_text)
            
            proposal = Proposal(
                title=proposal_data.get("title", "Untitled Proposal"),
                branch_name=branch_name,
                summary=proposal_data.get("summary", ""),
                diff_text=diff_text,
                risk_score=risk_score,
                risk_tier=risk_tier,
                risk_reason=risk_reason,
                status="PENDING"
            )
            
            db.session.add(proposal)
            db.session.commit()
            
            logger.info(f"Created proposal #{proposal.id}: {proposal.title} (risk: {risk_tier})")
            return proposal.id
            
        except Exception as e:
            logger.error(f"Failed to create proposal record: {e}")
            return None
    
    def generate_branch_name(self, title: str) -> str:
        """Generate a safe branch name from a title."""
        import re
        safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower())
        safe_title = safe_title[:40].strip('-')
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        return f"proposal/{safe_title}-{timestamp}"


def get_builder_prompts() -> Dict[str, str]:
    """Return the Builder Agent prompts for external use."""
    return {
        "system": BUILDER_SYSTEM_PROMPT,
        "developer_template": BUILDER_DEVELOPER_PROMPT
    }
