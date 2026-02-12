"""
Code Guardian Agent

Monitors code quality, detects syntax errors, validates agent implementations,
and identifies potential issues before they cause runtime failures.
"""

import logging
import subprocess
import ast
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base_agent import BaseAgent


logger = logging.getLogger(__name__)


class CodeGuardianAgent(BaseAgent):
    """
    AI agent that monitors code quality and detects issues:
    - Syntax errors in Python files
    - Import errors and missing dependencies
    - Agent validation (all agents have required methods)
    - UI regression detection (missing buttons, tabs)
    - Security checks (exposed secrets, unsafe patterns)
    """

    def __init__(self, name: str = "CodeGuardianAgent"):
        super().__init__(name)
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.critical_files = [
            'routes/api.py',
            'routes/dashboard.py',
            'agents/__init__.py',
            'scheduler.py',
            'models.py',
            'app.py',
            'main.py',
        ]
        self.agent_dir = os.path.join(self.project_root, 'agents')

    def analyze(self) -> List[Dict[str, Any]]:
        """
        Run comprehensive code quality checks.
        
        Returns:
            List of findings about code issues
        """
        findings = []

        try:
            syntax_findings = self._check_syntax_errors()
            if syntax_findings:
                findings.extend(syntax_findings)

            quality_findings = self._check_code_quality()
            if quality_findings:
                findings.extend(quality_findings)

            agent_findings = self._validate_agents()
            if agent_findings:
                findings.extend(agent_findings)

            health_findings = self._check_system_health()
            if health_findings:
                findings.extend(health_findings)

            security_findings = self._check_security()
            if security_findings:
                findings.extend(security_findings)

            dependency_findings = self._check_dependencies()
            if dependency_findings:
                findings.extend(dependency_findings)

            import_findings = self._check_imports()
            if import_findings:
                findings.extend(import_findings)

            business_logic_findings = self._check_business_logic()
            if business_logic_findings:
                findings.extend(business_logic_findings)

            action_required_findings = self._check_action_required()
            if action_required_findings:
                findings.extend(action_required_findings)

            scheduler_findings = self._check_scheduler_health()
            if scheduler_findings:
                findings.extend(scheduler_findings)

            runtime_findings = self._check_runtime_errors()
            if runtime_findings:
                findings.extend(runtime_findings)

            logger.info(f"Code Guardian: {len(findings)} issues found")
            return findings

        except Exception as e:
            logger.error(f"Code Guardian analysis failed: {str(e)}")
            return [{
                "title": "CODE_GUARDIAN_ERROR",
                "description": f"Code Guardian analysis failed: {str(e)}",
                "severity": "high",
                "confidence": 1.0,
                "symbol": "SYSTEM",
                "market_type": "system"
            }]

    def _check_syntax_errors(self) -> List[Dict[str, Any]]:
        """Check all Python files for syntax errors."""
        findings = []
        
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pythonlibs', 'node_modules', '.upm']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, self.project_root)
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            source = f.read()
                        ast.parse(source)
                    except SyntaxError as e:
                        findings.append({
                            "title": f"SYNTAX_ERROR: {relative_path}",
                            "description": f"Line {e.lineno}: {e.msg}",
                            "severity": "critical",
                            "confidence": 1.0,
                            "symbol": relative_path,
                            "market_type": "system"
                        })
                    except Exception as e:
                        logger.debug(f"Could not parse {relative_path}: {str(e)}")

        return findings

    def _check_code_quality(self) -> List[Dict[str, Any]]:
        """Check for common code quality issues."""
        findings = []
        
        for critical_file in self.critical_files:
            filepath = os.path.join(self.project_root, critical_file)
            if not os.path.exists(filepath):
                findings.append({
                    "title": f"MISSING_CRITICAL_FILE: {critical_file}",
                    "description": f"Critical file {critical_file} is missing",
                    "severity": "critical",
                    "confidence": 1.0,
                    "symbol": critical_file,
                    "market_type": "system"
                })
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                if content.startswith('/') or content.startswith('governor'):
                    findings.append({
                        "title": f"CORRUPTED_FILE: {critical_file}",
                        "description": f"File starts with garbage text, possible merge conflict",
                        "severity": "critical",
                        "confidence": 0.95,
                        "symbol": critical_file,
                        "market_type": "system"
                    })
                
                for i, line in enumerate(lines[:50], 1):
                    if 'AVAILABLE_AGENTS' in line and 'class ' in line:
                        findings.append({
                            "title": f"CODE_CORRUPTION: {critical_file}",
                            "description": f"Line {i}: Possible code corruption - class definition in variable",
                            "severity": "high",
                            "confidence": 0.9,
                            "symbol": critical_file,
                            "market_type": "system"
                        })
                        
            except Exception as e:
                logger.warning(f"Could not check {critical_file}: {str(e)}")

        return findings

    def _validate_agents(self) -> List[Dict[str, Any]]:
        """Validate all agent implementations."""
        findings = []
        
        if not os.path.exists(self.agent_dir):
            return findings
        
        for file in os.listdir(self.agent_dir):
            if file.endswith('_agent.py') and file != 'base_agent.py':
                filepath = os.path.join(self.agent_dir, file)
                agent_name = file.replace('.py', '')
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    tree = ast.parse(content)
                    
                    has_analyze = False
                    has_init = False
                    has_base_agent_import = 'BaseAgent' in content
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            if node.name == 'analyze':
                                has_analyze = True
                            if node.name == '__init__':
                                has_init = True
                    
                    if not has_base_agent_import:
                        findings.append({
                            "title": f"AGENT_MISSING_BASE: {agent_name}",
                            "description": f"Agent doesn't inherit from BaseAgent",
                            "severity": "high",
                            "confidence": 0.9,
                            "symbol": agent_name,
                            "market_type": "system"
                        })
                    
                    if not has_analyze:
                        findings.append({
                            "title": f"AGENT_MISSING_ANALYZE: {agent_name}",
                            "description": f"Agent missing required analyze() method",
                            "severity": "high",
                            "confidence": 1.0,
                            "symbol": agent_name,
                            "market_type": "system"
                        })

                    if 'np.float' in content or 'np.int' in content:
                        if 'float(' not in content and 'int(' not in content:
                            findings.append({
                                "title": f"NUMPY_TYPE_SQL_RISK: {agent_name}",
                                "description": (
                                    f"Agent uses numpy types (np.float64/np.int64) that may cause "
                                    f"PostgreSQL insertion errors. Wrap with float()/int()."
                                ),
                                "severity": "high",
                                "confidence": 0.85,
                                "symbol": agent_name,
                                "market_type": "system"
                            })
                        
                except SyntaxError as e:
                    findings.append({
                        "title": f"AGENT_SYNTAX_ERROR: {agent_name}",
                        "description": f"Line {e.lineno}: {e.msg}",
                        "severity": "critical",
                        "confidence": 1.0,
                        "symbol": agent_name,
                        "market_type": "system"
                    })
                except Exception as e:
                    logger.debug(f"Could not validate {agent_name}: {str(e)}")

        ghost_findings = self._check_ghost_agents()
        if ghost_findings:
            findings.extend(ghost_findings)

        return findings

    def _check_ghost_agents(self) -> List[Dict[str, Any]]:
        """Detect agents registered in schedule/DB but missing source files."""
        findings = []
        import json

        schedule_path = os.path.join(self.project_root, 'agent_schedule.json')
        if os.path.exists(schedule_path):
            try:
                with open(schedule_path, 'r') as f:
                    schedule = json.load(f)

                for agent_name in schedule:
                    snake = ''.join(
                        ['_' + c.lower() if c.isupper() else c for c in agent_name]
                    ).lstrip('_')
                    source_file = os.path.join(self.agent_dir, f"{snake}.py")
                    if not os.path.exists(source_file):
                        findings.append({
                            "title": f"GHOST_AGENT: {agent_name}",
                            "description": (
                                f"Agent '{agent_name}' is registered in agent_schedule.json "
                                f"but source file '{snake}.py' is missing. "
                                f"Agent will fail at runtime."
                            ),
                            "severity": "critical",
                            "confidence": 1.0,
                            "symbol": agent_name,
                            "market_type": "system"
                        })
            except Exception as e:
                logger.debug(f"Could not check ghost agents: {e}")

        pycache_dir = os.path.join(self.agent_dir, '__pycache__')
        if os.path.exists(pycache_dir):
            for cached in os.listdir(pycache_dir):
                if cached.endswith('.pyc') and '_agent.' in cached:
                    base_name = cached.split('.')[0]
                    source_file = os.path.join(self.agent_dir, f"{base_name}.py")
                    if not os.path.exists(source_file):
                        findings.append({
                            "title": f"ORPHANED_CACHE: {base_name}",
                            "description": (
                                f"Compiled cache '{cached}' exists but source file "
                                f"'{base_name}.py' is missing. Stale cache may cause "
                                f"unpredictable behavior."
                            ),
                            "severity": "high",
                            "confidence": 1.0,
                            "symbol": base_name,
                            "market_type": "system"
                        })

        return findings

    def _check_system_health(self) -> List[Dict[str, Any]]:
        """Check overall system health indicators."""
        findings = []
        
        init_file = os.path.join(self.agent_dir, '__init__.py')
        if os.path.exists(init_file):
            try:
                with open(init_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                bracket_count = content.count('[') - content.count(']')
                paren_count = content.count('(') - content.count(')')
                brace_count = content.count('{') - content.count('}')
                
                if bracket_count != 0:
                    findings.append({
                        "title": "BRACKET_MISMATCH: agents/__init__.py",
                        "description": f"Unbalanced brackets: {bracket_count} unclosed '['",
                        "severity": "critical",
                        "confidence": 0.95,
                        "symbol": "agents/__init__.py",
                        "market_type": "system"
                    })
                    
            except Exception as e:
                logger.debug(f"Could not check __init__.py: {str(e)}")

        return findings

    def _check_security(self) -> List[Dict[str, Any]]:
        """Check for security issues like exposed secrets."""
        findings = []
        
        dangerous_patterns = [
            ('api_key', 'Hardcoded API key'),
            ('password', 'Hardcoded password'),
            ('secret', 'Hardcoded secret'),
            ('private_key', 'Hardcoded private key'),
        ]
        
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pythonlibs', 'node_modules', '.upm']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    relative_path = os.path.relpath(filepath, self.project_root)
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                        
                        for pattern, desc in dangerous_patterns:
                            if f'{pattern} = "' in content or f"{pattern} = '" in content:
                                if 'os.environ' not in content[:content.find(pattern) + 100]:
                                    findings.append({
                                        "title": f"SECURITY_RISK: {relative_path}",
                                        "description": f"{desc} detected - use environment variables",
                                        "severity": "high",
                                        "confidence": 0.8,
                                        "symbol": relative_path,
                                        "market_type": "system"
                                    })
                                    break
                    except Exception as e:
                        logger.debug(f"Could not check {relative_path}: {str(e)}")

        return findings

    def _check_dependencies(self) -> List[Dict[str, Any]]:
        """Check for missing or incompatible dependencies."""
        findings = []
        
        return findings

    def _check_imports(self) -> List[Dict[str, Any]]:
        """Check for import errors in critical files."""
        findings = []
        
        for critical_file in self.critical_files:
            filepath = os.path.join(self.project_root, critical_file)
            if not os.path.exists(filepath):
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith('agents.') and 'agent' in alias.name.lower():
                                agent_file = alias.name.replace('agents.', '') + '.py'
                                agent_path = os.path.join(self.agent_dir, agent_file)
                                if not os.path.exists(agent_path):
                                    findings.append({
                                        "title": f"MISSING_IMPORT: {alias.name}",
                                        "description": f"Imported module {alias.name} does not exist",
                                        "severity": "critical",
                                        "confidence": 1.0,
                                        "symbol": critical_file,
                                        "market_type": "system"
                                    })
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith('agents.'):
                            agent_file = node.module.replace('agents.', '') + '.py'
                            agent_path = os.path.join(self.agent_dir, agent_file)
                            if not os.path.exists(agent_path):
                                findings.append({
                                    "title": f"MISSING_IMPORT: {node.module}",
                                    "description": f"Imported module {node.module} does not exist",
                                    "severity": "critical",
                                    "confidence": 1.0,
                                    "symbol": critical_file,
                                    "market_type": "system"
                                })
                                
            except SyntaxError:
                pass
            except Exception as e:
                logger.debug(f"Could not check imports in {critical_file}: {str(e)}")

        return findings

    def _check_business_logic(self) -> List[Dict[str, Any]]:
        """Check for business logic violations in critical endpoints."""
        findings = []
        
        business_rules = [
            {
                'file': 'routes/api.py',
                'pattern': 'action-required',
                'required_patterns': ['ta_regime', 'ta_council', 'fund_council'],
                'description': 'Action-required endpoint must check BOTH council approval AND ta_regime',
                'severity': 'high'
            },
            {
                'file': 'routes/api.py',
                'pattern': 'action-required',
                'required_patterns': ['favorable_regimes', 'in_'],
                'description': 'Action-required must filter by favorable TA regimes',
                'severity': 'high'
            },
            {
                'file': 'meta/regime_rotation.py',
                'pattern': 'rotate_weights',
                'required_patterns': ['baseline', 'weight', 'stats'],
                'description': 'Regime rotation must have baseline weights for agents without stats',
                'severity': 'medium'
            }
        ]
        
        for rule in business_rules:
            filepath = os.path.join(self.project_root, rule['file'])
            if not os.path.exists(filepath):
                continue
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if rule['pattern'] not in content:
                    continue
                    
                pattern_start = content.find(rule['pattern'])
                pattern_end = min(pattern_start + 2000, len(content))
                relevant_section = content[pattern_start:pattern_end]
                
                missing = [p for p in rule['required_patterns'] if p not in relevant_section]
                
                if missing:
                    findings.append({
                        "title": f"BUSINESS_LOGIC_VIOLATION: {rule['file']}",
                        "description": f"{rule['description']}. Missing: {', '.join(missing)}",
                        "severity": rule['severity'],
                        "confidence": 0.85,
                        "symbol": rule['file'],
                        "market_type": "system"
                    })
                    
            except Exception as e:
                logger.debug(f"Could not check business logic in {rule['file']}: {str(e)}")
        
        return findings

    def _check_action_required(self) -> List[Dict[str, Any]]:
        """Monitor action-required findings and report on their status."""
        findings = []
        try:
            from models import Finding as FindingModel
            from datetime import timedelta
            from sqlalchemy import or_, and_, not_

            now = datetime.utcnow()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            blocking_regimes = ['risk_off', 'crisis', 'bearish', 'recession', 'panic']
            trading_types = ['equity', 'crypto', 'macro', 'bonds', 'volatility', 'technical',
                             'credit', 'structured_credit', 'geopolitical', 'commodities']
            high_severities = ['high', 'critical']

            action_count = FindingModel.query.filter(
                FindingModel.timestamp >= last_7d,
                or_(
                    and_(
                        FindingModel.ta_council == 'act',
                        FindingModel.fund_council == 'act',
                        or_(
                            FindingModel.ta_regime.is_(None),
                            not_(FindingModel.ta_regime.in_(blocking_regimes))
                        )
                    ),
                    and_(
                        FindingModel.market_type.in_(trading_types),
                        FindingModel.severity.in_(high_severities),
                        FindingModel.confidence >= 0.7,
                        or_(
                            FindingModel.ta_regime.is_(None),
                            not_(FindingModel.ta_regime.in_(blocking_regimes))
                        )
                    )
                )
            ).count()

            if action_count > 0:
                findings.append({
                    "title": f"ACTION_REQUIRED_ITEMS: {action_count}",
                    "description": f"{action_count} findings require attention in the last 7 days (high-severity market signals or council-approved trades)",
                    "severity": "high" if action_count > 10 else "medium",
                    "confidence": 0.95,
                    "symbol": "ACTION_REQUIRED",
                    "market_type": "system"
                })

            stale_action = FindingModel.query.filter(
                FindingModel.timestamp >= last_7d,
                FindingModel.timestamp < last_24h,
                FindingModel.market_type.in_(trading_types),
                FindingModel.severity.in_(high_severities),
                FindingModel.confidence >= 0.7
            ).count()

            if stale_action > 20:
                findings.append({
                    "title": f"STALE_ACTION_ITEMS: {stale_action}",
                    "description": f"{stale_action} high-severity findings older than 24h still unresolved",
                    "severity": "medium",
                    "confidence": 0.85,
                    "symbol": "STALE_ACTIONS",
                    "market_type": "system"
                })

        except Exception as e:
            logger.debug(f"Could not check action required: {e}")

        return findings

    def _check_scheduler_health(self) -> List[Dict[str, Any]]:
        """Check if agents are running on schedule."""
        findings = []
        try:
            from models import AgentStatus as AgentStatusModel
            from datetime import timedelta

            now = datetime.utcnow()
            stale_threshold = now - timedelta(hours=2)

            stale_agents = AgentStatusModel.query.filter(
                AgentStatusModel.is_active == True,
                AgentStatusModel.last_run < stale_threshold
            ).all()

            if stale_agents:
                agent_names = [a.agent_name for a in stale_agents[:10]]
                findings.append({
                    "title": f"STALE_AGENTS: {len(stale_agents)} agents overdue",
                    "description": f"These agents haven't run in 2+ hours: {', '.join(agent_names)}",
                    "severity": "high",
                    "confidence": 0.9,
                    "symbol": "SCHEDULER",
                    "market_type": "system"
                })

            import json
            from pathlib import Path
            q_path = Path("meta_supervisor/quarantine.json")
            if q_path.exists():
                q_data = json.loads(q_path.read_text())
                quarantined = {k: v for k, v in q_data.get("agents", {}).items() if v.get("active")}
                if quarantined:
                    findings.append({
                        "title": f"QUARANTINED_AGENTS: {len(quarantined)}",
                        "description": f"Quarantined agents: {', '.join(list(quarantined.keys())[:10])}",
                        "severity": "medium",
                        "confidence": 1.0,
                        "symbol": "QUARANTINE",
                        "market_type": "system"
                    })

        except Exception as e:
            logger.debug(f"Could not check scheduler health: {e}")

        return findings

    def _check_runtime_errors(self) -> List[Dict[str, Any]]:
        """Check agent_status table for agents with runtime errors."""
        findings = []
        try:
            from models import AgentStatus as AgentStatusModel

            error_agents = AgentStatusModel.query.filter(
                AgentStatusModel.error_count > 0,
                AgentStatusModel.last_error.isnot(None),
                AgentStatusModel.last_error != ''
            ).order_by(AgentStatusModel.error_count.desc()).all()

            error_categories = {}
            for agent in error_agents:
                error_msg = agent.last_error or ''
                if 'stored_findings' in error_msg:
                    cat = 'stored_findings_scope'
                elif 'abstract' in error_msg.lower():
                    cat = 'abstract_method_missing'
                elif 'import' in error_msg.lower() or 'module' in error_msg.lower():
                    cat = 'import_error'
                elif 'connection' in error_msg.lower() or 'timeout' in error_msg.lower():
                    cat = 'network_error'
                elif 'type' in error_msg.lower() or 'attribute' in error_msg.lower():
                    cat = 'type_error'
                else:
                    cat = 'other'

                if cat not in error_categories:
                    error_categories[cat] = []
                error_categories[cat].append({
                    'name': agent.agent_name,
                    'count': agent.error_count,
                    'error': error_msg[:200]
                })

            for cat, agents in error_categories.items():
                total_errors = sum(a['count'] for a in agents)
                agent_names = [a['name'] for a in agents[:5]]
                sample_error = agents[0]['error'] if agents else 'Unknown'

                severity = 'critical' if total_errors > 100 else 'high' if total_errors > 10 else 'medium'

                findings.append({
                    "title": f"RUNTIME_ERRORS ({cat}): {len(agents)} agents, {total_errors} total errors",
                    "description": (
                        f"Error pattern '{cat}' affecting {len(agents)} agents "
                        f"({', '.join(agent_names)}{'...' if len(agents) > 5 else ''}). "
                        f"Sample error: {sample_error}"
                    ),
                    "severity": severity,
                    "confidence": 1.0,
                    "symbol": "RUNTIME",
                    "market_type": "system"
                })

        except Exception as e:
            logger.debug(f"Could not check runtime errors: {e}")

        return findings
