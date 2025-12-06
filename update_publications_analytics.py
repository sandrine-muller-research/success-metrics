import requests
from datetime import datetime
import json
import os
import time
from collections import defaultdict
import init
from semanticscholar import SemanticScholar

# List of DOIs from your Biomedical Data Translator publications
DOIS = [doi for doi in init.load_publications()['publications'] if 'doi' in doi for doi in [doi['doi']]]
ANALYTICS_TYPE = 'publications_stats'



def get_citations_semanticscholar(doi):
    """Semantic Scholar - Year as string"""
    sch = SemanticScholar()
    
    try:
        # Find paper by DOI
        paper = sch.get_paper(doi)
        citations = []
        
        # Get first 10 citations with metadata
        for citation in paper.citations[:10]:
            year = getattr(citation, 'year', None)
            citations.append({
                'title': citation.title,
                'doi': getattr(citation, 'doi', None),
                'publication_date': str(year) if year is not None else None,  # Convert to string
                'source': 'semanticscholar'
            })
        return citations
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []

def get_citations_openalex(doi):
    """OpenAlex - Complete citation lookup with search fallback"""
    # First try direct DOI lookup
    url = f"https://api.openalex.org/works/DOI:{doi}"
    try:
        resp = requests.get(url, timeout=10)
        print(f"Direct DOI lookup status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"Found work with cited_by_count: {data.get('cited_by_count', 0)}")
            return _extract_citations(data)
        
        # Fallback: Search for DOI if direct lookup fails
        elif resp.status_code == 404:
            print("Direct DOI not found, trying search...")
            search_url = f"https://api.openalex.org/works?filter=doi:{doi}&per-page=1"
            search_resp = requests.get(search_url, timeout=10)
            print(f"Search status: {search_resp.status_code}")
            
            if search_resp.status_code == 200:
                search_data = search_resp.json()
                results = search_data.get('results', [])
                if results:
                    print(f"Found work via search with cited_by_count: {results[0].get('cited_by_count', 0)}")
                    return _extract_citations(results[0])
                
    except Exception as e:
        print(f"Error: {str(e)}")
    
    return []

def _extract_citations(work_data):
    """Extract citations from work data using correct filter format"""
    work_id = work_data.get('id')
    if not work_id:
        return []
    
    # Use short ID format (W12345) for cites filter
    work_id_short = work_id.split('/')[-1]
    citing_url = f"https://api.openalex.org/works?filter=cites:{work_id_short}&per-page=10"
    
    try:
        citing_resp = requests.get(citing_url, timeout=10)
        print(f"Citing works status: {citing_resp.status_code}")
        
        if citing_resp.status_code == 200:
            citing_data = citing_resp.json()
            works = citing_data.get('results', [])
            print(f"Found {len(works)} citing works")
            
            citing = []
            for work in works:
                citing.append({
                    'title': work.get('title', '').strip(),
                    'doi': work.get('doi'),
                    'publication_date': work.get('publication_date'),
                    'source': 'openalex'
                })
            return citing
            
    except Exception as e:
        print(f"Citing extraction error: {str(e)}")
    
    return []


def _extract_citations(work_data):
    """Extract citations from work data using correct filter format"""
    work_id = work_data.get('id')
    if not work_id:
        return []
    
    # Use short ID format (W12345) for cites filter
    work_id_short = work_id.split('/')[-1]
    citing_url = f"https://api.openalex.org/works?filter=cites:{work_id_short}&per-page=10"
    
    try:
        citing_resp = requests.get(citing_url, timeout=10)
        print(f"Citing works status: {citing_resp.status_code}")
        
        if citing_resp.status_code == 200:
            citing_data = citing_resp.json()
            works = citing_data.get('results', [])
            print(f"Found {len(works)} citing works")
            
            citing = []
            for work in works:
                citing.append({
                    'title': work.get('title', '').strip(),
                    'doi': work.get('doi'),
                    'publication_date': work.get('publication_date'),
                    'source': 'openalex'
                })
            return citing
            
    except Exception as e:
        print(f"Citing extraction error: {str(e)}")
    
    return []



def get_publications_citations():
    """Enhanced deduplication + OpenAlex date priority"""
    all_citing_by_doi = defaultdict(list)
    
    for doi in DOIS:
        print(f"Processing {doi}...")
        
        # Get citations from multiple sources
        openalex_cits = get_citations_openalex(doi)
        semanticscholar_cits = get_citations_semanticscholar(doi)

        
        # Combine ALL citations
        all_citations = openalex_cits + semanticscholar_cits
        
        # Deduplicate with OpenAlex date priority
        seen_dois = {}  # Track best version of each DOI
        for cit in all_citations:
            cit_doi = cit.get('doi')
            if not cit_doi:
                continue  # Skip citations without DOI
            
            # Prioritize OpenAlex dates, then Semantic Scholar #######TO fix
            if cit_doi not in seen_dois and cit.get('publication_date'):
                # Use OpenAlex if available, or update if better date
                if cit.source == 'openalex' or (seen_dois[cit_doi]['source'] != 'openalex' and cit.get('publication_date')):
                seen_dois[cit_doi] = {
                    'title': cit.get('title', ''),
                    'doi': cit_doi,
                    'publication_date': cit.get('publication_date'),  # OpenAlex preferred
                    'source': cit.get('source', 'combined')
                }
        
        # Convert to list and add title-only matches (fallback)
        unique_citations = list(seen_dois.values())
        
        # Add title-only citations (no DOI) if not already present
        for cit in all_citations:
            if not cit.get('doi'):  # Title-only
                title_key = cit.get('title', '')[:50]
                if title_key and not any(
                    existing.get('title', '')[:50] == title_key 
                    for existing in unique_citations
                ):
                    unique_citations.append(cit)
        
        all_citing_by_doi[doi] = unique_citations
        
        print(f"Found {len(unique_citations)} unique citing papers for {doi}")
        time.sleep(2)
    
    output = {doi: list(cits) for doi, cits in all_citing_by_doi.items()}
    
    with open('all_citing_papers_by_doi.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    return output



def filter_citations_by_date(citations_output, date_str):
    """
    Returns dict with:
    - num_original_pubs: # of input publications (DOIs) with ANY citation before/on date_str
    - num_citing_pubs: total # of unique citing publications before/on date_str
    """
    cutoff_date = datetime.strptime(date_str, '%Y-%m-%d')
    original_pubs_with_citations = 0
    all_citing_dois = set()
    
    for input_doi, citing_list in citations_output.items():
        has_early_citation = False
        
        for citation in citing_list:
            pub_date_str = citation.get('publication_date')
            if pub_date_str:
                try:
                    # Handle different date formats: YYYY, YYYY-MM, YYYY-MM-DD
                    if '-' in pub_date_str:
                        cit_date = datetime.strptime(pub_date_str, '%Y-%m-%d')
                    else:
                        cit_date = datetime.strptime(pub_date_str, '%Y')
                        cit_date = cit_date.replace(month=1, day=1)  # Normalize to year start
                    
                    if cit_date <= cutoff_date:
                        has_early_citation = True
                        # Collect unique citing DOIs
                        if citation.get('doi'):
                            all_citing_dois.add(citation['doi'])
                        break  # Found one early citation for this input DOI
                except ValueError:
                    continue  # Skip invalid dates
        
        if has_early_citation:
            original_pubs_with_citations += 1
    
    return {
        'num_original_pubs': original_pubs_with_citations,
        'num_citing_pubs': len(all_citing_dois)
    }

def main():
    config = init.load_config()
    
    # ------------------------------
    # Connect to Google Sheets:
    # ------------------------------
    client = init.get_client()
    spreadsheet = client.open_by_key(config['sheets']['github_stats']['sheet_id'])
    community_sheet = spreadsheet.worksheet("population")
    
    # Get dates:
    pending_dates = init.get_pending_date_columns(community_sheet, config['sheets']['github_stats']['date_row'], config['sheets']['github_stats']['data_row'])
    if not  pending_dates:
        print("✅ No pending dates - all columns filled!")
    else:
        print(f"📊 Found {len(pending_dates)} pending date columns: {pending_dates}")
        
    # ------------------------------
    # Publications analytics:
    # ------------------------------
    citations = get_publications_citations()
    for date_str, col_idx in pending_dates:
        out = filter_citations_by_date(citations, date_str)
        print(f"Total internal publications: {out['num_original_pubs']}, Total citations: {out['num_citing_pubs']}")
        init.write_stats_for_columns(community_sheet, out, config['sheets'][ANALYTICS_TYPE]['data_row'], [(date_str, col_idx)],['num_original_pubs','num_citing_pubs'])
    
    
    print(f"✅ SUCCESS! {ANALYTICS_TYPE} analytics recorded.") 

if __name__ == "__main__":
    main()
            

