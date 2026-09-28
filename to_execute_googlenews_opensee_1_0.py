# -*- coding: utf-8 -*-
"""TO EXECUTE GoogleNews_opensee_1_0.py

Cleaned version for standard Linux environment.
"""

import gnews
import pandas as pd
from datetime import datetime, timedelta
import email.utils
import os
import argparse

# --- Added Argument Parsing ---
def get_args():
    parser = argparse.ArgumentParser(description='Google News scraper with dynamic seed selection.')
    parser.add_argument('--seeds', type=str, help='Name of the seeds file in clean_seeds/ (e.g., seeds_buyside_london.csv)')
    return parser.parse_args()

args = get_args()
seeds_dir = 'clean_seeds'
available_seeds = [f for f in os.listdir(seeds_dir) if f.endswith('.csv')]

if args.seeds:
    if args.seeds in available_seeds:
        selected_seeds = args.seeds
    else:
        print(f"Error: {args.seeds} not found in {seeds_dir}.")
        print(f"Available files: {', '.join(available_seeds)}")
        exit(1)
else:
    # Default behavior: pick the first one or ask (here we pick the first one from the user's previous hardcode as default if it exists)
    default_seeds = 'seeds_buyside_eu_uae.csv'
    if default_seeds in available_seeds:
        selected_seeds = default_seeds
        print(f"No seeds file specified. Using default: {selected_seeds}")
    else:
        selected_seeds = available_seeds[0]
        print(f"No seeds file specified. Using first available: {selected_seeds}")

csv_path = os.path.join(seeds_dir, selected_seeds)
df_seeds = pd.read_csv(csv_path, sep=',')

# Extract the search themes into a list
search_themes = df_seeds['Seeds'].to_list()

# Create a list to hold all the articles data
all_articles_data = []

# Define the date range for filtering articles
current_date = datetime.now()
#-------------------------------------------------------
# CHANGE ROLLING WINDOW HERE
#-------------------------------------------------------

sixty_days_ago = current_date - timedelta(days=60)

# Function to search and collect articles for a given language
def collect_articles(gnews_client, language):
    for search_term in search_themes:
        print(f"Searching for: {search_term} in {language}")

        try:
            # Perform the search with a maximum of 20 results
            news_results = gnews_client.get_news(search_term)

            for result in news_results:
                # Parse the published date
                published_date_tuple = email.utils.parsedate_tz(result['published date'])
                if published_date_tuple:
                    published_date = datetime.fromtimestamp(email.utils.mktime_tz(published_date_tuple))

                    # Filter the news from the last 60 days
                    if published_date >= sixty_days_ago:
                        all_articles_data.append({
                            "Theme": search_term,
                            "Title": result['title'],
                            "Date": published_date,
                            "Description": result['description'],
                            "URL": result['url'],
                            "Language": language
                        })
        except Exception as e:
            print(f"Error searching for {search_term}: {e}")

# Bypass gnews URL redirection checks (gives 25x speedup per seed)
import gnews.gnews
gnews.gnews.process_url = lambda item, exclude_websites, proxies=None: item.get('link')

# Initialize the GNews objects for English
gnews_client_en = gnews.GNews(language="en", max_results=20, period="60d")


# Collect articles in English
collect_articles(gnews_client_en, "English")

if not all_articles_data:
    print("No articles found.")
else:
    # Create a DataFrame from the collected articles data
    df = pd.DataFrame(all_articles_data)
    # --- Improvement: Remove duplicate articles based on 'Title' ---
    initial_article_count = len(df)
    df.drop_duplicates(subset=['Title'], keep='first', inplace=True)
    articles_after_deduplication = len(df)
    print(f"Removed {initial_article_count - articles_after_deduplication} duplicate articles based on title.")

    # Print the Title, URL, and Language of each article
    for index, row in df.iterrows():
        print(f"Title: {row['Title']}, URL: {row['URL']}, Language: {row['Language']}")

    # --- Updated Output Filename Logic ---
    timestamp = datetime.now().strftime("%y-%m-%d-%H")
    seeds_base_name = os.path.splitext(selected_seeds)[0]
    output_base_name = seeds_base_name.replace("seeds", "news")
    output_filename = f"{output_base_name}_{timestamp}.csv"
    
    df.to_csv(output_filename, index=False)
    print(f"News articles saved to {output_filename}")
