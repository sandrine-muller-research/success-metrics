# import requests
from datetime import datetime
from github import Github
import os
# import gspread
from google.oauth2.service_account import Credentials
import init
from statistics import mean, median
from typing import Dict, Any, List
import requests
# import spacy
from collections import Counter
# import pandas as pd
# import numpy as np
import csv
import time

ANALYTICS_TYPES = ['github_repo_stats','github_issues_stats'] #,'github_issues_sentiment']

def fetch_comments(issue_number, OWNER, REPO, HEADERS=None):
    """Fetch all comments for single issue"""
    comments = []
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/issues/{issue_number}/comments'
    params = {'per_page': 100}
    
    while url:
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code != 200:
            break
        page_comments = resp.json()
        comments.extend(page_comments)
        url = resp.links.get('next', {}).get('url')
        params = {}
        time.sleep(0.1)
    
    return comments

def save_full_issues_tsv(issues, org_name: str, repo_name: str, filename='github_issues_full.tsv'):
    all_rows = []
    
    for i, issue in enumerate(issues, 1):
        print(f"Processing issue {i}/{len(issues)}: #{issue['number']}")
        
        # Issue row
        comments = fetch_comments(issue['number'], org_name, repo_name)
        body_preview = issue['body'][:500] + '...' if len(issue['body'] or '') > 500 else (issue['body'] or '')
        
        all_rows.append({
            'type': 'ISSUE',
            'number': issue['number'],
            'title': issue['title'][:200],
            'state': issue['state'],
            'created': issue['created_at'],
            'updated': issue['updated_at'],
            'author': issue['user']['login'],
            'assignee': issue.get('assignee', {}).get('login', '') if issue.get('assignee') else '',
            'labels': ', '.join(label['name'] for label in issue.get('labels', [])),
            'body_preview': body_preview.replace('\n', ' ').replace('\t', ' '),
            'total_comments': len(comments),
            'url': issue['html_url']
        })
        
        # Comment rows (one per comment)
        for comment in comments:
            body_preview = comment['body'][:500] + '...' if len(comment['body']) > 500 else comment['body']
            all_rows.append({
                'type': 'COMMENT',
                'number': issue['number'],
                'title': issue['title'][:100],
                'state': '',
                'created': comment['created_at'],
                'updated': comment['updated_at'],
                'author': comment['user']['login'],
                'assignee': '',
                'labels': '',
                'body_preview': body_preview.replace('\n', ' ').replace('\t', ' '),
                'total_comments': '',
                'url': comment['html_url']
            })
        time.sleep(0.2)  # Rate limit
    
    # Write TSV
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, delimiter='\t', fieldnames=[
            'type', 'number', 'title', 'state', 'created', 'updated', 
            'author', 'assignee', 'labels', 'body_preview', 'total_comments', 'url'
        ])
        writer.writeheader()
        writer.writerows(all_rows)
    
    print(f"Saved {len(all_rows)} rows to {filename}")

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



# def analyze_issues_sentiment_spacy(all_issues, text_fields=['title', 'body'], model_name='en_core_web_sm'):
#     """
#     Perform sentiment analysis on GitHub issues using spaCy + pattern.en.
    
#     Args:
#         all_issues: List of issue dicts from get_all_repo_issues()
#         text_fields: List of fields to analyze (default: title, body)
#         model_name: spaCy model ('en_core_web_sm' or 'en_core_web_lg')
    
#     Returns:
#         dict with overall stats and per-issue details
#     """
#     try:
#         nlp = spacy.load(model_name)
#     except OSError:
#         raise ValueError(f"spaCy model '{model_name}' not found. Run: python -m spacy download {model_name}")
    
#     sentiments = []
    
#     for issue in all_issues:
#         texts = []
#         for field in text_fields:
#             if issue.get(field):
#                 texts.append(issue[field])
        
#         full_text = ' '.join(texts)
#         if full_text.strip():
#             doc = nlp(full_text)
            
#             # Simple rule-based sentiment using pattern.en (bundled with spaCy)
#             polarity = doc._.polarity  # Requires pattern.en or custom rules
#             subjectivity = doc._.subjectivity
            
#             # Fallback: count positive/negative sentiment words
#             if not hasattr(doc, '_'):
#                 polarity, subjectivity = calculate_sentiment_fallback(doc)
            
#             sentiments.append({
#                 'issue_number': issue['number'],
#                 'title': issue.get('title', ''),
#                 'polarity': polarity,
#                 'subjectivity': subjectivity,
#                 'sentiment_label': classify_sentiment(polarity)
#             })
    
#     # Overall measurements
#     if sentiments:
#         df = pd.DataFrame(sentiments)
#         return {
#             'total_issues_analyzed': len(sentiments),
#             'positive_pct': (df['polarity'] > 0.1).mean() * 100,
#             'negative_pct': (df['polarity'] < -0.1).mean() * 100,
#             'neutral_pct': ((df['polarity'] >= -0.1) & (df['polarity'] <= 0.1)).mean() * 100,
#             'avg_polarity': df['polarity'].mean(),
#             'avg_subjectivity': df['subjectivity'].mean(),
#             'sentiment_distribution': dict(Counter(df['sentiment_label'])),
#             'detailed_results': df
#         }
#     return {'error': 'No text found in issues'}

def calculate_sentiment_fallback(doc):
    """Fallback sentiment scoring using sentiment lexicon."""
    # Simple positive/negative word counts (expand with full lexicon)
    positive_words = {'good', 'great', 'excellent', 'works', 'fixed', 'love', 'perfect'}
    negative_words = {'bad', 'broken', 'error', 'bug', 'hate', 'terrible', 'fails'}
    
    pos_count = sum(1 for token in doc if token.lemma_.lower() in positive_words)
    neg_count = sum(1 for token in doc if token.lemma_.lower() in negative_words)
    
    total_sentiment = pos_count - neg_count
    total_words = len([t for t in doc if not t.is_stop and not t.is_punct])
    
    polarity = total_sentiment / max(total_words, 1)
    subjectivity = 0.5  # Default for fallback
    
    return polarity, subjectivity

def classify_sentiment(polarity):
    """Simple 3-class classification."""
    if polarity > 0.1:
        return 'positive'
    elif polarity < -0.1:
        return 'negative'
    else:
        return 'neutral'



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
                
                # init.write_stats_for_columns(sheet, config['sheets'][analytic_type].get('measure_names', []), [(date_str, col_idx)], analytics, config['sheets'][analytic_type]['data_row'])
    

            print(f"✅ SUCCESS! {analytic_type} analytics recorded.")
            
        else:
            print(f"No pending dates for {analytic_type}, skipping.")

if __name__ == "__main__":
    # main()
    TOKEN = os.getenv('GITHUB_REPO_TOKEN')
    all_issues = get_all_repo_issues("NCATSTranslator", "Feedback", TOKEN)
    save_full_issues_tsv(all_issues, org_name="NCATSTranslator", repo_name="Feedback")
    'bob'
    # results = analyze_issues_sentiment_spacy(all_issues)
    # print(f"Avg polarity: {results['avg_polarity']:.3f}")
    # print(results['sentiment_distribution'])