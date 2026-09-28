import sqlite3
import re

db_path = '/home/francois_oustry/google_news/news_database.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check article 56 (ID: 2420 or search by title)
cursor.execute("SELECT id, title, published_date, resolved_url, extracted_text FROM historical_articles WHERE title LIKE '%Hedge Fund Launches Are Picking Up%'")
row = cursor.fetchone()
if row:
    print("=== ARTICLE 56 ===")
    print(f"Title: {row['title']}")
    print(f"Date: {row['published_date']}")
    print(f"URL: {row['resolved_url']}")
    print(f"Text snippet:\n{row['extracted_text'][:2500]}\n")

# Check if there are other articles with SFO or MFO or "family wealth" and "hedge fund"
cursor.execute("""
SELECT id, title, published_date, resolved_url, description, extracted_text
FROM historical_articles
WHERE published_date LIKE '2026%'
AND (
    extracted_text LIKE '%single family office%' OR
    extracted_text LIKE '%single-family office%' OR
    extracted_text LIKE '%multi family office%' OR
    extracted_text LIKE '%multi-family office%' OR
    extracted_text LIKE '%family wealth%' OR
    extracted_text LIKE '%private wealth%'
)
AND (
    extracted_text LIKE '%hedge fund%' OR
    extracted_text LIKE '%hedge funds%'
)
""")
rows = cursor.fetchall()
print(f"Found {len(rows)} articles matching extended FO/wealth terms and hedge funds")

# Filter those not already in our 67 (or check which ones discuss investing in hedge funds)
for r in rows:
    txt = f"{r['title']} {r['description'] or ''} {r['extracted_text'] or ''}"
    # check if 'family' appears
    if not re.search(r'family\s+offices?', txt, re.I):
        # This is a new match!
        print(f"\n[NEW MATCH NOT IN PREVIOUS 67]: ID {r['id']} | {r['published_date']} | {r['title']}")
        print(f"URL: {r['resolved_url']}")
        # print snippet
        for m in re.finditer(r'(?:SFO|MFO|family wealth|private wealth)', txt, re.I):
            st = max(0, m.start() - 100)
            en = min(len(txt), m.end() + 100)
            print(f"   Snippet: ...{txt[st:en].replace(chr(10), ' ')}...")
            break

conn.close()
