import json
from datetime import datetime
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
from itertools import product
from typing import List, Tuple
from gspread.utils import rowcol_to_a1

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

def load_config(config_file='config.json'):
    """
    Load public config.json with sheet IDs, tabs, date rows.
    
    Returns: dict from config.json
    """
    config_path = Path(config_file)
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Create config.json:\n"
            f"  {config_path}\n\n"
            f"Example:\n"
            f'{{\n'
            f'  "sheets": {{\n'
            f'    "github_stats": {{\n'
            f'      "sheet_id": "your_sheet_id",\n'
            f'      "tab_name": "MY_NAME",\n'
            f'      "date_row": 1,\n'
            f'      "data_row": 2\n'
            f'    }}\n'
            f'  }}\n'
            f'}}'
        )
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Validate structure
        if 'sheets' not in config:
            raise ValueError("config.json missing 'sheets' key")
        
        print(f"✅ Loaded config")
        return config
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {config_file}: {e}")

def load_publications():
    pub_path = Path(load_config()['Publications']['file_path'])
    
    if not pub_path.exists():
        raise FileNotFoundError(
            f"Publications .json file not found.\n"
        )
    
    try:
        with open(pub_path, 'r', encoding='utf-8') as f:
            pub = json.load(f)
        
        # Validate structure
        if 'publications' not in pub:
            raise ValueError("pub.json missing 'publications' key")
        
        print(f"✅ Loaded publications")
        return pub
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {pub_path}: {e}")

def get_client():
    creds_file = Path('credentials.json')
    if not creds_file.exists():
        raise FileNotFoundError("no credentials.json found.")
    
    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    return gspread.authorize(creds)

def get_pending_date_columns(sheet, date_row, data_row,number_rows_to_update=1):
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
    
    headers = sheet.row_values(date_row)
    
    for col_idx, date_str in enumerate(headers, 1):
        try:
            header_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            continue
        
        if header_date <= today:
            for rows_idx in range(number_rows_to_update):
                data_cell = gspread.utils.rowcol_to_a1(data_row+rows_idx, col_idx)
                data_value = sheet.acell(data_cell).value
            
                if data_value is None or data_value.strip() == "":
                    pending_columns.append((date_str, col_idx))
    
    return pending_columns


def write_stats_for_columns(sheet, type_to_write: List[List[str]], pending_columns: List[Tuple[str, int]], results: dict, data_row: int = 1):
    """Writes data row-by-row in flattened format across all combinations."""
    row_counter = 0  # Sequential row index for flattened layout
    
    # Generate ALL combinations in order
    for combo in product(*type_to_write):
        # Get value for this combination
        value = results
        for level in combo:
            if isinstance(value, dict):
                value = value.get(level, '')
            else:
                break
        
        # Write to sequential row for each pending column
        for date_str, col_idx in pending_columns:
            cell = rowcol_to_a1(data_row + row_counter, col_idx)
            sheet.update_acell(cell, value)
        
        row_counter += 1  # Move to next row for next combination
