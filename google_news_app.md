# Google News Scheduler: Setup & Deployment Guide

This guide explains how to deploy and configure the `google_news_scheduler.py` as a Google Cloud Function for automated news scraping.

## 1. Prerequisites
- **Project ID:** `innate-plexus-497011-m1`
- **Bucket Name:** Ensure the bucket `gnews-opensee` exists in Google Cloud Storage.
- **Service Account:** The default service account for Cloud Functions is typically `innate-plexus-497011-m1@appspot.gserviceaccount.com`.

## 2. Permissions & IAM

### A. Google Cloud Storage
The service account needs `Storage Object Admin` to read seeds and write results.

Run this command:
```bash
gcloud projects add-iam-policy-binding innate-plexus-497011-m1 \
    --member="serviceAccount:innate-plexus-497011-m1@appspot.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### B. Google Drive
Since service accounts are outside your workspace by default, you must share the target folder with them.

1. Copy the service account email: `innate-plexus-497011-m1@appspot.gserviceaccount.com`
2. Go to the target Google Drive folder.
3. Click **Share**.
4. Paste the email and grant **Editor** permissions.

## 3. Configuration Update
Before deploying, ensure `google_news_scheduler.py` has the correct constants:
- `BUCKET_NAME = "gnews-opensee"`
- `DRIVE_FOLDER_ID = "YOUR_ACTUAL_FOLDER_ID"`

## 4. Deployment

Deploy the function using the following command:

```bash
gcloud functions deploy run_gnews \
    --runtime python311 \
    --trigger-http \
    --allow-unauthenticated \
    --region us-central1 \
    --entry-point run_gnews \
    --memory 512MB \
    --timeout 540s
```

## 5. Automation (Cloud Scheduler)
To run this automatically (e.g., every morning at 8:00 AM):

1. Go to **Cloud Scheduler** in the GCP Console.
2. Create a Job.
3. Frequency: `0 8 * * *`
4. Target: **HTTP**
5. URL: (Use the URL provided after the `gcloud functions deploy` command finishes).
6. Auth Header: **Add OIDC token** (select the service account used above).
