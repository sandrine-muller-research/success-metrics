from datetime import datetime
from github import Github
import os
# import gspread
import init
from statistics import mean, median
from typing import Dict, Any, List
# import spacy
from collections import Counter
# import pandas as pd
# import numpy as np
import csv
import time

ANALYTICS_TYPES = ['github_repo_stats','github_issues_stats'] #,'github_issues_sentiment']

def save_full_issues_tsv(issues, org_name: str, repo_name: str, filename='github_issues_full.tsv'):
    all_rows = []
    
    for i, issue in enumerate(issues, 1):
        print(f"Processing issue {i}/{len(issues)}: #{issue.number}")
        
        # Issue row
        comments = list(issue.get_comments())
        body_text = issue.body or ''
        body_preview = body_text[:500] + '...' if len(body_text) > 500 else body_text
        
        all_rows.append({
            'type': 'ISSUE',
            'number': issue.number,
            'title': issue.title[:200],
            'state': issue.state,
            'created': issue.created_at.isoformat(),
            'updated': issue.updated_at.isoformat(),
            'author': issue.user.login,
            'assignee': issue.assignee.login if issue.assignee else '',
            'labels': ', '.join(label.name for label in issue.labels),
            'body_preview': body_preview.replace('\n', ' ').replace('\t', ' '),
            'total_comments': len(comments),
            'url': issue.html_url
        })
        
        # Comment rows (one per comment)
        for comment in comments:
            comment_body = comment.body or ''
            comment_preview = comment_body[:500] + '...' if len(comment_body) > 500 else comment_body
            all_rows.append({
                'type': 'COMMENT',
                'number': issue.number,
                'title': issue.title[:100],
                'state': '',
                'created': comment.created_at.isoformat(),
                'updated': comment.updated_at.isoformat(),
                'author': comment.user.login,
                'assignee': '',
                'labels': '',
                'body_preview': comment_preview.replace('\n', ' ').replace('\t', ' '),
                'total_comments': '',
                'url': comment.html_url
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
        token (str): GitHub PAT with 'repo' and 'read:org' scope
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
    
    for repo in org.get_repos(type='public'):  # Only public repos
        created = repo.created_at
        if created <= dt:  
            total_forks += repo.forks_count
            total_stars += repo.stargazers_count
            print(f"{repo.name}: {repo.forks_count} forks, {repo.stargazers_count} stars")
    
    return {'total_forks': total_forks, 'api_call_date': date_str}
      
def get_all_repo_issues(org_name: str, repo_name: str, token: str) -> List:
    """
    Collects ALL issues from a GitHub repository using PyGithub.
    
    Args:
        org_name (str): GitHub organization name
        repo_name (str): Repository name
        token (str): GitHub PAT with 'repo' scope
        
    Returns:
        List of PyGithub Issue objects
    """
    g = Github(token)
    repo = g.get_repo(f"{org_name}/{repo_name}")
    issues = repo.get_issues(state='all')
    return list(issues)

def analyze_repo_issues(org_name: str, repo_name: str, token: str, date_str: str) -> Dict[str, Any]:
    """Analyzes repo issues up to given date."""
    all_issues = get_all_repo_issues(org_name, repo_name, token)
    
    cutoff_date = datetime.strptime(date_str, '%Y-%m-%d')
    filtered_issues = [
        issue for issue in all_issues 
        if issue.created_at.date() <= cutoff_date.date()
    ]
    
    total_issues = len(filtered_issues)
    closed_issues = sum(1 for issue in filtered_issues if issue.state == 'closed')
    
    close_times = []
    for issue in filtered_issues:
        if issue.state == 'closed' and issue.closed_at:
            created = issue.created_at
            closed = issue.closed_at
            close_times.append((closed - created).days)
    
    avg_time_to_close = mean(close_times) if close_times else 0
    median_time_to_close = median(close_times) if close_times else 0
    
    return {
        'total_issues': total_issues,
        'closed_issues': closed_issues,
        'avg_issue_close_time_days': round(avg_time_to_close, 2),
        'median_issue_close_time_days': median_time_to_close,
        'all_issues_fetched': len(all_issues)
    }



# def analyze_issues_sentiment_spacy(all_issues, text_fields=['title', 'api_call_date'], model_name='en_core_web_sm'):
#     """
#     Perform sentiment analysis on GitHub issues using spaCy + pattern.en
    
#     Args:
#         all_issues: List of Issue objects from get_all_repo_issues()
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
#             val = getattr(issue, field, '')
#             if val:
#                 texts.append(val)
        
#         full_text = ' '.join(texts)
#         if full_text.strip():
#             doc = nlp(full_text)
            
#             # Simple rule-based sentiment using pattern.en (bundled with spaCy)
#             polarity = doc._.polarity  # Requires pattern.api or custom rules
#             subjectivity = doc._.subjectivity
            
#             # Fallback: count positive/negative sentiment words
#             if not hasattr(doc, '_'):
#                 polarity, subjectivity = calculate_sentiment_fallback(doc)
            
#             sentiments.append({
#                 'issue_number': issue.number,
#                 'title': issue.title,
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
    total_words = len([t for t: doc if not t.is_stop and not t.is_punct])
    
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
        pending_dates = init.get_pending_date_columns(sheet, config['sheets'][analytic_type]['date_row'], config='append_date_row' if 'append_date_row' in config['sheets'][analytic_type] else config['sheets'][analytic_type]['data_row'])
        # Note: I kept the logic as close to original as possible, but corrected the variable name check for safety.
        
        if pending_dates != []:
            print("Updating GitHub repos analytics:", pending_dates)
            for date_str, col_idx in pending_dates:
                if analytic_type == 'github_repo_stats':
                    analytics = analyze_org_repos("NCATSTranslator", TOKEN, date_str)
                elif analytic_type == 'github_issues_stats':
                    analytics = analyze_repo_issues("NCATSTranslator", "Feedback", TOKEN, date_str)
                
                # init.write_stats_for_columns(sheet, config['round_names', ...], ...)
    

            print(f"✅ SUCCESS! {analytic_type} analytics recorded.")
            
        else:
            print(f"No pending dates for {analytic_type}, skipping.")

if __name__ == "__main__":
    # main()
    TOKEN = os.getenv('GITHUB_REPO_TOKEN')
    all_issues = get_all_repo_issues("NCATTRanslator", "Feedback", TOKEN)
    save_full_issues_tsv(all_issues, org_name="NCATSTranslator", repo_name="Feedback")
    'bob'
    # results = analyze_issues_sentiment_spacy(all_issues)
    # print(f"Avg polarity: {results['avg_polarity']:.3f}")
    # print(results['sentiment_distribution'])
