# Google News & Playwright Article Extraction Pipeline

A robust, automated pipeline designed for Google Cloud Shell (or any Linux environment) that scrapes Google News articles based on search seeds, resolves their original URLs, and extracts full article text using headless browser automation.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Environment Setup](#3-environment-setup)
4. [Installation & Permissions](#4-installation--permissions)
5. [Connection-Triggered Automation](#5-connection-triggered-automation)
6. [Manual Execution & Monitoring](#6-manual-execution--monitoring)
7. [Data Pipeline Workflow](#7-data-pipeline-workflow)

---

## 1. Project Overview

The pipeline executes in two sequential stages:
1. **Scraping Stage**: Searches Google News for articles matching a set of search keywords (seeds) from a selected seed file, filtering for articles published in the last 60 days.
2. **Resolution & Extraction Stage**: Uses the Google Custom Search API to resolve original publisher URLs and Playwright (headless Chromium) to render and extract clean article body text (removing headers, footers, scripts, and navigation elements).

The system alternates through **six different seed files** day-by-day in a stateless, round-robin cycle.

---

## 2. Directory Structure

```text
/home/francois_oustry/google_news/
├── clean_seeds/                       # Directory containing seed CSV files
│   ├── seeds_buyside_eu_uae.csv
│   ├── seeds_buyside_london.csv
│   ├── seeds_buyside_us.csv
│   ├── seeds_sellside_eu.csv
│   ├── seeds_sellside_london.csv
│   └── seeds_sellside_us.csv
├── to_execute_googlenews_opensee_1_0.py # Stage 1: Google News scraper script
├── to_execute_resolveggopensee.py      # Stage 2: URL resolver & text extractor script
├── run_pipeline.sh                     # Master pipeline automation script (shell)
├── pipeline_user_guide.md              # Detailed pipeline workflow and strategy guide
├── .last_run_date                      # State file tracking the last run date (YYYY-MM-DD)
├── pipeline_run.log                    # Master execution log file (output redirected here)
└── README.md                           # This documentation guide
```

---

## 3. Environment Setup

The pipeline requires **Python 3.8+** and several external dependencies.

### Step 3.1: Install Python Dependencies
Run the following command to install all required libraries:
```bash
pip3 install gnews pandas playwright beautifulsoup4 requests
```

### Step 3.2: Install Playwright Browser Binaries
Playwright requires browser binaries to run headless browser instances. Install the Chromium binaries by running:
```bash
playwright install chromium
```
*(If running on a bare Linux server instead of Cloud Shell, you may also need to run `playwright install-deps` to install system-level library dependencies).*

---

## 4. Installation & Permissions

### Step 4.1: Make the Master Script Executable
To allow the master shell script to run, grant it execution permissions:
```bash
chmod +x /home/francois_oustry/google_news/run_pipeline.sh
```

---

## 5. Connection-Triggered Automation

Because Google Cloud Shell VMs shut down automatically after periods of inactivity, a standard crontab is unreliable. Instead, this pipeline uses a **daily login trigger** appended to your shell configuration.

### How It Works
Every time you connect to your Cloud Shell terminal, the shell reads your `~/.bashrc` file. The trigger block performs the following steps:
1. Checks if `run_pipeline.sh` exists.
2. Compares today's date with the date in `.last_run_date`.
3. Checks if a pipeline is **already running** in the background using `pgrep`.
4. If a run is needed and not already active:
   * It prints a notification banner.
   * It spawns `run_pipeline.sh` in the background (`&`).
5. **Note:** Unlike previous versions, the trigger does **not** update the `.last_run_date` immediately. Completion is only marked by the script itself upon successful extraction or if it verifies that today's output already exists.

---

## 6. Manual Execution & Monitoring

### Running the Master Script Manually
You can trigger the entire pipeline manually at any time. It includes a **locking mechanism** (`flock`) that prevents multiple instances from running simultaneously.
```bash
/home/francois_oustry/google_news/run_pipeline.sh
```
Manual execution supports **multiple runs per day** for different successive seeds, as long as the previous run completed properly.

---

## 7. Data Pipeline Workflow

Below is the step-by-step description of the data flow:

1. **Pre-run & Interruption Checks**:
   * **Locking**: The script checks `/tmp/google_news_pipeline.lock`. If locked, it exits to prevent concurrent runs.
   * **Interrupted Run Detection**: The script checks if any raw GNews file `news_*_[timestamp].csv` exists without its matching `*_fulltext.csv` file. If found, it marks the run as interrupted, skips Stage 1 (news scraping), and targets the interrupted seed for resumption.
2. **Seed Selection**:
   * If there is no interrupted run, the script identifies the last completed seed via the latest `*_fulltext.csv` file and selects the next seed in rotation sequence (round-robin list of 6 seeds).
   * **Output Verification**: Checks if a completed `_fulltext.csv` file for the selected seed and today's date already exists. If found, it skips the run to prevent duplicate processing.
3. **Scraping Stage (`to_execute_googlenews_opensee_1_0.py`)**:
   * (Skipped if resuming an interrupted run)
   * Queries Google News based on the selected seed keywords.
   * Saves raw articles as `news_[seed_base]_[yy-mm-dd-HH].csv`.
4. **Resolution & Extraction Stage (`to_execute_resolveggopensee.py`)**:
   * **Google Search Bypass**: If the intermediate `*_resolved.csv` file already exists from a previous run, the script skips the Google Search API URL resolution phase to conserve API quota.
   * **Text Extraction**: Runs headless Playwright (Chromium) to extract body paragraphs.
   * **Checkpointing**: Saves extraction progress to `*_fulltext_checkpoint.csv` every 5 articles, allowing resumption of text extraction exactly from where it was interrupted.
   * Saves final output to `news_[seed_base]_[yy-mm-dd-HH]_fulltext.csv` and deletes the checkpoint file.
5. **Finalization**:
   * Updates `.last_run_date` to prevent further automatic background triggers today.

