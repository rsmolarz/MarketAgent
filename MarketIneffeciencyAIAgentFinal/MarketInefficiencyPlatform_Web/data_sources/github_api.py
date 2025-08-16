
import requests

def get_github_stars(repo_full_name):
    """
    Fetch the star count of a GitHub repo like 'openai/gpt-4'
    """
    url = f"https://api.github.com/repos/{repo_full_name}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json().get("stargazers_count", 0)
        else:
            print(f"[GitHubAPI] Failed for {repo_full_name}: {response.status_code}")
            return None
    except Exception as e:
        print(f"[GitHubAPI] Error: {e}")
        return None
