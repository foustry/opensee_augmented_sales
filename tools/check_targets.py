import json

with open('/home/francois_oustry/.gemini/antigravity-cli/brain/87846c4e-9dff-4960-afcf-383b17aa9034/scratch/detailed_fo_hf.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# The candidates that could be relevant:
# 4, 6, 16, 18, 22, 27, 32, 33, 39, 46, 47, 56, 57, 59, 62, 64, 65

targets = [4, 6, 16, 18, 22, 27, 32, 33, 39, 46, 47, 56, 57, 59, 62, 64, 65]

for item in data:
    if item['index'] in targets:
        print(f"\n=================================================================")
        print(f"INDEX: {item['index']} | ID: {item['id']}")
        print(f"TITLE: {item['title']}")
        print(f"DATE:  {item['date']}")
        print(f"URL:   {item['url']}")
        print(f"-----------------------------------------------------------------")
        for tag, p in item['relevant_paragraphs']:
            print(f"[{tag}] {p}\n")
