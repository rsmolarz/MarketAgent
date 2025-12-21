// GitHub Push Script - Uses Replit's GitHub integration
import { Octokit } from '@octokit/rest';

let connectionSettings = null;

async function getAccessToken() {
  if (connectionSettings && connectionSettings.settings.expires_at && new Date(connectionSettings.settings.expires_at).getTime() > Date.now()) {
    return connectionSettings.settings.access_token;
  }
  
  const hostname = process.env.REPLIT_CONNECTORS_HOSTNAME;
  const xReplitToken = process.env.REPL_IDENTITY 
    ? 'repl ' + process.env.REPL_IDENTITY 
    : process.env.WEB_REPL_RENEWAL 
    ? 'depl ' + process.env.WEB_REPL_RENEWAL 
    : null;

  if (!xReplitToken) {
    throw new Error('X_REPLIT_TOKEN not found');
  }

  connectionSettings = await fetch(
    'https://' + hostname + '/api/v2/connection?include_secrets=true&connector_names=github',
    {
      headers: {
        'Accept': 'application/json',
        'X_REPLIT_TOKEN': xReplitToken
      }
    }
  ).then(res => res.json()).then(data => data.items?.[0]);

  const accessToken = connectionSettings?.settings?.access_token || connectionSettings?.settings?.oauth?.credentials?.access_token;

  if (!connectionSettings || !accessToken) {
    throw new Error('GitHub not connected');
  }
  return accessToken;
}

async function pushToGitHub() {
  try {
    console.log('Getting GitHub access token...');
    const token = await getAccessToken();
    
    const octokit = new Octokit({ auth: token });
    const { data: user } = await octokit.users.getAuthenticated();
    console.log(`Authenticated as: ${user.login}`);
    
    // Get repo info
    const owner = 'rsmolarz';
    const repo = 'MarketAgent';
    
    console.log(`\nRepository: https://github.com/${owner}/${repo}`);
    console.log('\nTo push your code to GitHub, run these commands in the Shell:');
    console.log('-----------------------------------------------------------');
    console.log(`export GH_TOKEN="${token.substring(0, 10)}..."`);
    console.log(`git remote set-url origin https://oauth2:$GH_TOKEN@github.com/${owner}/${repo}.git`);
    console.log('git add -A');
    console.log('git commit -m "Add agent documentation and time window feature"');
    console.log('git push origin main');
    console.log('-----------------------------------------------------------');
    
    // Try to get the latest commit to verify connection
    try {
      const { data: repoData } = await octokit.repos.get({ owner, repo });
      console.log(`\nRepository verified: ${repoData.full_name}`);
      console.log(`Default branch: ${repoData.default_branch}`);
      console.log(`Last updated: ${repoData.updated_at}`);
    } catch (e) {
      console.log('\nCould not verify repository access:', e.message);
    }
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

pushToGitHub();
