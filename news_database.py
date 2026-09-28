# -*- coding: utf-8 -*-
"""
Historical News Database Module (SQLite)
Caches scraped news, resolved URLs, and extracted article text to avoid
redundant Brave Search API queries and Playwright extractions across runs.
"""

import sqlite3
import os
import glob
import pandas as pd
from datetime import datetime

DB_PATH = "news_database.db"

def get_db_connection(db_path=DB_PATH):
    """Establishes SQLite connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=DB_PATH):
    """Initializes the database schema with necessary tables and indexes."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historical_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        title_normalized TEXT NOT NULL,
        description TEXT,
        theme TEXT,
        language TEXT,
        published_date TEXT,
        google_news_url TEXT,
        resolved_url TEXT,
        extracted_text TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT,
        UNIQUE(title_normalized)
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title_norm ON historical_articles(title_normalized)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resolved_url ON historical_articles(resolved_url)")
    conn.commit()
    conn.close()

def normalize_title(title):
    """Normalizes title string for exact and case-insensitive matching."""
    if not title or pd.isna(title):
        return ""
    return str(title).strip().lower()

def lookup_article(title, db_path=DB_PATH):
    """
    Looks up an article by title in the database.
    Returns a dictionary of cached data or None.
    """
    norm = normalize_title(title)
    if not norm:
        return None
        
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT resolved_url, extracted_text, theme, published_date, description
        FROM historical_articles 
        WHERE title_normalized = ?
    """, (norm,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "resolved_url": row["resolved_url"],
            "extracted_text": row["extracted_text"],
            "theme": row["theme"],
            "published_date": row["published_date"],
            "description": row["description"]
        }
    return None

def upsert_article(title, description=None, theme=None, language=None, 
                   published_date=None, google_news_url=None, 
                   resolved_url=None, extracted_text=None, db_path=DB_PATH):
    """
    Inserts a new article or updates existing article data in the database.
    """
    norm = normalize_title(title)
    if not norm:
        return
        
    now = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO historical_articles (
        title, title_normalized, description, theme, language, 
        published_date, google_news_url, resolved_url, extracted_text, 
        first_seen_at, last_seen_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(title_normalized) DO UPDATE SET
        description = COALESCE(NULLIF(excluded.description, ''), historical_articles.description),
        theme = COALESCE(NULLIF(excluded.theme, ''), historical_articles.theme),
        language = COALESCE(NULLIF(excluded.language, ''), historical_articles.language),
        published_date = COALESCE(NULLIF(excluded.published_date, ''), historical_articles.published_date),
        google_news_url = COALESCE(NULLIF(excluded.google_news_url, ''), historical_articles.google_news_url),
        resolved_url = COALESCE(NULLIF(excluded.resolved_url, ''), historical_articles.resolved_url),
        extracted_text = COALESCE(NULLIF(excluded.extracted_text, ''), historical_articles.extracted_text),
        last_seen_at = excluded.last_seen_at
    """, (
        str(title).strip(), norm, 
        str(description).strip() if description and not pd.isna(description) else None,
        str(theme).strip() if theme and not pd.isna(theme) else None,
        str(language).strip() if language and not pd.isna(language) else None,
        str(published_date).strip() if published_date and not pd.isna(published_date) else None,
        str(google_news_url).strip() if google_news_url and not pd.isna(google_news_url) else None,
        str(resolved_url).strip() if resolved_url and not pd.isna(resolved_url) and resolved_url != "None" else None,
        str(extracted_text).strip() if extracted_text and not pd.isna(extracted_text) and not str(extracted_text).startswith("Failed:") else None,
        now, now
    ))
    conn.commit()
    conn.close()

def bulk_fill_from_cache(df, db_path=DB_PATH):
    """
    Checks each article in df against the database.
    Populates 'Resolved_URL_via_GoogleSearch' and 'Extracted_Article_Text'
    from cache when available.
    Returns (updated_df, cached_url_count, cached_text_count).
    """
    if "Resolved_URL_via_GoogleSearch" not in df.columns:
        df["Resolved_URL_via_GoogleSearch"] = None
    if "Extracted_Article_Text" not in df.columns:
        df["Extracted_Article_Text"] = None

    cached_urls = 0
    cached_texts = 0
    
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    for idx, row in df.iterrows():
        title = row.get("Title")
        norm = normalize_title(title)
        if not norm:
            continue
            
        cursor.execute("SELECT resolved_url, extracted_text FROM historical_articles WHERE title_normalized = ?", (norm,))
        res = cursor.fetchone()
        if res:
            res_url = res["resolved_url"]
            ext_text = res["extracted_text"]
            
            # Fill resolved URL if cached and not yet present in df
            if res_url and (pd.isna(df.at[idx, "Resolved_URL_via_GoogleSearch"]) or df.at[idx, "Resolved_URL_via_GoogleSearch"] in [None, "", "None", "nan"]):
                df.at[idx, "Resolved_URL_via_GoogleSearch"] = res_url
                cached_urls += 1
                
            # Fill extracted text if cached and valid
            if ext_text and (pd.isna(df.at[idx, "Extracted_Article_Text"]) or df.at[idx, "Extracted_Article_Text"] in [None, "", "None", "nan"]):
                df.at[idx, "Extracted_Article_Text"] = ext_text
                cached_texts += 1
                
    conn.close()
    return df, cached_urls, cached_texts

def save_dataframe_to_db(df, db_path=DB_PATH):
    """Saves all rows from a DataFrame into the database."""
    init_db(db_path)
    saved_count = 0
    for _, row in df.iterrows():
        title = row.get("Title")
        if pd.isna(title) or not str(title).strip():
            continue
            
        upsert_article(
            title=title,
            description=row.get("Description"),
            theme=row.get("Theme"),
            language=row.get("Language"),
            published_date=row.get("Date"),
            google_news_url=row.get("URL"),
            resolved_url=row.get("Resolved_URL_via_GoogleSearch"),
            extracted_text=row.get("Extracted_Article_Text"),
            db_path=db_path
        )
        saved_count += 1
    return saved_count

def backfill_all_historical_csvs(db_path=DB_PATH):
    """Scans and backfills all historical CSV files into the database."""
    init_db(db_path)
    files = glob.glob("*_fulltext.csv") + glob.glob("*_resolved.csv")
    total_files = len(files)
    total_articles = 0
    print(f"📦 Starting backfill from {total_files} historical CSV files...")
    
    for f in sorted(files):
        try:
            df = pd.read_csv(f)
            if "Title" not in df.columns:
                continue
            saved = save_dataframe_to_db(df, db_path)
            total_articles += saved
            print(f"  ✓ Ingested {saved} rows from: {f}")
        except Exception as e:
            print(f"  ❌ Error reading {f}: {e}")
            
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total, COUNT(resolved_url) as resolved, COUNT(extracted_text) as extracted FROM historical_articles")
    stats = cursor.fetchone()
    conn.close()
    
    print("\n========================================================")
    print("📊 HISTORICAL NEWS DATABASE STATS")
    print("========================================================")
    print(f"  Total Unique Articles in DB : {stats['total']}")
    print(f"  Articles with Resolved URLs : {stats['resolved']}")
    print(f"  Articles with Extracted Text: {stats['extracted']}")
    print("========================================================\n")
    return stats

if __name__ == "__main__":
    backfill_all_historical_csvs()
