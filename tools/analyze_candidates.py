import sqlite3
import re
import json

db_path = '/home/francois_oustry/google_news/news_database.db'

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
SELECT id, title, description, published_date, theme, google_news_url, resolved_url, extracted_text
FROM historical_articles
WHERE published_date LIKE '2026%'
""")

fo_pattern = re.compile(r'\bfamily\s+offices?\b', re.IGNORECASE)
hf_pattern = re.compile(r'\bhedge\s+funds?\b', re.IGNORECASE)

matches = []
for row in cursor.fetchall():
    t = row['title'] or ''
    d = row['description'] or ''
    txt = row['extracted_text'] or ''
    full = f"{t}\n{d}\n{txt}"
    if fo_pattern.search(full) and hf_pattern.search(full):
        matches.append(dict(row))

conn.close()

print(f"Total matching both: {len(matches)}")

output_data = []

for i, m in enumerate(matches):
    full = f"{m['title']}\n{m['description'] or ''}\n{m['extracted_text'] or ''}"
    # Split into paragraphs or sentences
    paragraphs = full.split('\n')
    relevant_paras = []
    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        # if paragraph mentions both, or mentions either
        has_fo = bool(fo_pattern.search(p_clean))
        has_hf = bool(hf_pattern.search(p_clean))
        if has_fo and has_hf:
            relevant_paras.append(("BOTH", p_clean))
        elif has_fo:
            # check if hf is mentioned nearby or in context
            relevant_paras.append(("FO", p_clean))
        elif has_hf:
            relevant_paras.append(("HF", p_clean))

    output_data.append({
        "index": i + 1,
        "id": m["id"],
        "date": m["published_date"],
        "title": m["title"],
        "url": m["resolved_url"] or m["google_news_url"],
        "relevant_paragraphs": relevant_paras
    })

with open('/home/francois_oustry/.gemini/antigravity-cli/brain/87846c4e-9dff-4960-afcf-383b17aa9034/scratch/detailed_fo_hf.json', 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print("Saved detailed analysis to scratch/detailed_fo_hf.json")
