---
name: risk-net-extractor
description: Extract financial articles, executive appointments, and institution metadata from Risk.net using canonical Drupal taxonomy feeds.
---

# Risk.net Extractor Skill

## Overview

Risk.net uses Drupal 11 behind **Fastly** and **F5 / Shape Security** bot protection. Direct HTTP requests (`curl`, `urllib`, standard Python `requests`) and standard headless Playwright browsers typically trigger a JavaScript `Client Challenge` (`/_fs-ch-1T1wmsGaOgGaSxcX/`).

This skill documents and packages the bypass methodology:
1. **Canonical Taxonomy Feeds**: Risk.net exposes public RSS 2.0 feeds on its Drupal taxonomy terms (`https://www.risk.net/taxonomy/term/{term_id}/feed`).
2. **Metadata & Entity Extraction**: The RSS `<description>` tags contain fully rendered HTML that includes tagged organizations (`/organisations/{slug}`), author handles, image URLs, and publication timestamps without requiring secondary article page hits.
3. **Agent Ingestion Workflow**: When running in Antigravity, the `read_url_content` tool can fetch these feeds directly. The companion Python script [fetch_risk_net.py](file:///home/francois_oustry/google_news/tools/fetch_risk_net.py) parses the output into structured JSON, Markdown reports, or terminal summaries.
4. **Multi-Category Scraping**: Quickly scrape and aggregate the top article across multiple desks (`people`, `ai`, `market-risk`, `fx`, `model-risk`).

---

## Canonical Taxonomy Directory

| Desk / Topic | Taxonomy ID | Canonical Feed URL |
| :--- | :--- | :--- |
| **People / Appointments** | `262371` | `https://www.risk.net/taxonomy/term/262371/feed` |
| **Artificial Intelligence (AI)** | `262941` | `https://www.risk.net/taxonomy/term/262941/feed` |
| **Market Risk** | `255841` | `https://www.risk.net/taxonomy/term/255841/feed` |
| **Operational Risk** | `257361` | `https://www.risk.net/taxonomy/term/257361/feed` |
| **Clearing** | `249391` | `https://www.risk.net/taxonomy/term/249391/feed` |
| **Model Risk** | `256261` | `https://www.risk.net/taxonomy/term/256261/feed` |
| **Foreign Exchange (FX)** | `252606` | `https://www.risk.net/taxonomy/term/252606/feed` |
| **Repo** | `258751` | `https://www.risk.net/taxonomy/term/258751/feed` |
| **Liquidity Risk** | `255356` | `https://www.risk.net/taxonomy/term/255356/feed` |
| **US Treasuries** | `272400` | `https://www.risk.net/taxonomy/term/272400/feed` |
| **Banking Papers** | `262696` | `https://www.risk.net/taxonomy/term/262696/feed` |
| **Investments Papers** | `262466` | `https://www.risk.net/taxonomy/term/262466/feed` |

---

## Tool Usage & CLI Commands

The CLI tool is located at [tools/fetch_risk_net.py](file:///home/francois_oustry/google_news/tools/fetch_risk_net.py) (and accessible from the project root as [fetch_risk_net.py](file:///home/francois_oustry/google_news/fetch_risk_net.py)).

### 1. Multi-Category Top Article Scraping
```bash
# Scrape the top article for all 5 key categories (People, AI, Market Risk, FX, Model Risk)
python3 fetch_risk_net.py --all-top

# Export to a Markdown report
python3 fetch_risk_net.py --all-top --save-md risk_top_articles_by_category.md

# Export as JSON
python3 fetch_risk_net.py --all-top --save-json risk_top_articles.json

# Log top articles & discrete people appointments to SQLite database
python3 fetch_risk_net.py --all-top --log-db

# Select specific categories
python3 fetch_risk_net.py --categories people,market-risk,fx --log-db
```

### 2. Fetch Top Articles from a Single Section
```bash
# Get top 5 articles from People desk
python3 fetch_risk_net.py --section people --top 5

# Get top article from AI desk
python3 fetch_risk_net.py --section ai --top 1
```

### 3. Parse from a Saved XML / Feed Dump
```bash
python3 fetch_risk_net.py --input tools/sample_people_feed.xml --top 1
```

### 4. List All Pre-mapped Sections
```bash
python3 fetch_risk_net.py --list-sections
```

---

## Python API Integration

You can import `fetch_risk_net` directly into your Python scripts or pipeline runners:

```python
from tools.fetch_risk_net import scrape_categories, parse_feed, get_feed_url

# Scrape multiple categories at once:
results = scrape_categories(['people', 'ai', 'market-risk', 'fx', 'model-risk'])

for category, data in results.items():
    art = data['top_article']
    print(f"[{category}] {art['title']}")
    print(f"URL: {art['url']}")
    print(f"Entities: {art['organisations']}")
```
