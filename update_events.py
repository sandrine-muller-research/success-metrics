import requests
from datetime import datetime
import json
import os
import time
from collections import defaultdict
import init
from semanticscholar import SemanticScholar

# List of DOIs from your Biomedical Data Translator publications

ANALYTICS_TYPE = 'events_stats'


def get_lower_bound(user_str):
    """
    Extracts the lower bound integer from a string formatted as 'X-Y' or 'Z+'.
    
    Args:
        user_str (str): String representing number of users, e.g., '5-10' or '15+'
    """    
    if user_str is not None:
        if len(user_str) != 0:
            if '-' in user_str:
                return int(user_str.split('-')[0])
            elif '+' in user_str:
                return int(user_str.replace('+', ''))
            else :
                return int(user_str) 
        else:
            return 0   
        
def get_total_events(client,source_sheet_id,date_str):
    """
    Fetch total events and normalized users from Google Sheets.
    
    Returns:
        dates (List[str]): Sorted list of event dates
    """
    
    source_sheet = client.open_by_key(source_sheet_id).worksheet('User engagement beyond A&C')

    dates = []
    teams = []
    normalized_users = []
    for row in source_sheet.get_all_records():
        date = row['Date']
        team = row['Team']
        if date is not None and team is not None:
            dates.append(datetime.strptime(date, '%Y-%m-%d').date())
            teams.append(team)
            normalized_users.append(get_lower_bound(str(row['Number of users engaged normalized'])))


    unique_teams = list(set(teams))

    nb_events = {}
    nb_people_engaged = {}
    for team in unique_teams:
        nb_events[team] = 0
        nb_people_engaged[team] = 0
        for user, t, dt in zip(normalized_users, teams, dates):
            if t == team and user > 1 and dt <= datetime.strptime(date_str, '%Y-%m-%d').date():
                nb_events[team] += 1 
                nb_people_engaged[team] += user

            
    return {"nb_events": nb_events, "nb_people_engaged": nb_people_engaged}


def main():
    config = init.load_config()
    
    # ------------------------------
    # Connect to Google Sheets:
    # ------------------------------
    client = init.get_client()
    spreadsheet = client.open_by_key(config['sheets'][ANALYTICS_TYPE]['sheet_id'])
    sheet = spreadsheet.worksheet(config['sheets'][ANALYTICS_TYPE]['tab_name'])
    
    # Get dates:
    pending_dates = init.get_pending_date_columns(sheet, config['sheets'][ANALYTICS_TYPE]['date_row'], config['sheets'][ANALYTICS_TYPE]['data_row'])
        
    # ------------------------------
    # Events analytics:
    # ------------------------------
    
    for date_str, col_idx in pending_dates:
        total_events = get_total_events(client,'1eKP8eeJSZiYc3b2Jp71bvTSI8vlMFJ3V-Q0kjATqr-o', date_str)
        if len(total_events['nb_events']) != 0 and len(total_events['nb_people_engaged']) != 0 :
            init.write_stats_for_columns(sheet, config['sheets'][ANALYTICS_TYPE].get('measure_names', []), [(date_str, col_idx)], total_events, config['sheets'][ANALYTICS_TYPE]['data_row'])
    
    print(f"✅ SUCCESS! {ANALYTICS_TYPE} analytics recorded.") 

if __name__ == "__main__":
    main()
            

