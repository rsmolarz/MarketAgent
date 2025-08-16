"""
GitHub API Client

Provides access to GitHub repository data for tracking development
activity and trends in technology projects.
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class GitHubClient:
    """
    Client for GitHub API data
    """
    
    def __init__(self):
        self.token = Config.GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        
        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json'
            })
    
    def get_repo_info(self, repo: str) -> Optional[Dict]:
        """
        Get basic repository information
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            Repository data or None
        """
        try:
            url = f"{self.base_url}/repos/{repo}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting repo info for {repo}: {e}")
            
        return None
    
    def get_repo_activity(self, repo: str, days: int = 7) -> Optional[Dict]:
        """
        Get repository activity metrics
        
        Args:
            repo: Repository in format 'owner/repo'
            days: Number of days to look back
            
        Returns:
            Activity data or None
        """
        try:
            # Get basic repo info
            repo_info = self.get_repo_info(repo)
            if not repo_info:
                return None
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            activity = {
                'stars': repo_info.get('stargazers_count', 0),
                'forks': repo_info.get('forks_count', 0),
                'open_issues': repo_info.get('open_issues_count', 0),
                'commits': 0,
                'issues': 0,
                'pull_requests': 0
            }
            
            # Get recent commits
            commits = self.get_recent_commits(repo, since=start_date.isoformat())
            if commits:
                activity['commits'] = len(commits)
            
            # Get recent issues
            issues = self.get_recent_issues(repo, since=start_date.isoformat())
            if issues:
                activity['issues'] = len(issues)
            
            # Get recent pull requests
            prs = self.get_recent_pull_requests(repo, since=start_date.isoformat())
            if prs:
                activity['pull_requests'] = len(prs)
            
            return activity
            
        except Exception as e:
            logger.error(f"Error getting repo activity for {repo}: {e}")
            
        return None
    
    def get_recent_commits(self, repo: str, since: str = None, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get recent commits for a repository
        
        Args:
            repo: Repository in format 'owner/repo'
            since: ISO 8601 timestamp
            limit: Maximum number of commits
            
        Returns:
            List of commit data or None
        """
        try:
            url = f"{self.base_url}/repos/{repo}/commits"
            params = {'per_page': min(limit, 100)}
            
            if since:
                params['since'] = since
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting commits for {repo}: {e}")
            
        return None
    
    def get_recent_issues(self, repo: str, since: str = None, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get recent issues for a repository
        
        Args:
            repo: Repository in format 'owner/repo'  
            since: ISO 8601 timestamp
            limit: Maximum number of issues
            
        Returns:
            List of issue data or None
        """
        try:
            url = f"{self.base_url}/repos/{repo}/issues"
            params = {
                'state': 'all',
                'per_page': min(limit, 100),
                'sort': 'created',
                'direction': 'desc'
            }
            
            if since:
                params['since'] = since
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                # Filter out pull requests (GitHub includes PRs in issues endpoint)
                issues = [item for item in response.json() if 'pull_request' not in item]
                return issues
                
        except Exception as e:
            logger.error(f"Error getting issues for {repo}: {e}")
            
        return None
    
    def get_recent_pull_requests(self, repo: str, since: str = None, limit: int = 100) -> Optional[List[Dict]]:
        """
        Get recent pull requests for a repository
        
        Args:
            repo: Repository in format 'owner/repo'
            since: ISO 8601 timestamp
            limit: Maximum number of PRs
            
        Returns:
            List of PR data or None
        """
        try:
            url = f"{self.base_url}/repos/{repo}/pulls"
            params = {
                'state': 'all',
                'per_page': min(limit, 100),
                'sort': 'created',
                'direction': 'desc'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                prs = response.json()
                
                # Filter by date if since parameter provided
                if since:
                    since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
                    filtered_prs = []
                    
                    for pr in prs:
                        created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                        if created_at >= since_date:
                            filtered_prs.append(pr)
                    
                    return filtered_prs
                
                return prs
                
        except Exception as e:
            logger.error(f"Error getting pull requests for {repo}: {e}")
            
        return None
    
    def search_repositories(self, query: str, sort: str = 'stars', limit: int = 10) -> Optional[List[Dict]]:
        """
        Search for repositories
        
        Args:
            query: Search query
            sort: Sort criteria (stars, forks, updated)
            limit: Maximum number of results
            
        Returns:
            List of repository data or None
        """
        try:
            url = f"{self.base_url}/search/repositories"
            params = {
                'q': query,
                'sort': sort,
                'order': 'desc',
                'per_page': min(limit, 100)
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
                
        except Exception as e:
            logger.error(f"Error searching repositories with query '{query}': {e}")
            
        return None
    
    def get_trending_repos(self, language: str = None, since: str = 'daily') -> Optional[List[Dict]]:
        """
        Get trending repositories (simplified implementation)
        
        Args:
            language: Programming language filter
            since: Time period (daily, weekly, monthly)
            
        Returns:
            List of trending repositories or None
        """
        try:
            # Use search to find recently starred repos as proxy for trending
            if since == 'daily':
                date_filter = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
            elif since == 'weekly':
                date_filter = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
            else:  # monthly
                date_filter = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            query = f"created:>{date_filter}"
            if language:
                query += f" language:{language}"
            
            return self.search_repositories(query, sort='stars', limit=20)
            
        except Exception as e:
            logger.error(f"Error getting trending repos: {e}")
            
        return None
