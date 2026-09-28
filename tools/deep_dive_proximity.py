import sqlite3
import re
import json

db_path = '/home/francois_oustry/google_news/news_database.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. First, let's inspect the specific text around FO and HF for candidates 4, 6, 16, 18, 20, 27, 28, 31, 32, 45, 51, 56, 59, 60, 64
interesting_indices = [4, 6, 16, 18, 20, 27, 28, 31, 32, 45, 51, 56, 59, 60, 64]

with open('/home/francois_oustry/.gemini/antigravity-cli/brain/87846c4e-9dff-4960-afcf-383b17aa9034/scratch/detailed_fo_hf.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== DEEP DIVE INTO CANDIDATES ===")
for item in data:
    idx = item['index']
    # Let's inspect all items where FO and HF are mentioned in the text
    full_text = f"{item['title']}\n{item['url']}\n"
    # Find all sentences or windows where family office appears
    t = f"{item['title']}\n{item['relevant_paragraphs']}"
    # Let's see if there's any mention of investing, allocating, backing, commitments between FO and HF
    # Let's search in all paragraphs
    all_p = [p[1] for p in item['relevant_paragraphs']]
    combined = "\n".join(all_p)
    
    # Check if this article discusses family office investing in hedge funds
    # or hedge fund investors including family offices
    keywords = [
        r'family\s+office.*?(?:invest|allocat|back|commit|exposure|lp|stake|client|fund)',
        r'(?:invest|allocat|back|commit|exposure|lp|stake|client|fund).*?family\s+office',
        r'hedge\s+fund.*?(?:invest|allocat|back|commit|exposure|lp|stake|client|fund)',
    ]
    
    # Let's print excerpts for each of the 67 articles that have any investing context
    fo_matches = list(re.finditer(r'family\s+offices?', combined, re.I))
    hf_matches = list(re.finditer(r'hedge\s+funds?', combined, re.I))
    
    # Check proximity: is there any place where FO and HF appear within 500 characters of each other?
    close_pairs = []
    for fo in fo_matches:
        for hf in hf_matches:
            dist = abs(fo.start() - hf.start())
            if dist < 500:
                start = max(0, min(fo.start(), hf.start()) - 100)
                end = min(len(combined), max(fo.end(), hf.end()) + 100)
                close_pairs.append((dist, combined[start:end].replace('\n', ' ')))
    
    if close_pairs:
        close_pairs.sort(key=lambda x: x[0])
        print(f"\n[{idx}] {item['date'][:10]} | {item['title']}")
        print(f"URL: {item['url']}")
        print(f"Closest match (distance {close_pairs[0][0]} chars):")
        print(f"   \"{close_pairs[0][1]}\"")
