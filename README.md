# 🎯 Mission Challenge Analyzer

Comprehensive analysis system for OpenWebUI mission challenges and employee engagement tracking. The project now ships as a two-service stack: a FastAPI backend that exposes analytics data and a Next.js (TypeScript) frontend that renders the enhanced interactive dashboard.

## 🏗️ Repository Structure

- `backend/` – FastAPI application (`uvicorn backend.app.main:app`)
- `frontend/` – Next.js app for the mission dashboard UI
- `mission_analyzer.py` and `/scripts` – Existing analytics utilities retained for CLI or batch workflows
- `data/` – Chat export files + user name mappings consumed by the backend

## 🚀 Quick Start

### 1. Prepare data

Place an OpenWebUI export in `data/` (e.g. `data/all-chats-export-*.json`). Optionally add a `data/user_names.json` mapping for friendly names.

### 2. Start the stack

#### Option A – Manual terminals

```bash
# Terminal 1 – Backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload

# Terminal 2 – Frontend
cd frontend
npm install
npm run dev
```

Environment variables:

- `MISSION_DATA_FILE` (optional) – absolute/relative path to a specific export
- `MISSION_USER_NAMES_FILE` (optional) – override the default `data/user_names.json`
- `OPEN_WEBUI_HOSTNAME` – (optional) base URL for live OpenWebUI instance (e.g. `https://amichat.prod.amivero-solutions.com`)
- `OPEN_WEBUI_API_KEY` – (optional) bearer token used when fetching live chats from OpenWebUI

When both `OPEN_WEBUI_HOSTNAME` and `OPEN_WEBUI_API_KEY` are set, the backend bypasses local exports and streams data directly from `${OPEN_WEBUI_HOSTNAME}/api/v1/chats/all/db` and `${OPEN_WEBUI_HOSTNAME}/api/v1/users/all` on each request, so the dashboard always reflects the latest conversations and user display names.

Set `NEXT_PUBLIC_API_BASE_URL` (and `API_BASE_URL` for server-side fetches if the API is remote). Defaults to `http://localhost:8000`.

Open `http://localhost:3000` to view the dashboard. The UI mirrors the legacy enhanced dashboard, including overview metrics, leaderboard, mission breakdown, all-chats view, and model stats with live filtering.

#### Option B – Docker Compose (via Make)

```bash
make up
```

Hot reload is enabled for both services:
- Backend runs `uvicorn` with `--reload` and mounts the repository so Python changes apply immediately.
- Frontend runs `npm run dev` with the project mounted and `node_modules` persisted in a named volume.

The compose file and `.env` bind the local `data/` directory into both containers at `/app/data` so new exports are immediately available to the API and UI. Update `.env` if you need to tweak ports or API URLs.

---

### View Results

The system generates:
- **`public/mission_dashboard.html`** - Interactive web dashboard (opens automatically)
- Console output with summary and leaderboards

## 🔍 Advanced Usage

### Filtering Options

```bash
# Filter by specific week
python analyze_missions.py --week 1

# Filter by specific challenge
python analyze_missions.py --challenge 1

# Filter by specific week AND challenge
python analyze_missions.py --week 1 --challenge 1

# Filter by specific user
python analyze_missions.py --user abc123-def456-...

# Use specific export file
python analyze_missions.py --file data/all-chats-export-1234567890.json
```

### Export Options

```bash
# Export results to JSON
python analyze_missions.py --export-json

# Export leaderboard to CSV
python analyze_missions.py --export-csv

# Skip HTML dashboard generation
python analyze_missions.py --no-dashboard

# Combine options
python analyze_missions.py --week 1 --export-csv --export-json
```

### Get Help

```bash
python analyze_missions.py --help
```

## 📁 Required Files

The system needs an OpenWebUI chat export file:
- **Format:** `all-chats-export-<timestamp>.json`
- **Location:** `data/` directory in this repository
- **Source:** Exported from OpenWebUI Admin Panel

### Optional: User Names Mapping

The system auto-generates friendly names (User 1, User 2, etc.) for all participants.

**To use custom names:**
1. Edit `data/user_names.json`
2. Replace `"User 1"` with actual names like `"John Smith"`
3. Run the analyzer again
4. Dashboard now shows real names!

See `USER_NAMES_GUIDE.txt` for detailed instructions.

## 📊 Understanding the Results

### Dashboard Tabs

The enhanced dashboard features **4 interactive tabs**:

#### 1. 📊 Overview Tab
   - Summary statistics cards
   - Top performers leaderboard
   - Ranked by completions
   - Success rate visualizations

#### 2. 💬 All Chats Tab ⭐ NEW!
   - **Browse all 20 chats** in one place
   - Search by title, user, or model
   - Filter by type (Mission/Regular/Completed)
   - Expandable conversation previews
   - See first 3 messages of each chat
   - Distinguish mission vs regular chats

#### 3. 🎯 Missions Tab
   - Detailed mission breakdown
   - Per-mission statistics
   - Success rates
   - Participant counts

#### 4. 🤖 Models Tab ⭐ NEW!
   - Model usage statistics
   - Total chats per model
   - Mission vs regular chat breakdown
   - Completion rates by model

### Success Determination

A mission is marked as "completed" when the AI assistant's response contains success keywords:
- "congratulations"
- "you did it"
- "success"
- "mission accomplished"
- And more...

## 🎯 Mission Model Detection

The system automatically detects missions by looking for these patterns in model names:
- `maip---week-X---challenge-Y`
- Any model containing: `maip`, `challenge`, `week`, or `mission`

### Example Mission URLs

- Week 1, Challenge 1: `?model=maip---week-1---challenge-1`
- Week 1, Challenge 2: `?model=maip---week-1---challenge-2`
- Week 2, Challenge 1: `?model=maip---week-2---challenge-1`

## 📤 Export Formats

### JSON Export (`mission_results.json`)

Contains:
- Summary statistics
- Complete leaderboard
- Mission breakdown
- Individual chat details

### CSV Export (`mission_results.csv`)

Leaderboard in spreadsheet format with:
- User rankings
- Attempt/completion counts
- Success rates
- Message statistics

## 🔄 Workflow

### Regular Monitoring

1. **Export chats** from OpenWebUI (Admin Panel)
2. **Save file** into the `data/` directory as `all-chats-export-<timestamp>.json`
3. **Run analysis:**
   ```bash
   python analyze_missions.py
   ```
4. **Review dashboard** in browser
5. **Repeat** as needed to track progress

### Weekly Reports

```bash
# Generate Week 1 report
python analyze_missions.py --week 1 --export-csv

# Generate Week 2 report
python analyze_missions.py --week 2 --export-csv
```

## 📋 System Files

- **`analyze_missions.py`** - Main entry point (run this!)
- **`mission_analyzer.py`** - Core analysis engine
- **`generate_dashboard.py`** - Dashboard generator
- **`public/mission_dashboard.html`** - Generated dashboard (auto-updated)
- **`mission_results.json`** - Exported data (optional)
- **`mission_results.csv`** - Exported leaderboard (optional)

## 📚 Documentation

All supporting guides live in the `docs/` directory. Start with the guides that match your role:

- `docs/ADMIN_DEPLOYMENT_GUIDE.md` – Full deployment playbook with setup options, permissions, and maintenance tips.
- `docs/ADMIN_QUICK_REFERENCE.txt` – One-page cheat sheet admins can pin for daily operations.
- `docs/DEPLOYMENT_SUMMARY.md` – High-level summary of deliverables, deployment checklist, and success metrics.
- `docs/QUICKSTART.txt` – Three-step walkthrough for running the analyzer manually.
- `docs/API_SETUP_GUIDE.md` – Instructions for enabling API-based chat fetching and automation.
- `docs/QUICK_START_API.txt` – Fast reference for the API workflow once it is configured.
- `docs/DEPLOY_MISSION_2.md` – Mission 2 rollout plan, including prompts, success criteria, and communications.
- `docs/MISSION_2_CIPHER_BREAKER.md` – Detailed mission brief that complements the deployment guide.
- `docs/mission-2-system-prompt.txt` – Ready-to-paste system prompt used for Mission 2.
- `docs/USER_NAMES_GUIDE.txt` – Optional mapping guide for replacing user IDs with friendly names.
- `docs/WHATS_NEW.txt` – Change log of recent updates to the analytics tool.
- `docs/chat_summary.txt` / `docs/complete_conversation_log.txt` – Example output artifacts for demos or troubleshooting.

## 🎨 Dashboard Features

The HTML dashboard includes:
- 📊 Real-time statistics cards
- 🏆 Animated leaderboard with medals
- 📈 Progress bars for success rates
- 🎯 Mission-by-mission breakdown
- 🔄 Auto-updating timestamp
- 📱 Responsive design (mobile-friendly)

## ⚠️ Troubleshooting

### No export file found
```
✗ No export file found!
```
**Solution:** Export chats from OpenWebUI and save to the `data/` directory

### No mission attempts yet
```
⏳ NO MISSION ATTEMPTS YET
```
**Solution:** This is normal! Share the mission link with employees:
```
https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-1
```

### File encoding errors
The system handles UTF-8 encoding automatically, but ensure your export file is valid JSON.

## 💡 Tips

1. **Regular Updates:** Run analysis after employees have had time to participate
2. **Filters:** Use filters to focus on specific weeks or challenges
3. **Exports:** Use CSV export for presentations and reports
4. **Dashboard:** Share the HTML dashboard with stakeholders
5. **Monitoring:** Check participation rates to gauge engagement

## 🔧 Technical Details

**Language:** Python 3.6+  
**Dependencies:** Standard library only (no pip install needed!)  
**Platform:** Cross-platform (Windows, Mac, Linux)

## 📞 Support

For questions or issues:
1. Check this README
2. Run `python analyze_missions.py --help`
3. Review the console output for error messages

## 🎉 Example Output

```
================================================================================
  🎯  MISSION CHALLENGE ANALYZER
  OpenWebUI Employee Engagement Tracker
================================================================================

📁 Using file: all-chats-export-1760058097987.json
✓ Loaded 20 chats from all-chats-export-1760058097987.json

================================================================================
📊 ANALYSIS RESULTS
================================================================================
Total Chats in Export: 20
Mission Attempts Found: 5
Mission Completions: 3
Success Rate: 60.0%
Unique Participants: 4

📋 Missions Identified:
  • Week 1, Challenge 1
  • Week 1, Challenge 2

================================================================================
🏆 TOP PERFORMERS
================================================================================
🥇 user123-abc-def...
    Completions: 2 | Attempts: 2 | Success Rate: 100.0% | Messages: 8
🥈 user456-ghi-jkl...
    Completions: 1 | Attempts: 2 | Success Rate: 50.0% | Messages: 12

🎨 Generating HTML dashboard...
✓ Dashboard generated: public/mission_dashboard.html

✓ Dashboard ready: public/mission_dashboard.html
  Open it in your browser to view interactive results!
  (Opening in browser...)

================================================================================
✅ ANALYSIS COMPLETE
================================================================================
```

---

**Ready to track your missions!** 🚀
