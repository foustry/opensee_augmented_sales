#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool to extract and analyze news articles from the SQLite news database
mentioning family offices investing in, allocating to, or backing hedge funds.
"""

import sqlite3
import re
import argparse
import pandas as pd
from datetime import datetime

DEFAULT_DB = "news_database.db"

def extract_news(db_path=DEFAULT_DB, year="2026"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT id, title, description, published_date, theme, google_news_url, resolved_url, extracted_text
    FROM historical_articles
    WHERE published_date LIKE ?
    """
    cursor.execute(query, (f"{year}%",))
    rows = cursor.fetchall()
    conn.close()

    fo_pattern = re.compile(r'\bfamily\s+offices?\b', re.IGNORECASE)
    hf_pattern = re.compile(r'\bhedge\s+funds?\b', re.IGNORECASE)

    # Keywords indicating investment, allocation, backing, commitments, exposure
    invest_pattern = re.compile(
        r'\b(invest|invests|investing|investment|investor|investors|'
        r'allocate|allocates|allocating|allocation|allocations|allocator|allocators|'
        r'back|backs|backing|backed|co-invest|co-investing|co-investment|co-investments|'
        r'commit|commits|committing|commitment|commitments|exposure|pour|poured|pouring|'
        r'deploy|deploying|deployed|lps?|sub-advisor|mandates?)\b',
        re.IGNORECASE
    )

    results = []
    for r in rows:
        title = r['title'] or ''
        desc = r['description'] or ''
        text = r['extracted_text'] or ''
        combined = f"{title}\n{desc}\n{text}"

        has_fo = bool(fo_pattern.search(combined))
        has_hf = bool(hf_pattern.search(combined))

        if has_fo and has_hf:
            # Check proximity between FO and HF
            fo_matches = list(fo_pattern.finditer(combined))
            hf_matches = list(hf_pattern.finditer(combined))
            
            min_dist = min(abs(fo.start() - hf.start()) for fo in fo_matches for hf in hf_matches)
            
            # Find best snippet
            best_snippet = ""
            for fo in fo_matches:
                for hf in hf_matches:
                    if abs(fo.start() - hf.start()) <= 500:
                        st = max(0, min(fo.start(), hf.start()) - 100)
                        en = min(len(combined), max(fo.end(), hf.end()) + 100)
                        best_snippet = combined[st:en].replace('\n', ' ')
                        break
                if best_snippet:
                    break

            results.append({
                "id": r["id"],
                "published_date": r["published_date"],
                "title": title,
                "url": r["resolved_url"] or r["google_news_url"],
                "min_distance_chars": min_dist,
                "snippet": best_snippet or combined[:300].replace('\n', ' ')
            })

    results.sort(key=lambda x: x["min_distance_chars"])
    return results

def main():
    parser = argparse.ArgumentParser(description="Extract news mentioning family offices investing in hedge funds")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite database")
    parser.add_argument("--year", default="2026", help="Year prefix (default: 2026)")
    parser.add_argument("--csv", help="Save output to CSV file")
    args = parser.parse_args()

    results = extract_news(args.db, args.year)
    print(f"Found {len(results)} articles mentioning both family offices and hedge funds for year {args.year}.")
    
    if args.csv:
        df = pd.DataFrame(results)
        df.to_csv(args.csv, index=False)
        print(f"Results exported to {args.csv}")
    else:
        for idx, item in enumerate(results[:20], 1):
            print(f"[{idx}] ID: {item['id']} | Date: {item['published_date'][:10]} | Title: {item['title']}")
            print(f"    URL: {item['url']}")
            print(f"    Snippet: {item['snippet'][:180]}...")

if __name__ == "__main__":
    main()
