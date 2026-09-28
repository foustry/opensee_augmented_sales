#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Merge Utility
Merges news_database.db and news_database_elena.db into a unified, clean database.

Key Features:
- Preserves unique constraint on title_normalized.
- Preserves existing IDs from news_database.db.
- Assigns new auto-increment IDs for new articles from news_database_elena.db.
- Deduplication and conflict resolution:
  * Extracted text: selects highest-quality / complete text (filtering error stubs/blocked pages).
  * Resolved URL: aligns with selected extracted text or selects highest-quality deep link.
  * Timestamps: earliest first_seen_at, latest last_seen_at.
  * Metadata (description, theme, language, date): fills missing values, selects richest non-empty fields.
- Full backup of both source databases prior to modification.
- Atomic file replacement and SQLite integrity checks.
"""

import os
import sys
import shutil
import sqlite3
import argparse
from datetime import datetime

MAIN_DB = "news_database.db"
ELENA_DB = "news_database_elena.db"
MERGED_OUTPUT_DB = "news_database.db"
STANDALONE_MERGED_DB = "news_database_merged.db"

def text_quality(txt):
    """Calculates text extraction quality score.
    Returns 0 for missing, stubs, bot blockers, or extraction failures.
    Returns character length for valid text.
    """
    if not txt or not isinstance(txt, str):
        return 0
    s = txt.strip()
    if not s or s == "No URL provided" or s.startswith("Failed:"):
        return 0
    if s.startswith("Id: ") and "Client IP:" in s:
        return 0
    return len(s)

def url_quality(url):
    """Scores URL validity and specificity.
    Higher score for deep paths over domain roots/homepages.
    """
    if not url or not isinstance(url, str):
        return 0
    s = url.strip()
    if not s or s == "None":
        return 0
    parts = [p for p in s.split("/") if p and not p.endswith(":")]
    if len(parts) <= 1:
        return 1
    return 10 + len(s)

def clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s != "None" else None

def best_timestamp_min(t1, t2):
    t1 = clean_str(t1)
    t2 = clean_str(t2)
    if t1 and t2:
        return min(t1, t2)
    return t1 or t2

def best_timestamp_max(t1, t2):
    t1 = clean_str(t1)
    t2 = clean_str(t2)
    if t1 and t2:
        return max(t1, t2)
    return t1 or t2

def create_backups(main_db=MAIN_DB, elena_db=ELENA_DB):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    main_bak = f"{main_db}.bak_{timestamp}"
    elena_bak = f"{elena_db}.bak_{timestamp}"
    
    print(f"📦 Creating backup of {main_db} -> {main_bak}")
    shutil.copy2(main_db, main_bak)
    
    print(f"📦 Creating backup of {elena_db} -> {elena_bak}")
    shutil.copy2(elena_db, elena_bak)
    
    return main_bak, elena_bak

def merge_databases(main_db=MAIN_DB, elena_db=ELENA_DB, dry_run=False):
    if not os.path.exists(main_db):
        raise FileNotFoundError(f"Main database not found: {main_db}")
    if not os.path.exists(elena_db):
        raise FileNotFoundError(f"Elena database not found: {elena_db}")

    print(f"\n========================================================")
    print(f"🔀 Starting Database Merge")
    print(f"   Main DB : {main_db}")
    print(f"   Elena DB: {elena_db}")
    print(f"========================================================\n")

    c_main = sqlite3.connect(main_db)
    c_elena = sqlite3.connect(elena_db)

    # Fetch stats
    count_m = c_main.execute("SELECT count(*) FROM historical_articles").fetchone()[0]
    count_e = c_elena.execute("SELECT count(*) FROM historical_articles").fetchone()[0]
    print(f"📊 Source Counts:")
    print(f"   {main_db} articles: {count_m:,}")
    print(f"   {elena_db} articles: {count_e:,}")

    # Load all rows from Main
    print(f"📥 Loading records from {main_db}...")
    main_rows = c_main.execute("""
        SELECT id, title, title_normalized, description, theme, language,
               published_date, google_news_url, resolved_url, extracted_text,
               first_seen_at, last_seen_at
        FROM historical_articles
    """).fetchall()

    main_dict = {}
    for r in main_rows:
        norm = r[2]
        main_dict[norm] = {
            "id": r[0],
            "title": clean_str(r[1]),
            "title_normalized": norm,
            "description": clean_str(r[3]),
            "theme": clean_str(r[4]),
            "language": clean_str(r[5]),
            "published_date": clean_str(r[6]),
            "google_news_url": clean_str(r[7]),
            "resolved_url": clean_str(r[8]),
            "extracted_text": clean_str(r[9]),
            "first_seen_at": clean_str(r[10]),
            "last_seen_at": clean_str(r[11])
        }

    # Load all rows from Elena
    print(f"📥 Loading records from {elena_db}...")
    elena_rows = c_elena.execute("""
        SELECT id, title, title_normalized, description, theme, language,
               published_date, google_news_url, resolved_url, extracted_text,
               first_seen_at, last_seen_at
        FROM historical_articles
    """).fetchall()

    elena_dict = {}
    for r in elena_rows:
        norm = r[2]
        elena_dict[norm] = {
            "id": r[0],
            "title": clean_str(r[1]),
            "title_normalized": norm,
            "description": clean_str(r[3]),
            "theme": clean_str(r[4]),
            "language": clean_str(r[5]),
            "published_date": clean_str(r[6]),
            "google_news_url": clean_str(r[7]),
            "resolved_url": clean_str(r[8]),
            "extracted_text": clean_str(r[9]),
            "first_seen_at": clean_str(r[10]),
            "last_seen_at": clean_str(r[11])
        }

    c_main.close()
    c_elena.close()

    # Track metrics
    elena_only_count = 0
    main_only_count = 0
    overlap_count = 0
    text_upgraded_from_elena = 0
    url_upgraded_from_elena = 0

    merged_records = []

    # 1. Process Main records (and merge overlapping Elena records)
    for norm, m_rec in main_dict.items():
        if norm in elena_dict:
            overlap_count += 1
            e_rec = elena_dict[norm]

            q_mt = text_quality(m_rec["extracted_text"])
            q_et = text_quality(e_rec["extracted_text"])
            q_mu = url_quality(m_rec["resolved_url"])
            q_eu = url_quality(e_rec["resolved_url"])

            # Resolve extracted text & URL
            if q_et > q_mt:
                best_text = e_rec["extracted_text"]
                # Elena has superior text; prefer Elena's URL if valid to keep extraction consistent
                best_url = e_rec["resolved_url"] if q_eu > 0 else m_rec["resolved_url"]
                text_upgraded_from_elena += 1
                if best_url == e_rec["resolved_url"] and e_rec["resolved_url"] != m_rec["resolved_url"]:
                    url_upgraded_from_elena += 1
            elif q_mt > q_et:
                best_text = m_rec["extracted_text"]
                best_url = m_rec["resolved_url"] if q_mu > 0 else e_rec["resolved_url"]
            else:
                # Equal text quality
                best_text = m_rec["extracted_text"] or e_rec["extracted_text"]
                if q_eu > q_mu:
                    best_url = e_rec["resolved_url"]
                    url_upgraded_from_elena += 1
                else:
                    best_url = m_rec["resolved_url"] or e_rec["resolved_url"]

            # Resolve description
            desc_m = m_rec["description"] or ""
            desc_e = e_rec["description"] or ""
            best_desc = desc_m if len(desc_m) >= len(desc_e) else desc_e

            merged_record = {
                "id": m_rec["id"],  # Preserve original ID
                "title": m_rec["title"] or e_rec["title"],
                "title_normalized": norm,
                "description": best_desc if best_desc else None,
                "theme": m_rec["theme"] or e_rec["theme"],
                "language": m_rec["language"] or e_rec["language"],
                "published_date": m_rec["published_date"] or e_rec["published_date"],
                "google_news_url": m_rec["google_news_url"] or e_rec["google_news_url"],
                "resolved_url": best_url,
                "extracted_text": best_text,
                "first_seen_at": best_timestamp_min(m_rec["first_seen_at"], e_rec["first_seen_at"]),
                "last_seen_at": best_timestamp_max(m_rec["last_seen_at"], e_rec["last_seen_at"])
            }
        else:
            main_only_count += 1
            merged_record = m_rec

        merged_records.append(merged_record)

    # 2. Add Elena-only records
    for norm, e_rec in elena_dict.items():
        if norm not in main_dict:
            elena_only_count += 1
            merged_records.append({
                "id": None,  # Will be assigned next autoincrement ID
                "title": e_rec["title"],
                "title_normalized": norm,
                "description": e_rec["description"],
                "theme": e_rec["theme"],
                "language": e_rec["language"],
                "published_date": e_rec["published_date"],
                "google_news_url": e_rec["google_news_url"],
                "resolved_url": e_rec["resolved_url"],
                "extracted_text": e_rec["extracted_text"],
                "first_seen_at": e_rec["first_seen_at"],
                "last_seen_at": e_rec["last_seen_at"]
            })

    print(f"\n🔄 Merge Analysis:")
    print(f"   Articles in both databases: {overlap_count:,}")
    print(f"   Articles unique to Main   : {main_only_count:,}")
    print(f"   Articles unique to Elena  : {elena_only_count:,}")
    print(f"   Total Unique in Merged    : {len(merged_records):,}")
    print(f"   Overlapping texts upgraded from Elena: {text_upgraded_from_elena:,}")
    print(f"   Overlapping URLs upgraded from Elena : {url_upgraded_from_elena:,}")

    if dry_run:
        print("\n[DRY RUN] No changes written to disk.")
        return

    # Create backups before writing
    main_bak, elena_bak = create_backups(main_db, elena_db)

    # Write to temporary database
    tmp_merged_db = "news_database_merged.db.tmp"
    if os.path.exists(tmp_merged_db):
        os.remove(tmp_merged_db)

    print(f"\n✍️ Writing merged records to temporary database: {tmp_merged_db}...")
    conn_out = sqlite3.connect(tmp_merged_db)
    cur_out = conn_out.cursor()

    cur_out.execute("""
    CREATE TABLE historical_articles (
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

    insert_sql = """
    INSERT INTO historical_articles (
        id, title, title_normalized, description, theme, language,
        published_date, google_news_url, resolved_url, extracted_text,
        first_seen_at, last_seen_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for r in merged_records:
        cur_out.execute(insert_sql, (
            r["id"], r["title"], r["title_normalized"], r["description"],
            r["theme"], r["language"], r["published_date"], r["google_news_url"],
            r["resolved_url"], r["extracted_text"],
            r["first_seen_at"], r["last_seen_at"]
        ))

    print("⚡ Creating database indexes...")
    cur_out.execute("CREATE INDEX idx_title_norm ON historical_articles(title_normalized)")
    cur_out.execute("CREATE INDEX idx_resolved_url ON historical_articles(resolved_url)")
    conn_out.commit()

    # Integrity verification
    print("🔍 Performing SQLite integrity check...")
    integrity = cur_out.execute("PRAGMA integrity_check").fetchall()
    if integrity != [('ok',)]:
        conn_out.close()
        raise RuntimeError(f"Integrity check failed: {integrity}")

    # Verify counts
    merged_total = cur_out.execute("SELECT count(*) FROM historical_articles").fetchone()[0]
    merged_resolved = cur_out.execute("SELECT count(*) FROM historical_articles WHERE resolved_url IS NOT NULL AND resolved_url != '' AND resolved_url != 'None'").fetchone()[0]
    merged_extracted = cur_out.execute("SELECT count(*) FROM historical_articles WHERE extracted_text IS NOT NULL AND extracted_text != '' AND extracted_text != 'No URL provided' AND NOT extracted_text LIKE 'Failed:%'").fetchone()[0]
    conn_out.close()

    if merged_total != len(merged_records):
        raise ValueError(f"Count mismatch: expected {len(merged_records)}, got {merged_total}")

    print(f"\n✅ Verification Passed:")
    print(f"   Integrity: OK")
    print(f"   Total Articles: {merged_total:,}")
    print(f"   With Resolved URLs: {merged_resolved:,}")
    print(f"   With Extracted Text (valid): {merged_extracted:,}")

    # Copy to standalone merged file and atomically replace news_database.db
    shutil.copy2(tmp_merged_db, STANDALONE_MERGED_DB)
    print(f"💾 Saved standalone merged database copy to: {STANDALONE_MERGED_DB}")

    # Replace news_database.db atomically
    os.replace(tmp_merged_db, MERGED_OUTPUT_DB)
    print(f"🚀 Atomically replaced {MERGED_OUTPUT_DB} with merged database!")

    print("\n========================================================")
    print("🎉 DATABASE MERGE COMPLETED SUCCESSFULLY!")
    print("========================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge news_database.db and news_database_elena.db")
    parser.add_argument("--dry-run", action="store_true", help="Simulate merge without saving to disk")
    parser.add_argument("--main", default=MAIN_DB, help="Path to main database")
    parser.add_argument("--elena", default=ELENA_DB, help="Path to elena database")
    args = parser.parse_args()

    merge_databases(main_db=args.main, elena_db=args.elena, dry_run=args.dry_run)
