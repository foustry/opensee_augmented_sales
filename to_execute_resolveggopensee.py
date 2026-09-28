import os
import glob
import re
import pandas as pd
import requests
import time
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import brave_quota_manager
import news_database

# Config: Brave Search API
BRAVE_API_KEY = brave_quota_manager.get_brave_api_key()

def get_latest_csv():
    """Finds the latest CSV file starting with 'news_' that isn't already an output file."""
    all_csvs = glob.glob("news_*.csv")
    # Exclude files that contain suffixes indicating they are processed
    input_csvs = [f for f in all_csvs if "_resolved" not in f and "_fulltext" not in f]
    if not input_csvs:
        return None
    # Sort by modification time to find the newest
    return max(input_csvs, key=os.path.getmtime)

def get_seed_filename(input_csv):
    """Maps raw news CSV file back to seed CSV filename (e.g. news_buyside_london_... -> seeds_buyside_london.csv)."""
    if not input_csv:
        return "seeds_buyside_eu_uae.csv"
    base = os.path.basename(input_csv)
    cleaned = re.sub(r'_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.csv$', '.csv', base)
    if cleaned.startswith('news_'):
        return cleaned.replace('news_', 'seeds_')
    return cleaned

# --- Part 1: Brave Search Resolution with Database Caching ---

def brave_search(title, api_key=None, seed_filename=None):
    """Searches for a title via Brave Search Web API and returns the first link."""
    if not api_key:
        api_key = BRAVE_API_KEY or brave_quota_manager.get_brave_api_key()
    if not api_key:
        print("⚠️ Error: Brave Search API Key not found in brave_api_key.txt or BRAVE_API_KEY env var.")
        return None

    can_call, reason = brave_quota_manager.can_make_call(seed_filename)
    if not can_call:
        print(f"⚠️ Quota limit reached ({reason}) — skipping resolution")
        return None

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    }
    params = {
        "q": title,
        "count": 1
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            brave_quota_manager.record_call(seed_filename, 1)
            data = response.json()
            results = data.get("web", {}).get("results", [])
            if results:
                return results[0].get("url")
    except Exception as e:
        print(f"Error searching for {title}: {e}")
    return None

def resolve_urls(df, seed_filename=None):
    """Checks database cache first, then resolves remaining news titles via Brave Search."""
    # 1. Check local SQLite historical database cache
    df, cached_urls, cached_texts = news_database.bulk_fill_from_cache(df)
    total = len(df)
    print(f"\n========================================================")
    print(f"🔍 Starting URL Resolution ({total} articles total)")
    print(f"💾 Database Cache Hit : {cached_urls} resolved URLs found in DB (0 API calls)")
    print(f"📄 Full-Text Cache Hit : {cached_texts} articles already have full text in DB")
    print(f"🌐 Remaining to Resolve: {total - cached_urls} articles via Brave Search")
    print(f"========================================================")

    for idx, row in df.iterrows():
        title = row.get("Title")
        existing_url = df.at[idx, "Resolved_URL_via_GoogleSearch"]
        
        # Skip if already cached from database
        if existing_url and not pd.isna(existing_url) and existing_url not in ["None", "", "nan"]:
            print(f"⏩ ({idx+1}/{total}) [DB CACHE] {title[:60]}... ➔ {existing_url}")
            continue
            
        print(f"🔍 ({idx+1}/{total}) [BRAVE SEARCH] {title}")
        link = brave_search(title, BRAVE_API_KEY, seed_filename=seed_filename)
        df.at[idx, "Resolved_URL_via_GoogleSearch"] = link
        print(f"➡️  Link found: {link}")
        time.sleep(0.5)
    
    # Deduplication
    initial_count = len(df)
    df.drop_duplicates(subset=['Title'], keep='first', inplace=True)
    print(f"\n✅ Deduplication: Removed {initial_count - len(df)} duplicate titles.")
    return df

# --- Part 2: Playwright Extraction ---

async def extract_article_text_with_playwright(url, browser_type="chromium"):
    """Uses Playwright to render the page and extract text."""
    try:
        async with async_playwright() as p:
            browser = await getattr(p, browser_type).launch(headless=True)
            page = await browser.new_page()
            # Wait for content to load
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector('body', timeout=10000)
            content = await page.content()
            await browser.close()

            soup = BeautifulSoup(content, "html.parser")
            # Remove noise
            for tag in soup(["script", "style", "header", "footer", "nav", "aside", "form", "img", "svg"]):
                tag.decompose()

            # Heuristic for main content
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 40)

            if text:
                first_line = text.splitlines()[0] if text else "No first line"
                return "SUCCESS", text, first_line
            else:
                return "FAILED", "No readable text found", None
    except Exception as e:
        return "ERROR", str(e), None

async def process_articles(df, checkpoint_file=None):
    """Processes each resolved URL to extract full article text."""
    if "Extracted_Article_Text" not in df.columns:
        df["Extracted_Article_Text"] = None

    total = len(df)
    
    # Find unprocessed rows (where Extracted_Article_Text is null/NaN or empty)
    unprocessed_indices = df[df["Extracted_Article_Text"].isna() | (df["Extracted_Article_Text"] == "")].index.tolist()
    processed_count = total - len(unprocessed_indices)

    print(f"\n📄 Starting/Resuming text extraction for {total} articles...")
    print(f"Already processed: {processed_count}")
    print(f"Remaining to process: {len(unprocessed_indices)}")

    success_count = 0
    failed_count = 0
    save_interval = 5
    counter = 0

    for idx in unprocessed_indices:
        row = df.loc[idx]
        url = str(row.get("Resolved_URL_via_GoogleSearch", ""))
        print(f"\n🔎 ({idx+1}/{total}) Extracting from: {url}")

        if pd.isna(row.get("Resolved_URL_via_GoogleSearch")) or url in ["", "None", "nan"]:
            df.at[idx, "Extracted_Article_Text"] = "No URL provided"
            failed_count += 1
            print("    ➡️ Skipping (No URL)")
            counter += 1
            continue

        status, text, first_line = await extract_article_text_with_playwright(url)
        if status == "SUCCESS":
            df.at[idx, "Extracted_Article_Text"] = text
            success_count += 1
            print(f"    ✅ Success! First line: {first_line[:100]}...")
        else:
            df.at[idx, "Extracted_Article_Text"] = f"Failed: {status}. Reason: {text}. URL: {url}"
            failed_count += 1
            print(f"    ❌ Extraction failed: {status} - {text}")
        
        counter += 1
        if checkpoint_file and counter % save_interval == 0:
            df.to_csv(checkpoint_file, index=False)
            print(f"💾 Checkpoint saved to: {checkpoint_file}")
            
        await asyncio.sleep(1.5) # Polite delay

    print(f"\n--- Extraction Summary ---")
    print(f"Total processed in this session: {counter}")
    print(f"Successfully extracted: {success_count}")
    print(f"Failed: {failed_count}")
    return df

# --- Execution ---

async def main():
    input_file = get_latest_csv()
    if not input_file:
        print("❌ No suitable input CSV found in the current directory.")
        return

    seed_filename = get_seed_filename(input_file)
    brave_quota_manager.start_run(seed_filename)

    base_name = os.path.splitext(input_file)[0]
    resolved_file = f"{base_name}_resolved.csv"
    checkpoint_file = f"{base_name}_fulltext_checkpoint.csv"
    final_file = f"{base_name}_fulltext.csv"

    print(f"🚀 Processing latest file: {input_file} (seed context: {seed_filename})")
    
    # Load and Resolve (Skip resolution if resolved file already exists)
    if os.path.exists(resolved_file):
        print(f"🔄 Resolved URLs file already exists: {resolved_file}. Skipping resolution stage.")
        df = pd.read_csv(resolved_file)
    else:
        df = pd.read_csv(input_file)
        df = resolve_urls(df, seed_filename=seed_filename)
        df.to_csv(resolved_file, index=False)
        print(f"💾 Resolved URLs saved to: {resolved_file}")

    # Extract Text
    print(f"\n🚀 Starting full-text extraction...")
    if os.path.exists(checkpoint_file):
        print(f"🔄 Checkpoint file found: {checkpoint_file}. Resuming text extraction...")
        df = pd.read_csv(checkpoint_file)

    try:
        df = await process_articles(df, checkpoint_file=checkpoint_file)
    except Exception as e:
        print(f"\n❌ Extraction interrupted due to error: {e}")
        df.to_csv(checkpoint_file, index=False)
        print(f"💾 Checkpoint saved to: {checkpoint_file}")
        raise e

    df.to_csv(final_file, index=False)
    print(f"💾 Final results saved to: {final_file}")
    
    # Save newly resolved & extracted articles to historical SQLite database
    try:
        saved = news_database.save_dataframe_to_db(df)
        print(f"💾 Synchronized {saved} articles with the historical database (news_database.db)")
    except Exception as e:
        print(f"⚠️ Warning: Could not save to database: {e}")

    # Clean up checkpoint
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)
        print(f"Cleaned up checkpoint file: {checkpoint_file}")
        
    print(f"\n🎉 Workflow complete! Output: {final_file}")
    brave_quota_manager.print_recap(seed_filename)

if __name__ == "__main__":
    asyncio.run(main())
