import os
import sys
import pandas as pd
import asyncio
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

RESOLVED_FILE = "news_buyside_eu_uae_26-06-30-21_resolved.csv"
CHECKPOINT_FILE = "news_buyside_eu_uae_26-06-30-21_fulltext_checkpoint.csv"
FINAL_FILE = "news_buyside_eu_uae_26-06-30-21_fulltext.csv"

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

async def main():
    if not os.path.exists(RESOLVED_FILE):
        print(f"❌ Input file {RESOLVED_FILE} not found!")
        sys.exit(1)

    print(f"Loading {RESOLVED_FILE}...")
    if os.path.exists(CHECKPOINT_FILE):
        print(f"🔄 Checkpoint file found: {CHECKPOINT_FILE}. Resuming extraction...")
        df = pd.read_csv(CHECKPOINT_FILE)
    else:
        print(f"🆕 No checkpoint file found. Starting fresh...")
        df = pd.read_csv(RESOLVED_FILE)
        if "Extracted_Article_Text" not in df.columns:
            df["Extracted_Article_Text"] = None

    # We want to process rows that don't have Extracted_Article_Text yet
    # We treat pd.isna or empty strings or strings starting with "Failed: " or "No URL provided" as unprocessed or failed?
    # Wait, if it previously failed, should we retry it or skip?
    # Usually we don't need to retry errors if we want to finish quickly, or we can retry them.
    # Let's consider a row unprocessed if Extracted_Article_Text is null/NaN or empty.
    # If there's an error message like "Failed: " or "ERROR: ", let's not retry it to save time, unless we want to.
    # Actually, let's treat anything that is NaN/None/empty as unprocessed.
    
    total = len(df)
    unprocessed_indices = df[df["Extracted_Article_Text"].isna() | (df["Extracted_Article_Text"] == "")].index.tolist()
    
    processed_count = total - len(unprocessed_indices)
    print(f"Total articles: {total}")
    print(f"Already processed: {processed_count}")
    print(f"Remaining to process: {len(unprocessed_indices)}")

    if len(unprocessed_indices) == 0:
        print("🎉 All articles are already processed!")
        df.to_csv(FINAL_FILE, index=False)
        print(f"Saved final results to: {FINAL_FILE}")
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
            print("Removed checkpoint file.")
        return

    success_count = 0
    failed_count = 0
    save_interval = 5  # Save checkpoint every 5 successful/failed extractions
    counter = 0

    try:
        for idx in unprocessed_indices:
            row = df.loc[idx]
            url = str(row.get("Resolved_URL_via_GoogleSearch", ""))
            print(f"\n🔎 ({idx+1}/{total}) Extracting from: {url}")

            if pd.isna(row.get("Resolved_URL_via_GoogleSearch")) or url in ["", "None", "nan"]:
                df.at[idx, "Extracted_Article_Text"] = "No URL provided"
                failed_count += 1
                print("    ➡️ Skipping (No URL)")
                counter += 1
                if counter % save_interval == 0:
                    df.to_csv(CHECKPOINT_FILE, index=False)
                    print(f"💾 Checkpoint saved ({counter} items since last save)")
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
            if counter % save_interval == 0:
                df.to_csv(CHECKPOINT_FILE, index=False)
                print(f"💾 Checkpoint saved ({counter} items since last save)")

            await asyncio.sleep(1.5) # Polite delay

    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user. Saving checkpoint...")
        df.to_csv(CHECKPOINT_FILE, index=False)
        print("💾 Checkpoint saved. Run the script again to resume.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}. Saving checkpoint...")
        df.to_csv(CHECKPOINT_FILE, index=False)
        print("💾 Checkpoint saved.")
        sys.exit(1)

    # Save final results
    df.to_csv(FINAL_FILE, index=False)
    print(f"\n--- Extraction Summary ---")
    print(f"Total processed in this run: {counter}")
    print(f"Successfully extracted: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"💾 Final results saved to: {FINAL_FILE}")
    
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("Removed checkpoint file.")
    print(f"\n🎉 Workflow complete! Output: {FINAL_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
