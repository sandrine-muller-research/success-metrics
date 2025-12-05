import requests
from datetime import datetime
from github import Github
import os
import gspread
from google.oauth2.service_account import Credentials
import init
# from pathlib import Path
# import json




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


def get_pending_date_columns(sheet, date_row, data_row):
    """
    Reads date headers and returns list of (date_str, col_idx) where:
    - date <= today
    - data cell in data_row is empty
    
    Args:
        sheet: gspread worksheet
        date_row: int, row number with dates
        data_row: int, row number with data to check
    
    Returns:
        List of tuples: [(date_str, col_idx), ...]
    """
    pending_columns = []
    today = datetime.now().date()
    
    date_headers = sheet.row_values(date_row)
    
    for col_idx, date_str in enumerate(date_headers, 1):
        try:
            header_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            continue
        
        if header_date <= today:
            data_cell = gspread.utils.rowcol_to_a1(data_row, col_idx)
            data_value = sheet.acell(data_cell).value
            
            if data_value is None or data_value.strip() == "":
                pending_columns.append((date_str, col_idx))
    
    return pending_columns


def write_github_stats_for_columns(sheet, results, data_row, pending_columns):
    """
    Writes forks and stars into specified columns on data_row and data_row+1.
    
    Args:
        sheet: gspread worksheet
        results: dict with 'total_forks' and 'total_stars'
        data_row: int, row number for forks writing
        pending_columns: list of (date_str, col_idx) to write to
    """
    for date_str, col_idx in pending_columns:
        forks_cell = gspread.utils.rowcol_to_a1(data_row, col_idx)
        stars_cell = gspread.utils.rowcol_to_a1(data_row + 1, col_idx)
        
        sheet.update_acell(forks_cell, results['total_forks'])
        sheet.update_acell(stars_cell, results['total_stars'])
        
        print(f"✅ Wrote Forks to {forks_cell}, Stars to {stars_cell} for date {date_str}")


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
    TOKEN = os.getenv('GITHUB_PUBLIC_REPO_TOKEN')
    
    # ------------------------------
    # Connect to Google Sheets:
    # ------------------------------
    client = init.get_client()
    spreadsheet = client.open_by_key(config['sheets']['github_stats']['sheet_id'])
    community_sheet = spreadsheet.worksheet("community")
    
    # Get dates:
    pending_dates = get_pending_date_columns(community_sheet, config['sheets']['github_stats']['date_row'], config['sheets']['github_stats']['data_row'])
    if not  pending_dates:
        print("✅ No pending dates - all columns filled!")
    else:
        print(f"📊 Found {len(pending_dates)} pending date columns: {pending_dates}")
        
    # ------------------------------
    # Repos analytics:
    # ------------------------------
    for date_str, col_idx in pending_dates:
        git_repos_analytics = analyze_org_repos("NCATSTranslator", TOKEN, date_str)
        print(f"Total forks: {git_repos_analytics['total_forks']}, Total stars: {git_repos_analytics['total_stars']}")
        write_github_stats_for_columns(community_sheet, git_repos_analytics, config['sheets']['github_stats']['data_row'], [(date_str, col_idx)])
    
    
    print("✅ SUCCESS! Repository analytics recorded.") 

if __name__ == "__main__":
    main()