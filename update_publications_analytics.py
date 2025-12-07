import requests
from datetime import datetime
import json
import os
import time
from collections import defaultdict
import init
from semanticscholar import SemanticScholar

# List of DOIs from your Biomedical Data Translator publications
TRANSLATOR_pubs = init.load_publications()['publications']
TITLES = [pub['title'] if 'title' in pub else '' for pub in TRANSLATOR_pubs]
DOIS = [pub['doi'] if 'doi' in pub else '' for pub in TRANSLATOR_pubs]
ANALYTICS_TYPE = 'publications_stats'

def get_semanticscholar_pub_info(paper):
    """Semantic Scholar - Basic publication info"""
    
    try:
        pub_dt = getattr(paper, 'publicationDate')  # datetime.datetime(2025, 8, 29, 0, 0)
        pub_str = pub_dt.strftime('%Y-%m-%d') if pub_dt is not None else None            
        pub = {
        'title': paper.title,
        'doi': getattr(paper, 'externalIds', {}).get('DOI') if hasattr(paper, 'externalIds') else None,
        'publication_date': pub_str if pub_str is not None else None,
        'source': 'semanticscholar'
        }
        return pub
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return None

def get_citations_semanticscholar_from_doi(doi):
    """Semantic Scholar - Year as string"""
    sch = SemanticScholar()
    
    try:
        # Find paper by DOI
        paper = sch.get_paper(doi)
        pub = get_semanticscholar_pub_info(paper)
        
        if pub is not None:
            citations = []
            
            # Get first 10 citations with metadata
            for citation in paper.citations:
                cit = get_semanticscholar_pub_info(citation)
                if cit is not None:
                    citations.append(cit)      

            pub['citations'] = citations
            return pub
        else:
            return []
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []

def get_citations_semanticscholar_from_title(title: str):
    """Semantic Scholar - query by title and return pub info + citations."""
    sch = SemanticScholar()

    try:
        # Search paper by title (take best match)
        results = sch.search_paper(title, limit=1)
        if not results or len(results) == 0:
            return []

        paper = results[0]
        pub = get_semanticscholar_pub_info(paper)

        if pub is not None:
            citations = []

            for citation in paper.citations:
                cit = get_semanticscholar_pub_info(citation)
                if cit is not None:
                    citations.append(cit)

            pub['citations'] = citations
            return pub
        else:
            return []
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []

def get_citations_openalex_from_doi(doi):
    """OpenAlex - Complete citation lookup with search fallback"""
    # First try direct DOI lookup 
    url = f"https://api.openalex.org/works?filter=doi:{doi}"
    try:
        search_resp = requests.get(url, timeout=10)

        print(f"Search status: {search_resp.status_code}")
        
        if search_resp.status_code == 200:
            search_data = search_resp.json()
            results = search_data.get('results', [])
            if len(results)>0:
                pub = {
                'title': results[0].get('title', '').strip(),
                'doi': results[0].get('doi'),
                'publication_date': results[0].get('publication_date'),
                'source': 'openalex'
                }
                pub['citations'] = _extract_citations(results[0])
                return pub
            else :
                print("No results found for DOI search")
                return []
        else:
            print(f"Error: {str(e)}")
            return []
                
    except Exception as e:
        print(f"Error: {str(e)}")
        return []

def get_citations_openalex_from_title(title: str):
    """OpenAlex - Complete citation lookup by title search"""
    # Search by title
    search_url = f"https://api.openalex.org/works?filter=title.search:'{title}'&per-page=1"
    try:
        resp = requests.get(search_url, timeout=10)
        print(f"Title search status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('results', [])
            print(f"Found {len(results)} matching works")
            
            if results:
                work = results[0]  # Take best match
                print(f"Found work with cited_by_count: {work.get('cited_by_count', 0)}")
                
                pub = {
                    'title': work.get('title', '').strip(),
                    'doi': work.get('doi'),
                    'publication_date': work.get('publication_date'),
                    'source': 'openalex'
                }
                pub['citations'] = _extract_citations(work)
                return pub
        
        print("No results found for title search")
        
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



def get_publications_citations():
    """Enhanced deduplication + OpenAlex date priority"""
    all_citing_by_doi = defaultdict(list)
    if len(DOIS) != len(TITLES):
        raise ValueError("DOIS and TITLES lists must be of same length.")
    else: 
        for i,doi in enumerate(DOIS):

            # Get citations from sources
            if doi != '':
                print(f"Processing {doi}...")
                
                openalex_cits = get_citations_openalex_from_doi(doi)
                semanticscholar_cits = get_citations_semanticscholar_from_doi(doi)

            elif 'title' in TITLES:
                print(f"No DOI, processing by title...")
                openalex_cits = get_citations_openalex_from_title(TITLES[i])
                semanticscholar_cits = get_citations_semanticscholar_from_title(TITLES[i])
                
                
            # Combine citations from sources    
            if len(openalex_cits) == 0 and len(semanticscholar_cits) == 0:
                print(f"No citations found for {doi if doi != '' else TITLES[i]}")
                continue
            
            elif len(openalex_cits) == 0 and len(semanticscholar_cits) != 0:
                if 'citations' in semanticscholar_cits:
                    all_citations = semanticscholar_cits['citations']
                    
            elif len(semanticscholar_cits) == 0 and len(openalex_cits) != 0:
                if 'citations' in openalex_cits:
                    all_citations = openalex_cits['citations']
            elif len(openalex_cits) != 0 and len(semanticscholar_cits) != 0:
                if 'citations' in openalex_cits and 'citations' in semanticscholar_cits:
                    all_citations = openalex_cits['citations'] + semanticscholar_cits['citations']
                elif 'citations' in openalex_cits and 'citations' not in semanticscholar_cits:
                    all_citations = openalex_cits['citations']
                elif 'citations' not in openalex_cits and 'citations' in semanticscholar_cits:
                    all_citations = semanticscholar_cits['citations']
                            
            if all_citations is None:
                all_citations = []
            
            if len(all_citations) != 0:
                # Deduplicate with OpenAlex date priority
                seen_dois = {}  # Track best version of each DOI
                for cit in all_citations:
                    cit_doi = cit.get('doi')
                    if not cit_doi:
                        continue  # Skip citations without DOI - will handle later
                    
                    # Prioritize OpenAlex dates, then Semantic Scholar
                    if cit_doi not in seen_dois :
                        if cit.get('source') == 'openalex':
                            seen_dois[cit_doi] = {
                                'title': cit.get('title', ''),
                                'doi': cit_doi,
                                'publication_date': cit.get('publication_date'),  # OpenAlex preferred
                                'source': cit.get('source', 'combined')
                            }
                    if cit_doi in seen_dois:
                        existing = seen_dois[cit_doi]
                        if (cit.get('source') == 'openalex') and (existing.get('source') == 'semanticscholar') and (cit.get('publication_date') is not None) and (existing.get('source') == 'semanticscholar'):
                            seen_dois[cit_doi]['publication_date'] = cit.get('publication_date')
                            seen_dois[cit_doi]['source'] = cit.get('source', existing['source'])
            
                # Convert to list and add title-only matches
                unique_citations = list(seen_dois.values())
                    
                # get unique title-only citations
                unique_title_only_citations = []
                for cit in all_citations:
                    if cit.get('doi') is None or cit.get('doi') == '':
                        title_key = cit.get('title', '')[:50]
                        if title_key is not None:
                            if title_key != '':
                                existing = next((e for e in unique_title_only_citations if e.get('title', '')[:50] == title_key), None)
                                if existing is None:
                                    unique_title_only_citations.remove(existing) if existing else None
                                    unique_title_only_citations.append(cit)
                                elif cit.get('publication_date') is not None: 
                                    if cit.get('publication_date') < existing.get('publication_date'):
                                        unique_title_only_citations.remove(existing) if existing else None
                                        unique_title_only_citations.append(cit)                                

                [unique_citations.append(cit) for cit in unique_title_only_citations if cit.get('title', '')[:50] not in [u.get('title', '')[:50] for u in unique_citations]]
                
                all_citing_by_doi[doi] = unique_citations
            
                print(f"Found {len(unique_citations)} unique citing papers for {doi}")
                
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
                        # Collect unique citing DOIs
                        if citation.get('doi'):
                            all_citing_dois.add(citation['doi'])
                        break  # Found one early citation for this input DOI
                except ValueError:
                    continue  # Skip invalid dates

    
    return {
        'num_original_pubs': len(citations_output),
        'num_citing_pubs': len(all_citing_dois)
    }

def main():
    config = init.load_config()
    
    # ------------------------------
    # Connect to Google Sheets:
    # ------------------------------
    client = init.get_client()
    spreadsheet = client.open_by_key(config['sheets']['publications_stats']['sheet_id'])
    community_sheet = spreadsheet.worksheet("population")
    
    # Get dates:
    pending_dates = init.get_pending_date_columns(community_sheet, config['sheets']['publications_stats']['date_row'], config['sheets']['publications_stats']['data_row'])
        
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
            

