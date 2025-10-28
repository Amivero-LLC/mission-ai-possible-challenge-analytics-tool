# Scripts Directory

## missing_credit_report.py

This script compares completed challenges from the API with awarded credits from the CSV file to identify users who completed challenges but haven't received credit yet. The report includes a detailed console table showing week numbers, user information, and point values.

### Automatic Data Refresh

The script automatically checks if the cached data is more than 1 hour old and attempts to refresh it from Open WebUI before running the comparison. This ensures you're always working with recent data without manual intervention.

### Prerequisites

1. **FastAPI Server Running**: The script requires the FastAPI backend to be running on port 8000 (or specify a custom URL with `API_BASE_URL` environment variable)

   ```bash
   # Start the API server in one terminal
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Required Data Files**:
   - `data/SubmittedActivityList.csv` - **REQUIRED**: CSV file with awarded credits from the activity tracking system
     - This file must be manually uploaded to the `data/` folder
     - Format should include columns: `Email`, `MissionChallenge`, `ActivityStatus`, `PointsAwarded`
     - Only rows with `ActivityStatus = "Review Completed"` will be considered for credit matching

3. **Optional: Open WebUI Credentials** (for automatic data refresh):
   - Set `OPEN_WEBUI_HOSTNAME` and `OPEN_WEBUI_API_KEY` environment variables
   - If configured, the script will automatically refresh stale data (>1 hour old)
   - If not configured, the script will use cached data and show a warning

### Usage

```bash
# With default API URL (http://localhost:8000)
python scripts/missing_credit_report.py

# With custom API URL
API_BASE_URL=http://your-server:8000 python scripts/missing_credit_report.py
```

### What It Does

1. **Checks data freshness** - Verifies when data was last refreshed from Open WebUI
   - If data is more than 1 hour old, attempts automatic refresh
   - Shows time since last refresh (e.g., "✓ Data is fresh (15.3 minutes old)")
2. **Fetches completed challenge data** from the `/users` API endpoint
3. **Loads awarded credit data** from `data/SubmittedActivityList.csv`
4. **Normalizes challenge names** to match between both sources
5. **Identifies users** who completed challenges but haven't received credit
6. **Displays detailed console table** with week numbers, names, emails, challenges, and points
7. **Generates two Excel reports** in the `exports/` folder:
   - `exports/combined_report.xlsx` - Full comparison report
   - `exports/missing_credit_report.xlsx` - Only users missing credit

**Note**: The `exports/` folder is automatically created if it doesn't exist. These files are excluded from git tracking.

### Output

The script displays:
- Data freshness check and automatic refresh status
- Summary statistics (total completions, credits awarded, credit rate)
- List of challenges completed but not credited with details
- List of unique users with missing credits
- **Detailed table** showing week numbers, user info, challenges, and points
- Excel report file locations

### Example Output

**With fresh data (< 1 hour old):**
```
=== CHECKING DATA FRESHNESS ===
✓ Data is fresh (15.3 minutes old)

=== FETCHING DATA FROM API ===
✓ Successfully fetched data from API
...
```

**With stale data (> 1 hour old, credentials configured):**
```
=== CHECKING DATA FRESHNESS ===
⚠️  Data is 2.5 hours old - refreshing...

🔄 Refreshing data from Open WebUI...
✓ Data refresh successful!
  Last fetched: 2025-10-28T11:30:00+00:00
  Data source: api
...
```

**With stale data (> 1 hour old, no credentials):**
```
=== CHECKING DATA FRESHNESS ===
⚠️  Data is 9.1 hours old - refreshing...

🔄 Refreshing data from Open WebUI...
✗ Warning: Cannot refresh - Open WebUI credentials not configured
  Set OPEN_WEBUI_HOSTNAME and OPEN_WEBUI_API_KEY to enable auto-refresh
  Continuing with existing cached data...
...
```

**Summary report:**
```
============================================================
SUMMARY REPORT
============================================================

✅ Total completed challenges: 128
🏆 Received credit: 119
❌ Did NOT receive credit: 9
📊 Credit rate: 93.0%

👥 7 USERS WITH MISSING CREDIT:
  • Crystal Carter (ccarter@amivero.com) - 1 challenge(s)
  • Kelly Weiner (kweiner@amivero.com) - 2 challenge(s)
  ...

==========================================================================================
DETAILED MISSING CREDIT REPORT
==========================================================================================

Name                      Email                          Week   Challenge                           Points
------------------------- ------------------------------ ------ ----------------------------------- ----------
Crystal Carter            ccarter@amivero.com            1      Intel Guardian                      20
Daniel Ruggiero           druggiero@amivero.com          1      Prompt Qualification                15
David Larrimore           dlarrimore@amivero.com         3      Broken Compass                      20
Kelly Weiner              kweiner@amivero.com            3      Broken Compass                      20
Kelly Weiner              kweiner@amivero.com            3      Adjudication Protocol               20
------------------------------------------------------------------------------------------
Total missing credit: 9 challenges

📄 Full report saved as exports/combined_report.xlsx
📄 Missing credit report saved as exports/missing_credit_report.xlsx
```

### Important Notes

- **Automatic Refresh**: The script checks data age before running and auto-refreshes if data is > 1 hour old
- **Refresh Behavior**:
  - With Open WebUI credentials configured: Fetches fresh data automatically
  - Without credentials: Shows warning and uses cached data
  - You can manually refresh at any time via the `/refresh` API endpoint
- **Exports Folder**: All generated reports are saved to the `exports/` folder which is excluded from git
- **Required Data File**: The `data/SubmittedActivityList.csv` file must be manually placed in the `data/` folder before running the script
- **API Dependency**: The FastAPI server must be running for the script to fetch user challenge data
