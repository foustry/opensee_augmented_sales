import sqlite3
import re
import json

db_paths = [
    '/home/francois_oustry/google_news/news_database.db',
    '/home/francois_oustry/google_news/news_database_merged.db',
    '/home/francois_oustry/google_news/news_database_elena.db'
]

# We want 2026 news mentioning family offices investing in hedge funds
# Let's inspect articles mentioning both family office and hedge fund
query = """
SELECT id, title, description, published_date, theme, google_news_url, resolved_url, extracted_text
FROM historical_articles
WHERE published_date LIKE '2026%'
"""

seen_titles = set()
all_articles = []

for db_path in db_paths:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)
    for row in cursor.fetchall():
        t_norm = (row['title'] or '').strip().lower()
        if t_norm not in seen_titles:
            seen_titles.add(t_norm)
            all_articles.append(dict(row))
    conn.close()

print(f"Total unique 2026 articles across dbs: {len(all_articles)}")

# Search for family office(s) and hedge fund(s)
fo_pattern = re.compile(r'\bfamily\s+offices?\b', re.IGNORECASE)
hf_pattern = re.compile(r'\bhedge\s+funds?\b', re.IGNORECASE)

fo_hf_both = []
for art in all_articles:
    title = art['title'] or ''
    desc = art['description'] or ''
    text = art['extracted_text'] or ''
    full = f"{title} \n {desc} \n {text}"
    
    has_fo = bool(fo_pattern.search(full))
    has_hf = bool(hf_pattern.search(full))
    
    if has_fo and has_hf:
        fo_hf_both.append(art)

print(f"Articles mentioning both 'family office(s)' and 'hedge fund(s)': {len(fo_hf_both)}")

# Let's inspect what these articles are about
for i, art in enumerate(fo_hf_both):
    print(f"\n--- [{i+1}] {art['published_date']} | {art['title']} ---")
    print(f"URL: {art['resolved_url'] or art['google_news_url']}")
    desc = art['description'] or ''
    print(f"Desc: {desc[:200]}")
    # find snippets around family office and hedge fund
    full = f"{art['title']}\n{desc}\n{art['extracted_text'] or ''}"
    # find occurrences of family office
    for m in fo_pattern.finditer(full):
        start = max(0, m.start() - 100)
        end = min(len(full), m.end() + 100)
        snippet = full[start:end].replace('\n', ' ')
        print(f"   [FO Snippet]: ...{snippet}...")
