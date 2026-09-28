#!/usr/bin/env python3
"""
Risk.net Article & Feed Extractor Tool
Extracts articles, entities, and metadata from Risk.net canonical taxonomy RSS feeds and desks.

Supports:
1. Single-section extraction (people, ai, market-risk, fx, model-risk, etc.)
2. Multi-category scraping (--categories people,ai,market-risk,fx,model-risk)
3. Reading from local XML/JSON datasets (--input <file>)
4. Logging scraped articles & discrete people appointments to SQLite database (--log-db)
5. Exporting to JSON (--json / --save-json) and Markdown reports (--save-md)
"""

import sys
import os
import argparse
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from bs4 import BeautifulSoup

# Canonical mapping of Risk.net sections to their Drupal taxonomy term IDs
TAXONOMY_MAP = {
    'people': '262371',
    'ai': '262941',
    'artificial-intelligence': '262941',
    'market-risk': '255841',
    'operational-risk': '257361',
    'clearing': '249391',
    'repo': '258751',
    'model-risk': '256261',
    'foreign-exchange': '252606',
    'fx': '252606',
    'liquidity': '255356',
    'us-treasuries': '272400',
    'banking-papers': '262696',
    'investments-papers': '262466'
}

DEFAULT_CATEGORIES = ['people', 'ai', 'market-risk', 'fx', 'model-risk']

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(SCRIPT_DIR, 'top_articles_by_category.json')
DEFAULT_DB = os.path.join(os.path.dirname(SCRIPT_DIR), 'news_database.db') if os.path.basename(SCRIPT_DIR) == 'tools' else os.path.join(SCRIPT_DIR, 'news_database.db')

def get_feed_url(section_or_term_id):
    """Resolve section name or numeric term ID to the canonical feed URL."""
    cleaned = section_or_term_id.lower().strip()
    term_id = TAXONOMY_MAP.get(cleaned, section_or_term_id.strip())
    return f"https://www.risk.net/taxonomy/term/{term_id}/feed"

def fetch_feed_xml(url):
    """Fetch raw XML from the feed endpoint, detecting bot challenges."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        raise RuntimeError(f"HTTP request failed: {e}")

    if '<title>Client Challenge</title>' in content or '_fs-ch-' in content:
        raise PermissionError(
            "Risk.net F5/Fastly Bot Protection (Client Challenge) was triggered.\n"
            "Tip: In the Antigravity agent environment, use 'read_url_content' on the canonical feed,\n"
            f"or run with pre-cached datasets (--input <file>)."
        )

    return content

def parse_feed(xml_text):
    """Parse RSS items, deduplicate, and extract entities from descriptions."""
    xml_start = xml_text.find('<?xml')
    if xml_start == -1:
        if '<title>Client Challenge</title>' in xml_text or '_fs-ch-' in xml_text:
            raise PermissionError("Input contains an F5 Bot Challenge HTML page instead of RSS XML.")
        raise ValueError("No valid '<?xml' declaration found in content.")

    xml_text = xml_text[xml_start:]
    root = ET.fromstring(xml_text)
    channel = root.find('channel')
    if channel is None:
        return []

    items = []
    seen_links = set()

    for it in channel.findall('item'):
        title = it.find('title').text if it.find('title') is not None else ''
        link = it.find('link').text if it.find('link') is not None else ''
        pub_date = it.find('pubDate').text if it.find('pubDate') is not None else ''
        desc = it.find('description').text if it.find('description') is not None else ''

        if not link or link in seen_links:
            continue
        seen_links.add(link)

        # Parse embedded entities and image from HTML description
        soup = BeautifulSoup(desc, 'html.parser')
        orgs = [a.get_text().strip() for a in soup.find_all('a', href=re.compile(r'/organisations/'))]
        img_tag = soup.find('img')
        img_url = img_tag.get('src', '') if img_tag else ''

        clean_desc = re.sub(r'<[^>]+>', ' ', desc).strip()
        clean_desc = re.sub(r'\s+', ' ', clean_desc)
        clean_desc = re.sub(r'(Off\s*){2,}.*$', '', clean_desc).strip()

        author_match = re.search(r'([a-zA-Z0-9_.+-]+@(?:info|risk)[a-zA-Z0-9_.-]*)', desc)
        author = author_match.group(1) if author_match else ''

        items.append({
            'title': title,
            'url': link,
            'published_date': pub_date,
            'summary': clean_desc,
            'author_handle': author,
            'organisations': orgs,
            'image_url': img_url
        })

    return items

def load_cached_top_articles():
    """Load the curated top articles dataset if available."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def scrape_categories(categories, top_n=1):
    """Retrieve top article(s) across multiple categories."""
    cached = load_cached_top_articles().get('categories', {})
    results = {}

    for cat in categories:
        cat_key = cat.lower().strip()
        cat_data = cached.get(cat_key)
        if cat_data:
            results[cat_key] = cat_data
        else:
            # Fallback to feed query
            feed_url = get_feed_url(cat_key)
            try:
                xml_text = fetch_feed_xml(feed_url)
                items = parse_feed(xml_text)
                if items:
                    top_item = items[0]
                    results[cat_key] = {
                        'category_name': cat_key.replace('-', ' ').title(),
                        'taxonomy_id': TAXONOMY_MAP.get(cat_key, 'unknown'),
                        'top_article': top_item
                    }
            except Exception as e:
                results[cat_key] = {
                    'category_name': cat_key.replace('-', ' ').title(),
                    'error': str(e)
                }

    return results

def log_articles_to_database(results, db_path=DEFAULT_DB):
    """
    Logs top articles into historical_articles in news_database.db.
    For the 'people' category, logs:
    1. The parent roundup article
    2. One separate entry per executive appointment / people move
    """
    try:
        # Import news_database dynamically
        sys.path.insert(0, os.path.dirname(os.path.abspath(db_path)))
        import news_database
        news_database.init_db(db_path)
    except Exception as e:
        sys.stderr.write(f"Error loading news_database module: {e}\n")
        return 0, 0

    logged_articles = 0
    logged_appointments = 0

    for cat_key, cat_val in results.items():
        if 'error' in cat_val:
            continue

        art = cat_val.get('top_article', {})
        if not art:
            continue

        title = art.get('title')
        url = art.get('url')
        date = art.get('published_date')
        summary = art.get('summary', '')
        theme = f"Risk.net {cat_val.get('category_name', cat_key.upper())}"
        orgs = art.get('organisations', [])
        orgs_str = f"Organisations: {', '.join(orgs)}\n\n" if orgs else ""
        extracted = f"{orgs_str}{summary}"

        # 1. Upsert parent article
        news_database.upsert_article(
            title=title,
            description=summary,
            theme=theme,
            language='en',
            published_date=date,
            google_news_url=url,
            resolved_url=url,
            extracted_text=extracted,
            db_path=db_path
        )
        logged_articles += 1

        # 2. For 'people', log each discrete appointment / move
        if cat_key == 'people':
            appointments = cat_val.get('appointments', [])
            for app in appointments:
                app_title = app.get('title')
                app_desc = app.get('summary')
                app_date = app.get('date', date)
                app_theme = "Executive Appointments & People Moves"
                
                # Detailed structured content for extracted_text
                details = [
                    f"Person: {app.get('person')}",
                    f"Position: {app.get('position')}",
                    f"Company: {app.get('company')}",
                    f"Previous Firm: {app.get('previous_company', 'N/A')}",
                    f"Sector: {app.get('sector', 'Banking')}",
                    f"Location: {app.get('location', 'Global')}",
                    f"Date: {app_date}",
                    f"Source: {url}",
                    "",
                    f"Summary: {app_desc}"
                ]
                app_extracted = "\n".join(details)

                news_database.upsert_article(
                    title=app_title,
                    description=app_desc,
                    theme=app_theme,
                    language='en',
                    published_date=app_date,
                    google_news_url=url,
                    resolved_url=url,
                    extracted_text=app_extracted,
                    db_path=db_path
                )
                logged_appointments += 1

    return logged_articles, logged_appointments

def format_markdown_report(results):
    """Format multi-category scrape results as GitHub-flavored Markdown."""
    lines = [
        "# Risk.net Top Articles by Category",
        "",
        "Overview of the latest top articles across key financial risk categories scraped from Risk.net.",
        "",
        "---",
        ""
    ]

    for cat_key, cat_val in results.items():
        name = cat_val.get('category_name', cat_key.upper())
        lines.append(f"## 📌 Desk: {name}")

        if 'error' in cat_val:
            lines.append(f"> ⚠️ **Fetch status:** {cat_val['error']}\n")
            continue

        art = cat_val.get('top_article', {})
        title = art.get('title', 'N/A')
        url = art.get('url', '#')
        date = art.get('published_date', 'N/A')
        authors = art.get('authors') or ([art.get('author_handle')] if art.get('author_handle') else [])
        authors_str = ", ".join(authors) if authors else 'Risk.net Editorial'
        orgs = art.get('organisations', [])
        summary = art.get('summary', '')

        lines.append(f"### [{title}]({url})")
        lines.append(f"- **Published Date:** {date}")
        lines.append(f"- **Authors / Desk:** {authors_str}")
        lines.append(f"- **Article Link:** [`{url}`]({url})")

        if orgs:
            lines.append(f"- **Tagged Entities:** {', '.join(orgs)}")

        lines.append(f"\n**Executive Summary:**\n{summary}\n")

        # Append individual appointments if present
        if cat_key == 'people' and cat_val.get('appointments'):
            lines.append("#### 👥 Tracked Executive Appointments & Leadership Moves:\n")
            lines.append("| Person | Position | Company | Previous Firm | Location |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for m in cat_val['appointments']:
                lines.append(f"| **{m['person']}** | {m['position']} | **{m['company']}** | {m.get('previous_company', '-')} | {m.get('location', '-')} |")
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Fetch, parse, and log Risk.net articles across single or multiple categories.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 fetch_risk_net.py --all-top --log-db
  python3 fetch_risk_net.py --categories people,ai,market-risk,fx,model-risk --log-db
  python3 fetch_risk_net.py --all-top --save-md risk_top_articles.md
  python3 fetch_risk_net.py --section people --top 1
  python3 fetch_risk_net.py --list-sections
"""
    )
    parser.add_argument('-s', '--section', help="Single section name (e.g. people, ai, market-risk) or numeric taxonomy term ID")
    parser.add_argument('-c', '--categories', help="Comma-separated list of categories (e.g. people,ai,market-risk,fx,model-risk)")
    parser.add_argument('--all-top', action='store_true', help="Scrape top articles for the 5 key desks: people, ai, market-risk, fx, model-risk")
    parser.add_argument('-i', '--input', help="Path to local XML file or '-' for stdin")
    parser.add_argument('-n', '--top', type=int, default=1, help="Number of articles to return per category (default: 1)")
    parser.add_argument('--json', action='store_true', help="Output results as JSON")
    parser.add_argument('--save-json', help="File path to save the structured JSON output")
    parser.add_argument('--save-md', help="File path to save a Markdown report")
    parser.add_argument('--log-db', action='store_true', help="Log scraped articles & people appointments directly into SQLite database")
    parser.add_argument('--db-path', default=DEFAULT_DB, help=f"Path to SQLite database (default: {DEFAULT_DB})")
    parser.add_argument('--list-sections', action='store_true', help="List all pre-mapped Risk.net taxonomy sections")

    args = parser.parse_args()

    if args.list_sections:
        print("\nPre-configured Risk.net Sections & Drupal Taxonomy IDs:")
        print(f"{'Section':<25} | {'Term ID':<10} | Canonical Feed URL")
        print("-" * 75)
        for name, tid in sorted(TAXONOMY_MAP.items()):
            url = f"https://www.risk.net/taxonomy/term/{tid}/feed"
            print(f"{name:<25} | {tid:<10} | {url}")
        print()
        return

    # Handle multi-category scraping mode
    if args.all_top or args.categories:
        cats = DEFAULT_CATEGORIES if args.all_top else [c.strip() for c in args.categories.split(',') if c.strip()]
        results = scrape_categories(cats, top_n=args.top)

        if args.save_json:
            with open(args.save_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            print(f"💾 Saved JSON report to: {args.save_json}")

        if args.save_md:
            md_content = format_markdown_report(results)
            with open(args.save_md, 'w', encoding='utf-8') as f:
                f.write(md_content)
            print(f"📄 Saved Markdown report to: {args.save_md}")

        # Database logging
        if args.log_db:
            n_art, n_app = log_articles_to_database(results, db_path=args.db_path)
            print(f"🗄️  Logged {n_art} category articles and {n_app} discrete appointments to database: {args.db_path}")

        if args.json:
            print(json.dumps(results, indent=2))
            return

        print("\n=======================================================")
        print(f"Risk.net Multi-Category Top Articles ({len(cats)} Desks)")
        print("=======================================================\n")

        for cat_key, cat_val in results.items():
            name = cat_val.get('category_name', cat_key.upper())
            print(f"📂 [{name.upper()}]")
            if 'error' in cat_val:
                print(f"   ⚠️ Error: {cat_val['error']}\n")
                continue
            art = cat_val.get('top_article', {})
            print(f"   📰 Title:    {art.get('title')}")
            print(f"   📅 Date:     {art.get('published_date')}")
            print(f"   🔗 URL:      {art.get('url')}")
            authors = art.get('authors') or ([art.get('author_handle')] if art.get('author_handle') else [])
            if authors:
                print(f"   ✍️ Authors:  {', '.join(authors)}")
            if art.get('organisations'):
                orgs_str = ", ".join(art['organisations'][:6])
                if len(art['organisations']) > 6:
                    orgs_str += f" (+{len(art['organisations']) - 6} more)"
                print(f"   🏢 Entities: {orgs_str}")
            print(f"   📝 Summary:  {art.get('summary', '')[:160]}...\n")

            if cat_key == 'people' and cat_val.get('appointments'):
                print(f"   👥 Tracked Executive Appointments ({len(cat_val['appointments'])} moves):")
                for app in cat_val['appointments']:
                    print(f"      • {app['person']} ➔ {app['position']} at {app['company']}")
                print()

        return

    # Single-section mode (default section: people if no input)
    section = args.section or 'people'
    if args.input:
        if args.input == '-':
            xml_content = sys.stdin.read()
        else:
            if not os.path.exists(args.input):
                sys.stderr.write(f"Error: input file '{args.input}' not found.\n")
                sys.exit(1)
            with open(args.input, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        source_label = f"Local file: {args.input}"
    else:
        feed_url = get_feed_url(section)
        source_label = f"Feed URL: {feed_url}"
        try:
            xml_content = fetch_feed_xml(feed_url)
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.exit(1)

    try:
        items = parse_feed(xml_content)
    except Exception as e:
        sys.stderr.write(f"Error parsing feed: {e}\n")
        sys.exit(1)

    selected_items = items[:args.top]

    if args.log_db:
        # Wrap in results structure and log
        single_res = {
            section: {
                'category_name': section.replace('-', ' ').title(),
                'taxonomy_id': TAXONOMY_MAP.get(section, 'unknown'),
                'top_article': selected_items[0] if selected_items else {}
            }
        }
        n_art, n_app = log_articles_to_database(single_res, db_path=args.db_path)
        print(f"🗄️  Logged {n_art} articles to database: {args.db_path}")

    if args.json:
        print(json.dumps(selected_items, indent=2))
        return

    print(f"\n=======================================================")
    print(f"Risk.net Extractor: [{section.upper()}]")
    print(f"Source: {source_label}")
    print(f"Retrieved {len(items)} unique articles (showing top {len(selected_items)})")
    print(f"=======================================================\n")

    for i, item in enumerate(selected_items, 1):
        print(f"[{i}] {item['title']}")
        print(f"    📅 Date:     {item['published_date']}")
        print(f"    🔗 URL:      {item['url']}")
        if item.get('author_handle'):
            print(f"    ✍️ Author:   {item['author_handle']}")
        if item.get('organisations'):
            orgs_str = ", ".join(item['organisations'][:8])
            if len(item['organisations']) > 8:
                orgs_str += f" (+{len(item['organisations']) - 8} more)"
            print(f"    🏢 Entities: {orgs_str}")
        print(f"    📝 Summary:  {item['summary'][:160]}...\n")

if __name__ == '__main__':
    main()
