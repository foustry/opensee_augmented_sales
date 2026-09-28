import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import re

DB_PATH = "news_database.db"

def search_buyside():
    # 1. Date calculation (3 months ago from Aug 28, 2026)
    target_date = "2026-05-28"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Define keywords from skills_buyside.md
    # We'll search in title and description
    
    # Query for all articles in the last 3 months
    cursor.execute("""
        SELECT title, description, published_date, google_news_url, resolved_url, theme, extracted_text
        FROM historical_articles
        WHERE published_date >= ?
    """, (target_date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    matches = []
    
    # Keywords from skill
    buyside_entities = [r"Asset Management", r"Hedge Fund", r"Pension Fund", r"Wealth Management", r"Family Office"]
    actions = [r"appointed", r"hired", r"joins", r"named", r"new hire", r"executive transition"]
    roles = [r"Portfolio Manager", r"Chief Investment Officer", r"CIO", r"Head of Research"]
    launches = [r"launches new fund", r"closes fund", r"new UCITS", r"team lift-out"]
    mandates = [r"wins mandate", r"awarded mandate", r"selected to manage"]
    firms = [r"BlackRock", r"Vanguard", r"Amundi"]
    
    def contains_any(text, patterns):
        if not text: return False
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)

    for row in rows:
        text = f"{row['title']} {row['description'] if row['description'] else ''}"
        
        is_match = False
        
        # Logic 1: (Asset Management OR Hedge Fund OR Pension Fund) AND (appointed OR hired OR joins)
        if contains_any(text, buyside_entities) and contains_any(text, actions):
            is_match = True
        
        # Logic 2: (Portfolio Manager OR Chief Investment Officer OR CIO OR Head of Research) AND (joins OR named)
        if not is_match and contains_any(text, roles) and contains_any(text, actions):
            is_match = True
            
        # Logic 3: launches new fund OR closes fund OR new UCITS OR team lift-out
        if not is_match and contains_any(text, launches):
            is_match = True
            
        # Logic 4: (wins mandate OR awarded mandate OR selected to manage) AND (BlackRock OR Vanguard OR Amundi)
        if not is_match and contains_any(text, mandates) and contains_any(text, firms):
            is_match = True
            
        # Logic 5: (Wealth Management OR Family Office) AND (new hire OR executive transition)
        if not is_match and contains_any(text, [r"Wealth Management", r"Family Office"]) and contains_any(text, [r"new hire", r"executive transition"]):
            is_match = True

        if is_match:
            matches.append({
                "Date": row['published_date'].split(' ')[0],
                "Title": row['title'],
                "Description": row['description'],
                "URL": row['resolved_url'] if row['resolved_url'] else row['google_news_url'],
                "Theme": row['theme'],
                "ExtractedText": row['extracted_text']
            })

    if not matches:
        print("No buy-side matches found in the last 3 months.")
        return

    df = pd.DataFrame(matches)
    # Deduplicate by title
    df.drop_duplicates(subset=['Title'], inplace=True)
    
    print(f"Found {len(df)} matches.")
    
    # Save to CSV for reference
    output_file = "buyside_search_results_3m.csv"
    df.to_csv(output_file, index=False)
    print(f"Results saved to {output_file}")
    
    # Return matches for the agent to process
    return df

if __name__ == "__main__":
    search_buyside()
