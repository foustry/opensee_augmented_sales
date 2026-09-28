import json
import re

with open('/home/francois_oustry/.gemini/antigravity-cli/brain/87846c4e-9dff-4960-afcf-383b17aa9034/scratch/detailed_fo_hf.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Loaded {len(data)} articles")

# We want articles mentioning family offices investing in hedge funds.
# Let's inspect paragraphs with BOTH or examine relationships.

candidates = []
for item in data:
    both_paras = [p[1] for p in item['relevant_paragraphs'] if p[0] == 'BOTH']
    all_paras = [p[1] for p in item['relevant_paragraphs']]
    
    full_text = " \n ".join(all_paras)
    
    # Check if any BOTH para contains investment keywords
    invest_words = re.compile(r'\b(invest|invests|investing|investment|investor|investors|allocate|allocating|allocation|allocations|allocator|allocators|backing|back|backs|backed|co-invest|co-investing|commit|committing|commitment|commitments|exposure|pour|poured|pouring|deploy|deploying|deployed|fund|funds)\b', re.IGNORECASE)
    
    has_both = len(both_paras) > 0
    has_invest = bool(invest_words.search(full_text))
    
    candidates.append({
        "index": item["index"],
        "id": item["id"],
        "title": item["title"],
        "date": item["date"],
        "url": item["url"],
        "num_both_paras": len(both_paras),
        "both_paras": both_paras,
        "all_relevant_count": len(all_paras),
        "full_snippet": full_text[:1000]
    })

print(f"Total articles with BOTH in same paragraph: {sum(1 for c in candidates if c['num_both_paras'] > 0)}")

for c in candidates:
    if c['num_both_paras'] > 0:
        print(f"\n==========================================")
        print(f"[{c['index']}] ID:{c['id']} | {c['date']} | {c['title']}")
        print(f"URL: {c['url']}")
        for bp in c['both_paras']:
            print(f"  -> {bp}")
