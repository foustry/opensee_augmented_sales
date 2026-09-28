# -*- coding: utf-8 -*-
"""
Brave Search API Quota Manager & Usage Tracker
Manages monthly quota (10,000 max), per-file monthly quota (1,650 max),
and per-run file quota (330 max) across pipeline executions.
"""

import os
import json
from datetime import datetime

USAGE_FILE = "brave_api_usage.json"
KEY_FILE = "brave_api_key.txt"
MONTHLY_TOTAL_CAP = 10000
MONTHLY_PER_FILE_CAP = 1650
PER_RUN_FILE_CAP = 330

_run_calls = 0
_current_run_seed = "default"

def get_brave_api_key():
    """
    Loads the Brave Search API key.
    Checks in order:
    1. Environment variable BRAVE_API_KEY
    2. Local file brave_api_key.txt in current working directory, script directory, or ~/google_news/
    """
    env_key = os.environ.get("BRAVE_API_KEY", "").strip()
    if env_key:
        return env_key

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        KEY_FILE,
        os.path.join(script_dir, KEY_FILE),
        os.path.join(os.path.expanduser("~"), "google_news", KEY_FILE),
        os.path.join(os.path.expanduser("~"), "google_news", "pipeline_deployment_package", KEY_FILE),
        os.path.join(os.path.expanduser("~"), "google_news", "colleague_pipeline_pkg", KEY_FILE),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception:
                pass
    return ""

def get_current_month():
    return datetime.now().strftime("%Y-%m")

def load_usage():
    current_month = get_current_month()
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            if data.get("month") == current_month:
                return data
        except Exception:
            pass
    # Reset for a new month or missing file
    return {
        "month": current_month,
        "total_calls": 0,
        "monthly_total_cap": MONTHLY_TOTAL_CAP,
        "monthly_per_file_cap": MONTHLY_PER_FILE_CAP,
        "per_run_file_cap": PER_RUN_FILE_CAP,
        "file_calls": {},
        "last_updated": datetime.now().isoformat()
    }

def save_usage(data):
    data["last_updated"] = datetime.now().isoformat()
    with open(USAGE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def start_run(seed_filename):
    global _run_calls, _current_run_seed
    _run_calls = 0
    _current_run_seed = os.path.basename(seed_filename)

def can_make_call(seed_filename=None):
    global _run_calls, _current_run_seed
    seed_name = os.path.basename(seed_filename) if seed_filename else _current_run_seed
    usage = load_usage()
    
    # 1. Total monthly cap check
    if usage["total_calls"] >= MONTHLY_TOTAL_CAP:
        return False, f"Monthly total cap reached ({usage['total_calls']}/{MONTHLY_TOTAL_CAP})"
    
    # 2. Monthly per-file cap check
    file_total = usage["file_calls"].get(seed_name, 0)
    if file_total >= MONTHLY_PER_FILE_CAP:
        return False, f"Monthly cap for '{seed_name}' reached ({file_total}/{MONTHLY_PER_FILE_CAP})"
        
    # 3. Per-run per-file cap check
    if _run_calls >= PER_RUN_FILE_CAP:
        return False, f"Per-run cap for '{seed_name}' reached ({_run_calls}/{PER_RUN_FILE_CAP})"
        
    return True, "OK"

def record_call(seed_filename=None, count=1):
    global _run_calls, _current_run_seed
    seed_name = os.path.basename(seed_filename) if seed_filename else _current_run_seed
    usage = load_usage()
    
    usage["total_calls"] += count
    current_file_calls = usage["file_calls"].get(seed_name, 0)
    usage["file_calls"][seed_name] = current_file_calls + count
    _run_calls += count
    
    save_usage(usage)
    return usage["total_calls"]

def get_run_recap(seed_filename=None):
    global _run_calls, _current_run_seed
    seed_name = os.path.basename(seed_filename) if seed_filename else _current_run_seed
    usage = load_usage()
    
    file_total = usage["file_calls"].get(seed_name, 0)
    total_calls = usage["total_calls"]
    remaining_month = max(0, MONTHLY_TOTAL_CAP - total_calls)
    remaining_file = max(0, MONTHLY_PER_FILE_CAP - file_total)
    
    recap = (
        f"\n========================================================"
        f"\n📊 BRAVE SEARCH API USAGE RECAP"
        f"\n========================================================"
        f"\n  Current Run Seed File   : {seed_name}"
        f"\n  Calls Made This Run     : {_run_calls} / {PER_RUN_FILE_CAP} (Per-Run Cap)"
        f"\n  Seed File Monthly Total : {file_total} / {MONTHLY_PER_FILE_CAP} (Per-File Monthly Cap)"
        f"\n  All Seeds Monthly Total : {total_calls} / {MONTHLY_TOTAL_CAP} (Global Monthly Cap)"
        f"\n  Remaining Global Quota  : {remaining_month} calls left for {usage['month']}"
        f"\n========================================================\n"
    )
    return recap

def print_recap(seed_filename=None):
    recap = get_run_recap(seed_filename)
    print(recap)

if __name__ == "__main__":
    import sys
    seed = sys.argv[1] if len(sys.argv) > 1 else "seeds_buyside_eu_uae.csv"
    print_recap(seed)
