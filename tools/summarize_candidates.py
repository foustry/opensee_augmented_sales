import json
import re

with open('/home/francois_oustry/.gemini/antigravity-cli/brain/87846c4e-9dff-4960-afcf-383b17aa9034/scratch/detailed_fo_hf.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    idx = item['index']
    title = item['title']
    date = item['date']
    url = item['url']
    
    paras = item['relevant_paragraphs']
    # Let's see what is discussed
    both = [p[1] for p in paras if p[0] == 'BOTH']
    
    print(f"[{idx}] {date[:10]} | {title}")
    if both:
        for b in both:
            # print up to 300 chars around both
            print(f"   BOTH: {b[:300]}...")
    else:
        fo_paras = [p[1] for p in paras if p[0] == 'FO']
        hf_paras = [p[1] for p in paras if p[0] == 'HF']
        print(f"   SEPARATE: {len(fo_paras)} FO paras, {len(hf_paras)} HF paras")
        if fo_paras:
            print(f"   FO: {fo_paras[0][:150]}...")
        if hf_paras:
            print(f"   HF: {hf_paras[0][:150]}...")
