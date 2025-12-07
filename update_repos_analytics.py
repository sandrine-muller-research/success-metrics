# import requests
from datetime import datetime
from github import Github
import os
import gspread
from google.oauth2.service_account import Credentials
import init
from statistics import mean, median
from typing import Dict, Any, List
import requests

ANALYTICS_TYPES = ['github_repo_stats','github_issues_stats']

def analyze_org_repos(org_name, token, date_str):
    """
    Analyzes public repos in GitHub org: total forks and stars between dates.
    
    Args:
        org_name (str): GitHub organization name
        token (str): GitHub PAT with 'repo' scope
        date_str (str): 'YYYY-MM-DD' date
    
    Returns:
        dict: {'total_forks': int, 'total_stars': int}
    """
    g = Github(token)
    org = g.get_organization(org_name)
    dt = datetime.fromisoformat(date_str + 'T00:00:00Z')
    
    total_forks = 0
    total_stars = 0
    
    print(f"Analyzing {len(list(org.get_repos(type='public')))} public repos in {org_name}...")
    
    for repo in org.get_repos(type='public'):  # Only public repos [web:17][web:20]
        created = repo.created_at
        if created <= dt:  
            total_forks += repo.forks_count
            total_stars += repo.stargazers_count
            print(f"{repo.name}: {repo.forks_count} forks, {repo.stargazers_count} stars")
    
    return {'total_forks': total_forks, 'total_stars': total_stars}
      


def get_all_repo_issues(org_name: str, repo_name: str, token: str) -> List[Dict]:
    """
    Collects ALL issues from a GitHub repository (public/private) with full pagination.
    
    Args:
        org_name (str): GitHub organization name
        repo_name (str): Repository name
        token (str): GitHub PAT with 'repo' scope
        
    Returns:
        List of all issues as dictionaries
    """
    headers = {
        'Authorization': f'token {token}', 
        'Accept': 'application/vnd.github.v3+json'
    }
    url = f'https://api.github.com/repos/{org_name}/{repo_name}/issues'
    all_issues = []
    page = 1
    
    while True:
        params = {'state': 'all', 'per_page': 100, 'page': page}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code != 200:
            print(f"API error on page {page}: {resp.status_code}")
            break
            
        issues_page = resp.json()
        if not issues_page:  # Empty page = end
            break
            
        all_issues.extend(issues_page)
        print(f"Fetched page {page}: {len(issues_page)} issues (total: {len(all_issues)})")
        page += 1
    
    return all_issues

def analyze_repo_issues(org_name: str, repo_name: str, token: str, date_str: str) -> Dict[str, Any]:
    """Analyzes repo issues up to given date."""
    all_issues = get_all_repo_issues(org_name, repo_name, token)
    
    cutoff_date = datetime.strptime(date_str, '%Y-%m-%d')
    filtered_issues = [
        issue for issue in all_issues 
        if datetime.strptime(issue['created_at'][:10], '%Y-%m-%d') <= cutoff_date
    ]
    
    total_issues = len(filtered_issues)
    closed_issues = sum(1 for issue in filtered_issues if issue['state'] == 'closed')
    
    close_times = []
    for issue in filtered_issues:
        if issue['state'] == 'closed' and issue.get('closed_at'):
            created = datetime.strptime(issue['created_at'][:10], '%Y-%m-%d')
            closed = datetime.strptime(issue['closed_at'][:10], '%Y-%m-%d')
            close_times.append((closed - created).days)
    
    avg_time_to_close = mean(close_times) if close_times else 0
    median_time_to_close = median(close_times) if close_times else 0
    
    return {
        'total_issues': total_issues,
        'closed_issues': closed_issues,
        'avg_issue_close_time_days': round(avg_time_to_close, 2),
        'median_issue_close_time_days':median_time_to_close,
        'all_issues_fetched': len(all_issues)
    }

def write_github_stats(client, results, config, input_dates):
    sheet_config = config['sheets']['github_stats']
    spreadsheet = client.open_by_key(sheet_config['sheet_id'])
    sheet = spreadsheet.worksheet(sheet_config['tab_name'])
    
    # Find target cell based on input dates
    target_cell, col_idx = get_target_cell(
        sheet, 
        input_dates, 
        sheet_config['date_row'], 
        sheet_config['data_row']
    )
    
    # Stars go to next row (data_row + 1)
    stars_cell = gspread.utils.rowcol_to_a1(sheet_config['data_row'] + 1, col_idx)
    
    # Write Forks to data_row
    sheet.update_acell(target_cell, results['total_forks'])
    
    # Write Stars to data_row + 1
    sheet.update_acell(stars_cell, results['total_stars'])
    
    print(f"✅ Wrote Forks to {target_cell}, Stars to {stars_cell} (column {col_idx}) for dates {input_dates}")

def main():
    config = init.load_config()
    TOKEN = os.getenv('GITHUB_REPO_TOKEN')

    client = init.get_client()

    # ------------------------------
    # Repos analytics:
    # ------------------------------
    for analytic_type in ANALYTICS_TYPES:
        spreadsheet = client.open_by_key(config['sheets'][analytic_type]['sheet_id'])
        sheet = spreadsheet.worksheet(config['sheets'][analytic_type]['tab_name'])

        # Get dates:
        pending_dates = init.get_pending_date_columns(sheet, config['sheets'][analytic_type]['date_row'], config['sheets'][analytic_type]['data_row'])
        if pending_dates != []:
            print("Updating GitHub repos analytics:", pending_dates)
            for date_str, col_idx in pending_dates:
                if analytic_type == 'github_repo_stats':
                    analytics = analyze_org_repos("NCATSTranslator", TOKEN, date_str)
                elif analytic_type == 'github_issues_stats':
                    analytics = analyze_repo_issues("NCATSTranslator", "Feedback", TOKEN, date_str)
                
                init.write_stats_for_columns(sheet, analytics, config['sheets'][analytic_type]['data_row'], [(date_str, col_idx)],config['sheets'][analytic_type].get('measure_names', []))
    

            print(f"✅ SUCCESS! {analytic_type} analytics recorded.")

if __name__ == "__main__":
    main()