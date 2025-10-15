# Dashboard Quick Start Guide

This guide will help you get the Mission Challenge Dashboard running in under 5 minutes.

## Prerequisites

- **Docker Desktop** installed and running ([Download here](https://www.docker.com/products/docker-desktop/))
- **Git** installed ([Download here](https://git-scm.com/downloads))
- **OpenWebUI API Key** (see below)

## Step 1: Get Your OpenWebUI API Key

1. Log into OpenWebUI at https://amichat.prod.amivero-solutions.com
2. Click on your profile → **Settings**
3. Go to **Account** tab
4. Scroll to **API Keys** section
5. Click **Create new API key**
6. Copy the generated key (you'll need it in Step 3)

## Step 2: Clone the Repository

Open your terminal/command prompt and run:

```bash
git clone https://github.com/Amivero-LLC/amichat-platform.git
cd amichat-platform
```

## Step 3: Configure Environment

### Windows (PowerShell):
```powershell
Copy-Item .env.example -Destination .env
notepad .env
```

### Mac/Linux:
```bash
cp .env.example .env
nano .env
```

**Edit the `.env` file and update these two lines:**
```
OPEN_WEBUI_HOSTNAME=https://amichat.prod.amivero-solutions.com
OPEN_WEBUI_API_KEY=paste_your_api_key_here
```

Save and close the file.

## Step 4: Start the Dashboard

```bash
docker compose up -d
```

This will:
- Build the backend (FastAPI) and frontend (Next.js) containers
- Start both services
- Takes about 3-5 minutes on first run

## Step 5: Access the Dashboard

Open your browser to: **http://localhost:3000**

The dashboard will automatically connect to OpenWebUI and display live mission data!

## Using the Dashboard

### Main Features:

1. **Filter Panel** (top of page):
   - **Date From/To** - Filter by date range
   - **Challenge** - Select specific missions
   - **Status** - All/Completed/In Progress
   - **User Name** - Filter by participant
   - Click **Apply Filters** to update data
   - Click **Reset** to clear all filters

2. **Export Buttons**:
   - **📥 CSV** - Download current tab as CSV
   - **📥 Excel** - Download current tab as Excel file

3. **Four Tabs**:
   - **📊 Overview** - Leaderboard and mission breakdown
   - **💬 All Chats** - Full chat history with timestamps
   - **🎯 Missions** - Mission-specific statistics
   - **🤖 Models** - AI model usage analytics

## Stopping the Dashboard

```bash
docker compose down
```

## Troubleshooting

### "Failed to fetch" or "No data" error:
- Check that your API key is correct in `.env`
- Verify you can access https://amichat.prod.amivero-solutions.com
- Try restarting: `docker compose restart`

### Docker errors:
- Make sure Docker Desktop is running
- On Windows, ensure WSL 2 is installed and enabled

### Port already in use:
- Change `FRONTEND_PORT` or `BACKEND_PORT` in `.env`
- Restart: `docker compose down && docker compose up -d`

## Getting Help

For more detailed documentation, see:
- `docs/ADMIN_DEPLOYMENT_GUIDE.md` - Full deployment guide
- `docs/QUICKSTART.txt` - General quickstart
- `README.md` - Complete project documentation

## Need to Update?

To get the latest dashboard updates:

```bash
git pull origin main
docker compose down
docker compose up -d --build
```

---

**That's it!** You now have a fully functional Mission Challenge Dashboard with live OpenWebUI data. 🎉

