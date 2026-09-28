---
name: bank-broker-appointments-tracker
description: >-
  Extract, track, and structure executive appointments, job moves, new firm creations,
  and mandate allocations across the banking and brokerage sectors from news databases.
  Use when the user asks to monitor executive moves, find new hires in financial institutions,
  or format banking and brokerage talent intelligence into structured Markdown.
---

# Banking & Broker Appointments Tracker Skill

A standardized operational skill and runbook for discovering, extracting, and structuring appointment announcements, executive transitions, new firm launches, and mandate allocations in the banking and brokerage industries.

---

## 1. Skill Purpose & Scope

This skill guides the identification and structured cataloging of key talent movements and commercial mandates in the financial services ecosystem, specifically targeting:
- **Banking:** Investment banks, commercial banks, private banks, corporate banking divisions.
- **Brokerage:** Interdealer brokers, prime brokers, retail/institutional broker-dealers, agency brokers.
- **Mandates & Launches:** Creation of new financial firms, spin-offs, or significant institutional mandate allocations.

---

## 2. Trigger Conditions

Activate this skill when:
- Searching news feeds, press releases, or news databases for banking or brokerage executive hires.
- Processing raw news text or scraped articles containing appointment or mandate notices.
- Structuring commercial sales intelligence and lead generation data for financial sector outreach.

---

## 3. Data Schema & Extraction Fields

Every detected event must extract and standardize the following fields:

| Field Name | Type | Description | Example / Allowed Values |
| :--- | :--- | :--- | :--- |
| **Person Name** | String | Full name of the person appointed, promoted, or founding a new firm | `Sarah Jenkins` |
| **New Position Title** | String | Official job title of the new role | `Global Head of FX & Rates Trading` |
| **Date of News** | Date (ISO) | Date when the news was published (`YYYY-MM-DD`) | `2026-08-28` |
| **Source Link** | URL | HTTP/HTTPS link to the original news article or press release | `https://example.com/news/article-123` |
| **Company Name** | String | Legal or recognized operating name of the institution | `Barclays`, `TP ICAP` |
| **Company Sector** | Enum / Tag | Industry classification of the firm | `Banking`, `Investment Banking`, `Brokerage`, `Prime Brokerage` |
| **Location** | String | City and country (or state/region) of the position | `London, UK`, `New York, NY, US` |
| **Event Type** *(Optional)* | String | Nature of the news event | `Appointment`, `Promotion`, `New Firm Launch`, `Mandate Allocation` |

---

## 4. Search & Query Strategies

When querying news databases or search tools, combine target entities with key action triggers:

### Recommended Search Queries
- `"<Company Name>" ("appointed" OR "named" OR "joins" OR "hired as" OR "taps")`
- `(bank OR broker OR "prime brokerage") ("new head of" OR "managing director" OR "CIO" OR "CRO" OR "CEO")`
- `("launches new boutique" OR "spins out" OR "allocated mandate" OR "wins mandate") (banking OR broker)`
- `("appointment" OR "executive moves" OR "people moves") (London OR "New York" OR Paris OR Singapore)`

---

## 5. Standardized Output Formats

Depending on the user's request or workflow, format the output in either **Table Format** (summary) or **Card/Record Format** (deep profile).

### Format A: Markdown Summary Table
Use when presenting multiple news items in a concise, sortable overview.

```markdown
| Date | Person Name | New Position Title | Company Name | Sector | Location | Source |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | [Full Name] | [Position Title] | [Company Name] | [Sector] | [City, Country] | [Article Link](URL) |
```

### Format B: Markdown Structured Cards
Use for detailed records, Obsidian daily notes, CRM syncs, or account dossiers.

```markdown
### [Person Name] — [New Position Title]

- **Person Name:** [Full Name]
- **New Position Title:** [Official Job Title]
- **Date of News:** [YYYY-MM-DD]
- **Company Name:** [Company Name]
- **Company Sector:** [Banking / Brokerage / etc.]
- **Location:** [City, Country]
- **Source Link:** [Read Article](URL)
- **Summary / Context:** Brief 1–2 sentence overview of the previous background, mandate scope, or strategic context.
```

---

## 6. Execution Workflow & Best Practices

1. **Query Execution:** Run targeted search queries against the news database or web search endpoints.
2. **De-duplication:** Check if the individual or move has already been logged under an earlier press announcement.
3. **Verification:**
   - Verify that the position is new (avoid recurring profile articles or historical recaps).
   - Ensure the entity belongs to the Banking or Brokerage sector.
4. **Link Integrity:** Ensure source URLs are valid and direct to the specific article, avoiding generic homepages.
5. **Formatting:** Generate the output markdown adhering strictly to the schema defined above.
