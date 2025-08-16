"""
Alternative Data Signal Agent

Monitors alternative data sources for market signals and anomalies.
"""

from typing import List, Dict, Any
from .base_agent import BaseAgent
from data_sources.github_client import GitHubClient

class AltDataSignalAgent(BaseAgent):
    """
    Monitors alternative data sources for market signals
    """
    
    def __init__(self):
        super().__init__()
        self.github_client = GitHubClient()
        
        # Repositories to monitor for technology trends
        self.tech_repos = [
            'pytorch/pytorch',
            'tensorflow/tensorflow', 
            'microsoft/vscode',
            'facebook/react',
            'bitcoin/bitcoin',
            'ethereum/ethereum'
        ]
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Analyze alternative data sources for signals
        """
        findings = []
        
        if not self.validate_config(['GITHUB_TOKEN']):
            self.logger.warning("GitHub token not configured")
            return findings
        
        # Analyze GitHub trends
        findings.extend(self._analyze_github_trends())
        
        return findings
    
    def _analyze_github_trends(self) -> List[Dict[str, Any]]:
        """Analyze GitHub repository trends"""
        findings = []
        
        for repo in self.tech_repos:
            try:
                activity = self.github_client.get_repo_activity(repo)
                if not activity:
                    continue
                
                # Analyze unusual activity spikes
                findings.extend(self._check_activity_spikes(repo, activity))
                
            except Exception as e:
                self.logger.error(f"Error analyzing repo {repo}: {e}")
                
        return findings
    
    def _check_activity_spikes(self, repo: str, activity: Dict) -> List[Dict[str, Any]]:
        """Check for unusual activity spikes in repositories"""
        findings = []
        
        try:
            stars = activity.get('stars', 0)
            forks = activity.get('forks', 0)
            issues = activity.get('issues', 0)
            commits = activity.get('commits', 0)
            
            # Define thresholds based on repo type
            if 'bitcoin' in repo.lower() or 'ethereum' in repo.lower():
                # Crypto repos - activity could signal market interest
                if commits > 50 or issues > 20:
                    findings.append(self.create_finding(
                        title=f"High Development Activity in {repo}",
                        description=f"Unusual activity detected: {commits} commits, "
                                   f"{issues} issues. This could signal upcoming "
                                   f"developments affecting crypto markets.",
                        severity='medium',
                        confidence=0.6,
                        symbol='CRYPTO_DEV',
                        market_type='crypto',
                        metadata={
                            'repository': repo,
                            'commits': commits,
                            'issues': issues,
                            'stars': stars,
                            'forks': forks
                        }
                    ))
            
            elif any(tech in repo.lower() for tech in ['pytorch', 'tensorflow']):
                # AI/ML repos - could signal AI sector trends
                if stars > 1000 or forks > 500:
                    findings.append(self.create_finding(
                        title=f"AI/ML Repository Gaining Traction: {repo}",
                        description=f"Significant community interest: {stars} new stars, "
                                   f"{forks} forks. This could indicate growing AI/ML "
                                   f"sector momentum affecting tech stocks.",
                        severity='low',
                        confidence=0.5,
                        symbol='AI_TECH',
                        market_type='equity',
                        metadata={
                            'repository': repo,
                            'stars': stars,
                            'forks': forks,
                            'sector': 'AI/ML'
                        }
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error checking activity spikes for {repo}: {e}")
            
        return findings
