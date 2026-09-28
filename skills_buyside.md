---
name: buyside-appointments-tracker
description: >-
  Extract, track, and structure executive appointments, portfolio manager moves, 
  fund launches, and mandate wins across the Buy Side (Asset Management, 
  Hedge Funds, Asset Owners, and Wealth Management).
---

# Buy-Side Appointments & Talent Tracker Skill

A standardized operational skill and runbook for discovering, extracting, and structuring appointment announcements, portfolio manager transitions, new fund launches, and mandate allocations in the investment management ecosystem.

---

## 1. Skill Purpose & Scope

This skill guides the identification and structured cataloging of key talent movements and commercial milestones in the Buy Side, specifically targeting:
- **Asset Management:** Long-only managers, mutual funds, ETF providers, alternative investment managers.
- **Hedge Funds:** Multi-manager platforms, boutique hedge funds, macro, equity long/short, and quantitative funds.
- **Asset Owners:** Pension funds (public/private), Sovereign Wealth Funds (SWFs), insurance companies, endowments, and foundations.
- **Wealth Management:** Multi-family offices, private wealth divisions, and independent wealth advisors.
- **Mandates & Launches:** New fund launches, team lift-outs, and significant institutional mandate awards.

---

## 2. Trigger Conditions

Activate this skill when:
- Searching news feeds, press releases, or news databases for Buy Side executive or investment professional hires.
- Processing raw news text or scraped articles containing portfolio manager moves or fund launch notices.
- Structuring competitive intelligence and talent mapping for the investment management sector.

---

## 3. Data Schema & Extraction Fields

Every detected event must extract and standardize the following fields:

| Field Name | Type | Description | Example / Allowed Values |
| :--- | :--- | :--- | :--- |
| **Person Name** | String | Full name of the professional appointed or transitioning | `Jane Doe` |
| **New Position Title** | String | Official job title of the new role | `Portfolio Manager, Global Equities` |
| **Date of News** | Date (ISO) | Date when the news was published (`YYYY-MM-DD`) | `2026-08-28` |
| **Source Link** | URL | HTTP/HTTPS link to the original news article or press release | `https://example.com/news/buyside-123` |
| **Company Name** | String | Legal or recognized operating name of the institution | `BlackRock`, `Bridgewater`, `CPPIB` |
| **Company Sector** | Enum / Tag | Industry classification of the firm | `Asset Management`, `Hedge Fund`, `Asset Owner`, `Wealth Management` |
| **Location** | String | City and country (or state/region) of the position | `London, UK`, `Singapore`, `New York, NY` |
| **Asset Class** | String | Primary asset class focus (if applicable) | `Equities`, `Fixed Income`, `Private Equity`, `Credit`, `Macro` |
| **Event Type** | String | Nature of the news event | `Appointment`, `Fund Launch`, `Mandate Win`, `Team Lift-out` |

---

## 4. Search & Query Strategies

When querying news databases or search tools, combine target entities with key action triggers:

### Recommended Search Queries
- `("Asset Management" OR "Hedge Fund" OR "Pension Fund") ("appointed" OR "hired" OR "joins")`
- `("Portfolio Manager" OR "Chief Investment Officer" OR "CIO" OR "Head of Research") ("joins" OR "named")`
- `("launches new fund" OR "closes fund" OR "new UCITS" OR "team lift-out")`
- `("wins mandate" OR "awarded mandate" OR "selected to manage") (BlackRock OR Vanguard OR Amundi)`
- `("Wealth Management" OR "Family Office") ("new hire" OR "executive transition")`

---

## 5. Standardized Output Formats

Depending on the user's request or workflow, format the output in either **Table Format** (summary) or **Card/Record Format** (deep profile).

### Format A: Markdown Summary Table
Use when presenting multiple news items in a concise, sortable overview.

```markdown
| Date | Person Name | Position | Company | Sector | Asset Class | Source |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | [Full Name] | [Position] | [Company Name] | [Sector] | [Asset Class] | [Link](URL) |
```

### Format B: Markdown Structured Cards
Use for detailed records, talent mapping, or CRM entries.

```markdown
### [Person Name] — [New Position Title]

- **Person Name:** [Full Name]
- **New Position Title:** [Official Job Title]
- **Date of News:** [YYYY-MM-DD]
- **Company Name:** [Company Name]
- **Company Sector:** [Asset Management / Hedge Fund / etc.]
- **Location:** [City, Country]
- **Asset Class:** [Equities / Credit / etc.]
- **Source Link:** [Read Article](URL)
- **Summary / Context:** Brief 1–2 sentence overview (e.g., previous firm, specific fund they will manage, or mandate size).
```

---

## 6. Execution Workflow & Best Practices

1. **Query Execution:** Run targeted search queries focusing on PMs, CIOs, and institutional sales roles.
2. **Asset Class Identification:** Ensure the asset class focus is captured, as this is critical for Buy Side intelligence.
3. **Verification:**
   - Confirm the individual is an investment or distribution professional (rather than back-office).
   - Ensure the firm is primarily a Buy Side entity (Asset Management, Hedge Fund, Asset Owner, or Wealth Management).
4. **Mandate Context:** For mandate wins, attempt to extract the size of the allocation (e.g., "$500m mandate").
5. **Formatting:** Generate the output markdown adhering strictly to the schema defined above.
