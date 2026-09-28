#!/bin/bash
# run_pipeline.sh
# Master orchestrator script to run:
# 1. Google News, LinkedIn, and Playwright fulltext extraction pipeline (rotating daily across seeds).
# 2. Risk.net weekly multi-category scraping & people appointments pipeline (executed once every 7 days).

# --- Configuration & Paths ---
WORKSPACE_DIR="/home/francois_oustry/google_news"
LOG_FILE="$WORKSPACE_DIR/pipeline_run.log"
LAST_RUN_FILE="$WORKSPACE_DIR/.last_run_date"
LAST_RISK_RUN_FILE="$WORKSPACE_DIR/.last_risk_run_date"
LOCK_FILE="/tmp/google_news_pipeline.lock"
TODAY=$(date +%Y-%m-%d)

# --- Status Reporting Mode ---
show_status() {
  LOCK_HELD=false
  # Try to flock in a subshell without blocking or keeping it locked
  ( flock -n 9 ) 9>"$LOCK_FILE"
  if [ $? -ne 0 ]; then
    LOCK_HELD=true
  fi

  echo "========================================================"
  echo "📊 Google News & Risk.net Pipeline Status"
  echo "========================================================"

  if [ "$LOCK_HELD" = "true" ]; then
    echo "🟢 Pipeline: RUNNING"
    # Find active processes without matching our grep or the script itself
    PIDS=$(pgrep -f "run_pipeline.sh|to_execute_googlenews_opensee_1_0.py|to_execute_resolveggopensee.py|fetch_risk_net.py" | tr '\n' ' ')
    echo "   PIDs: $PIDS"
    
    if [ -f "$LOG_FILE" ]; then
      CURRENT_SEED=$(grep -a -E "Processing seed:" "$LOG_FILE" | tail -n 1 | sed 's/Processing seed: //')
      if [ -n "$CURRENT_SEED" ]; then
        echo "   Active Seed: $CURRENT_SEED"
      fi
    fi
    
    if pgrep -f "[t]o_execute_googlenews_opensee_1_0.py" >/dev/null; then
      echo "   Current Stage: [Step 1/4] Google News Scraper"
      if [ -f "$LOG_FILE" ]; then
        LAST_QUERY=$(grep -a -E "Searching for: .* in English" "$LOG_FILE" | tail -n 1)
        [ -n "$LAST_QUERY" ] && echo "   Progress: $LAST_QUERY"
      fi
    elif pgrep -f "[t]o_execute_as_linkedin_v5.py" >/dev/null; then
      echo "   Current Stage: [Step 2/4] LinkedIn Post Scraper"
      if [ -f "$LOG_FILE" ]; then
        LAST_LINKEDIN=$(grep -a -E "\[[0-9]+/[0-9]+\] .*" "$LOG_FILE" | tail -n 1)
        [ -n "$LAST_LINKEDIN" ] && echo "   Progress: $LAST_LINKEDIN"
      fi
    elif pgrep -f "[t]o_execute_resolveggopensee.py" >/dev/null; then
      echo "   Current Stage: [Step 3/4] URL Resolution & Text Extraction"
      if [ -f "$LOG_FILE" ]; then
        LAST_EXTRACT=$(grep -a -E "🔎 \([0-9]+/[0-9]+\) Extracting from:" "$LOG_FILE" | tail -n 1)
        if [ -n "$LAST_EXTRACT" ]; then
          echo "   Progress: $LAST_EXTRACT"
        else
          LAST_RESOLVE=$(grep -a -E "🔍 \([0-9]+/[0-9]+\) Searching for:" "$LOG_FILE" | tail -n 1)
          [ -n "$LAST_RESOLVE" ] && echo "   Progress: $LAST_RESOLVE"
        fi
      fi
    elif pgrep -f "[f]etch_risk_net.py" >/dev/null; then
      echo "   Current Stage: [Step 4/4] (Weekly) Risk.net Article & Appointments Extractor"
    else
      echo "   Current Stage: Starting up / Orchestration"
    fi
    echo "   Logs: tail -f $LOG_FILE"
  else
    echo "⚪ Pipeline: IDLE"
  fi

  echo "--------------------------------------------------------"
  echo "🌾 Google News Seed Status:"

  cd "$WORKSPACE_DIR" || exit 1
  LATEST_RAW_CSV=$(ls -t news_*.csv seeds_*.csv 2>/dev/null | grep -E '^(news|seeds)_.*_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.csv$' | head -n 1)
  
  if [ -n "$LATEST_RAW_CSV" ]; then
    BASE_NAME="${LATEST_RAW_CSV%.csv}"
    FULLTEXT_FILE="${BASE_NAME}_fulltext.csv"
    CLEANED_BASE=$(echo "$LATEST_RAW_CSV" | sed -E 's/_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.csv//')
    SELECTED_SEED="${CLEANED_BASE/news_/seeds_}.csv"
    
    if [ "$LOCK_HELD" = "true" ]; then
      echo "⏳ Active Run (In Progress):"
      echo "   Raw File:   $LATEST_RAW_CSV"
      echo "   Seed:       $SELECTED_SEED"
      CHECKPOINT_FILE="${BASE_NAME}_fulltext_checkpoint.csv"
      if [ -f "$CHECKPOINT_FILE" ]; then
        CP_SIZE=$(du -sh "$CHECKPOINT_FILE" | cut -f1)
        echo "   Checkpoint: $CHECKPOINT_FILE ($CP_SIZE)"
      fi
    else
      if [ ! -f "$FULLTEXT_FILE" ]; then
        echo "⚠️  Last run was INTERRUPTED and is incomplete:"
        echo "   Raw File:   $LATEST_RAW_CSV"
        echo "   Seed:       $SELECTED_SEED"
        echo "   Status:     Missing ${FULLTEXT_FILE}"
        CHECKPOINT_FILE="${BASE_NAME}_fulltext_checkpoint.csv"
        if [ -f "$CHECKPOINT_FILE" ]; then
          CP_SIZE=$(du -sh "$CHECKPOINT_FILE" | cut -f1)
          echo "   Checkpoint: $CHECKPOINT_FILE ($CP_SIZE)"
        fi
      else
        OUT_SIZE=$(du -sh "$FULLTEXT_FILE" | cut -f1)
        OUT_DATE=$(date -r "$FULLTEXT_FILE" "+%Y-%m-%d %H:%M:%S")
        echo "✅ Last run completed successfully:"
        echo "   Output File: $FULLTEXT_FILE ($OUT_SIZE)"
        echo "   Seed:        $SELECTED_SEED"
        echo "   Completed:   $OUT_DATE"
      fi
    fi
  else
    LATEST_OUT=$(ls -t news_*_fulltext.csv seeds_*_fulltext.csv 2>/dev/null | head -n 1)
    if [ -n "$LATEST_OUT" ]; then
      OUT_FILE=$(basename "$LATEST_OUT")
      OUT_SIZE=$(du -sh "$LATEST_OUT" | cut -f1)
      OUT_DATE=$(date -r "$LATEST_OUT" "+%Y-%m-%d %H:%M:%S")
      echo "📝 Last completed output:"
      echo "   File: $OUT_FILE ($OUT_SIZE)"
      echo "   Completed: $OUT_DATE"
    else
      echo "📝 Last completed output: None found"
    fi
  fi

  echo "--------------------------------------------------------"
  echo "📰 Risk.net Weekly Pipeline Status:"
  if [ -f "$LAST_RISK_RUN_FILE" ]; then
    LAST_RISK_DATE=$(cat "$LAST_RISK_RUN_FILE" 2>/dev/null)
    if [ -n "$LAST_RISK_DATE" ]; then
      LAST_RISK_TS=$(date -d "$LAST_RISK_DATE" +%s 2>/dev/null || echo 0)
      TODAY_TS=$(date -d "$TODAY" +%s)
      DIFF_DAYS=$(( (TODAY_TS - LAST_RISK_TS) / 86400 ))
      if [ "$DIFF_DAYS" -ge 7 ]; then
        echo "   Schedule:   🔴 DUE TO RUN (Last run was $DIFF_DAYS days ago: $LAST_RISK_DATE)"
      else
        DAYS_LEFT=$(( 7 - DIFF_DAYS ))
        echo "   Schedule:   🟢 UP TO DATE (Last run: $LAST_RISK_DATE, $DIFF_DAYS days ago; next run in $DAYS_LEFT days)"
      fi
    else
      echo "   Schedule:   🔴 DUE TO RUN (State file empty)"
    fi
  else
    echo "   Schedule:   🔴 DUE TO RUN (No previous run recorded)"
  fi

  if [ -f "$WORKSPACE_DIR/risk_top_articles_by_category.md" ]; then
    RISK_MD_DATE=$(date -r "$WORKSPACE_DIR/risk_top_articles_by_category.md" "+%Y-%m-%d %H:%M:%S")
    echo "   Latest MD:  risk_top_articles_by_category.md (Generated: $RISK_MD_DATE)"
  fi

  if [ -f "$LOG_FILE" ]; then
    LAST_COMPLETION=$(grep -a -E "^🎉 Pipeline" "$LOG_FILE" | tail -n 1)
    [ -n "$LAST_COMPLETION" ] && echo "   Last Completion: $LAST_COMPLETION"
  fi
  echo "========================================================"
}

# --- On-Demand Risk.net Execution ---
run_risk_net_now() {
  echo "========================================================"
  echo "📰 Executing Risk.net Pipeline On-Demand..."
  echo "========================================================"
  cd "$WORKSPACE_DIR" || exit 1
  python3 -u fetch_risk_net.py --all-top --log-db --save-md risk_top_articles_by_category.md --save-json risk_top_articles.json
  STATUS=$?
  if [ $STATUS -eq 0 ]; then
    echo "$TODAY" > "$LAST_RISK_RUN_FILE"
    echo "✅ Risk.net pipeline completed successfully and logged to database."
  else
    echo "❌ Error: Risk.net pipeline failed with exit code $STATUS."
  fi
  exit $STATUS
}

# --- Weekly Cadence Execution Function ---
run_risk_net_weekly_check() {
  FORCE_RISK="${1:-false}"
  DAYS_SINCE_RISK=999
  
  if [ -f "$LAST_RISK_RUN_FILE" ]; then
    LAST_RISK_DATE=$(cat "$LAST_RISK_RUN_FILE" 2>/dev/null)
    if [ -n "$LAST_RISK_DATE" ]; then
      LAST_RISK_TS=$(date -d "$LAST_RISK_DATE" +%s 2>/dev/null || echo 0)
      TODAY_TS=$(date -d "$TODAY" +%s)
      DAYS_SINCE_RISK=$(( (TODAY_TS - LAST_RISK_TS) / 86400 ))
    fi
  fi

  if [ "$FORCE_RISK" = "true" ] || [ "$DAYS_SINCE_RISK" -ge 7 ]; then
    echo "-----------------------------------------------------------------" >> "$LOG_FILE"
    echo "📰 [Step 4/4] (Weekly) Running Risk.net Extraction & Database Ingestion Pipeline..." >> "$LOG_FILE"
    if [ "$FORCE_RISK" = "true" ]; then
      echo "   Trigger: Forced manual execution via flag" >> "$LOG_FILE"
    elif [ "$DAYS_SINCE_RISK" -ge 7 ] && [ "$DAYS_SINCE_RISK" -lt 999 ]; then
      echo "   Trigger: Weekly cadence reached ($DAYS_SINCE_RISK days since last run on $LAST_RISK_DATE)" >> "$LOG_FILE"
    else
      echo "   Trigger: Initial run (no previous run record found)" >> "$LOG_FILE"
    fi

    python3 -u fetch_risk_net.py --all-top --log-db --save-md risk_top_articles_by_category.md --save-json risk_top_articles.json >> "$LOG_FILE" 2>&1
    RISK_STATUS=$?

    if [ $RISK_STATUS -eq 0 ]; then
      echo "✅ (Weekly) Risk.net pipeline completed successfully." >> "$LOG_FILE"
      echo "$TODAY" > "$LAST_RISK_RUN_FILE"
    else
      echo "❌ Error: Risk.net pipeline failed with exit code $RISK_STATUS." >> "$LOG_FILE"
    fi
  else
    DAYS_LEFT=$(( 7 - DAYS_SINCE_RISK ))
    echo "ℹ️ (Weekly) Risk.net pipeline up to date (ran on $LAST_RISK_DATE, $DAYS_SINCE_RISK days ago; next run in $DAYS_LEFT days). Skipping today." >> "$LOG_FILE"
  fi
}

# --- CLI Argument Handling ---
if [ "$1" = "status" ]; then
  show_status
  exit 0
fi

if [ "$1" = "risk-net" ] || [ "$1" = "risk" ] || [ "$1" = "--risk-net" ]; then
  run_risk_net_now
fi

FORCE_RISK_NET=false
if [ "$1" = "--force-risk-net" ]; then
  FORCE_RISK_NET=true
fi

# --- Locking Mechanism ---
# Ensures only one instance of the pipeline runs at a time.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "⚠️ Pipeline is already running (Locked). Exiting."
  exit 0
fi

# Navigate to the script's directory to ensure all relative paths resolve correctly
cd "$WORKSPACE_DIR" || exit 1

# Log session startup
echo "=================================================================" >> "$LOG_FILE"
echo "Pipeline execution started: $(date)" >> "$LOG_FILE"

# List of available seed files
SEEDS=(
  "seeds_buyside_eu_uae.csv"
  "seeds_buyside_london.csv"
  "seeds_buyside_us.csv"
  "seeds_sellside_eu.csv"
  "seeds_sellside_london.csv"
  "seeds_sellside_us.csv"
)

# 1. Check for interrupted run: check the latest news_*.csv raw file (no _resolved and no _fulltext in name)
LATEST_RAW_CSV=$(ls -t news_*.csv 2>/dev/null | grep -E '^news_.*_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.csv$' | head -n 1)
RESUME_RUN=false
SELECTED_SEED=""

if [ -n "$LATEST_RAW_CSV" ]; then
    BASE_NAME="${LATEST_RAW_CSV%.csv}"
    FULLTEXT_FILE="${BASE_NAME}_fulltext.csv"
    if [ ! -f "$FULLTEXT_FILE" ]; then
        RESUME_RUN=true
        CLEANED_BASE=$(echo "$LATEST_RAW_CSV" | sed -E 's/_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}\.csv//')
        SELECTED_SEED="${CLEANED_BASE/news_/seeds_}.csv"
        echo "⚠️ Detected interrupted run: $LATEST_RAW_CSV (missing $FULLTEXT_FILE)." >> "$LOG_FILE"
        echo "Resuming this execution for seed: $SELECTED_SEED" >> "$LOG_FILE"
    fi
fi

# 2. If no interrupted run, select the next seed in rotation based on the latest completed fulltext output
if [ "$RESUME_RUN" = "false" ]; then
    LATEST_FULLTEXT=$(ls -t news_*_fulltext.csv 2>/dev/null | head -n 1)
    if [ -z "$LATEST_FULLTEXT" ]; then
        SELECTED_SEED="${SEEDS[0]}"
        echo "No previous completed runs found. Starting with first seed: $SELECTED_SEED" >> "$LOG_FILE"
    else
        CLEANED_BASE=$(echo "$LATEST_FULLTEXT" | sed -E 's/_[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{2}_fulltext\.csv//')
        LAST_SEED="${CLEANED_BASE/news_/seeds_}.csv"
        echo "Last completed seed was: $LAST_SEED" >> "$LOG_FILE"
        
        INDEX=-1
        for i in "${!SEEDS[@]}"; do
           if [ "${SEEDS[$i]}" = "$LAST_SEED" ]; then
               INDEX=$i
               break
           fi
        done
        
        if [ "$INDEX" -eq -1 ]; then
            echo "Warning: Last completed seed $LAST_SEED not found in SEEDS array. Starting with first seed." >> "$LOG_FILE"
            NEXT_INDEX=0
        else
            NEXT_INDEX=$(( (INDEX + 1) % 6 ))
        fi
        
        SELECTED_SEED="${SEEDS[$NEXT_INDEX]}"
        echo "Selected next seed in rotation: $SELECTED_SEED" >> "$LOG_FILE"
    fi
fi

SEED_BASE=$(basename "$SELECTED_SEED" .csv)
OUTPUT_BASE=${SEED_BASE/seeds/news}
echo "-----------------------------------------------------------------" >> "$LOG_FILE"
echo "Processing seed: $SELECTED_SEED" >> "$LOG_FILE"

# --- Skip Check: Skip if today's output already exists for this specific seed (only when not resuming) ---
SKIP_SEED=false
if [ "$RESUME_RUN" = "false" ]; then
    DATE_PATTERN=$(date +%y-%m-%d)
    EXISTING_OUTPUT=$(ls "${OUTPUT_BASE}_${DATE_PATTERN}"*_fulltext.csv 2>/dev/null | head -n 1)
    if [ -n "$EXISTING_OUTPUT" ]; then
        echo "✅ Today's output already exists for $OUTPUT_BASE: $EXISTING_OUTPUT" >> "$LOG_FILE"
        echo "Skipping daily Google News seed." >> "$LOG_FILE"
        SKIP_SEED=true
    fi
fi

# --- Execution Stages ---
STEP1_STATUS=0
RUN_STEP1=true

if [ "$RESUME_RUN" = "true" ]; then
    RUN_STEP1=false
    echo "Skipping Step 1 (Scraping) since we are resuming an interrupted run." >> "$LOG_FILE"
fi

if [ "$SKIP_SEED" = "false" ]; then
    if [ "$RUN_STEP1" = "true" ]; then
        echo "[Step 1/4] Running to_execute_googlenews_opensee_1_0.py with seed: $SELECTED_SEED" >> "$LOG_FILE"
        python3 -u to_execute_googlenews_opensee_1_0.py --seeds "$SELECTED_SEED" >> "$LOG_FILE" 2>&1
        STEP1_STATUS=$?
    fi

    if [ $STEP1_STATUS -ne 0 ]; then
        echo "❌ Error: Step 1 (Scraping) failed for $SELECTED_SEED with exit code $STEP1_STATUS." >> "$LOG_FILE"
    else
        if [ "$RUN_STEP1" = "true" ]; then
            echo "✅ Step 1 completed successfully." >> "$LOG_FILE"
        fi

        # Step 2: Run LinkedIn scraper
        echo "[Step 2/4] Running to_execute_as_linkedin_v5.py with seed: $SELECTED_SEED" >> "$LOG_FILE"
        python3 -u to_execute_as_linkedin_v5.py --seeds "$SELECTED_SEED" >> "$LOG_FILE" 2>&1
        STEP2_STATUS=$?

        if [ $STEP2_STATUS -ne 0 ]; then
            echo "❌ Error: Step 2 (LinkedIn Scraper) failed for $SELECTED_SEED with exit code $STEP2_STATUS." >> "$LOG_FILE"
        else
            echo "✅ Step 2 completed successfully." >> "$LOG_FILE"

            # Step 3: Run URL resolution and text extraction
            echo "[Step 3/4] Running to_execute_resolveggopensee.py on the scraped news articles" >> "$LOG_FILE"
            python3 -u to_execute_resolveggopensee.py >> "$LOG_FILE" 2>&1
            STEP3_STATUS=$?

            if [ $STEP3_STATUS -ne 0 ]; then
                echo "❌ Error: Step 3 (Resolution and Extraction) failed for $SELECTED_SEED with exit code $STEP3_STATUS." >> "$LOG_FILE"
            else
                echo "✅ Step 3 completed successfully." >> "$LOG_FILE"

                # --- Output Post-Processing: Copy to .txt and Split if > 1500 lines ---
                LATEST_OUT=$(ls -t news_*_fulltext.csv 2>/dev/null | head -n 1)
                if [ -n "$LATEST_OUT" ]; then
                    BASE_OUT="${LATEST_OUT%.csv}"
                    TXT_OUT="${BASE_OUT}.txt"
                    echo "📋 Copying final output to $TXT_OUT" >> "$LOG_FILE"
                    cp "$LATEST_OUT" "$TXT_OUT"

                    LINE_COUNT=$(wc -l < "$TXT_OUT")
                    if [ "$LINE_COUNT" -gt 1500 ]; then
                        echo "✂️ Output has $LINE_COUNT lines (> 1500). Splitting into smaller files..." >> "$LOG_FILE"
                        python3 -c "
import math
import os
file_path = '$TXT_OUT'
base_name = os.path.splitext(file_path)[0]
with open(file_path, 'r') as f:
    lines = f.readlines()
header = lines[0]
data = lines[1:]
max_lines = 1499
num_parts = math.ceil(len(data) / max_lines)
for i in range(num_parts):
    part_data = data[i*max_lines : (i+1)*max_lines]
    part_filename = f'{base_name}_part_{i:02d}.txt'
    with open(part_filename, 'w') as f_out:
        f_out.write(header)
        f_out.writelines(part_data)
    print(f'   Created {part_filename} ({len(part_data) + 1} lines)')
" >> "$LOG_FILE" 2>&1
                    fi
                fi
            fi
        fi
    fi

    # Print Brave Search API Quota Recap
    python3 -c "import brave_quota_manager; brave_quota_manager.print_recap('$SELECTED_SEED')" >> "$LOG_FILE" 2>&1
fi

# --- Step 4: Risk.net Weekly Cadence Execution ---
# Evaluated every time run_pipeline.sh is invoked, ensuring it runs once every 7 days.
run_risk_net_weekly_check "$FORCE_RISK_NET"

echo "🎉 Pipeline batch execution completed at: $(date)" >> "$LOG_FILE"
echo "$TODAY" > "$LAST_RUN_FILE"
echo "=================================================================" >> "$LOG_FILE"

exit 0
