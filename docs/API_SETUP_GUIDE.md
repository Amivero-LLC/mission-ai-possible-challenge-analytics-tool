# 🔌 OpenWebUI API Integration Guide

## Automatic Chat Fetching - No Manual Export Needed!

This guide shows you how to set up automatic data fetching from OpenWebUI.

---

## 🎯 Benefits of API Integration

Instead of manual export:
- ✅ **Automatic data fetching** - No manual export needed
- ✅ **Real-time data** - Always get latest chats
- ✅ **User names included** - Automatic name mapping
- ✅ **Scheduled updates** - Can run automatically (hourly/daily)
- ✅ **One-click operation** - Fetch and analyze together

---

## 📋 Prerequisites

1. **Admin access to OpenWebUI**
2. **Python with requests library**
   ```bash
   pip install requests
   ```

---

## 🔑 Step 1: Get OpenWebUI API Key

### **Method A: From OpenWebUI Settings**

1. **Log into OpenWebUI** (as admin)
   - Go to: https://amichat.prod.amivero-solutions.com

2. **Access Settings**
   - Click your profile icon (top right)
   - Select "Settings"

3. **Find API Section**
   - Look for "Account" or "API" tab
   - Or check "Admin Settings" → "API Keys"

4. **Generate API Key**
   - Click "Generate API Key" or "Create New Key"
   - Copy the key (save it securely!)
   - **Important:** You'll only see this once!

### **Method B: Via OpenWebUI Admin Panel**

1. **Go to Admin Panel**
   - Settings → Admin Panel

2. **API Settings**
   - Navigate to API or Authentication section
   - Create/Copy API key

3. **Save Key Securely**
   - Store in password manager
   - Don't share publicly

---

## ⚙️ Step 2: Configure the Script

### **Option A: Environment Variable (Recommended)**

```bash
# Windows PowerShell
$env:OPENWEBUI_API_KEY = "your-api-key-here"

# Windows CMD
set OPENWEBUI_API_KEY=your-api-key-here

# Or set permanently in System Environment Variables
```

### **Option B: Edit the Script**

1. Open `fetch_from_openwebui.py`
2. Find this line:
   ```python
   API_KEY = os.environ.get('OPENWEBUI_API_KEY', '')
   ```
3. Replace with:
   ```python
   API_KEY = "your-api-key-here"
   ```

### **Option C: Config File (Most Secure)**

Create `config.json`:
```json
{
  "openwebui_url": "https://amichat.prod.amivero-solutions.com",
  "api_key": "your-api-key-here"
}
```

---

## 🚀 Step 3: Run with API Fetch

### **One-Time Fetch:**

**Windows:**
```bash
Double-click: scripts/RUN_WITH_API_FETCH.bat
```

**Command Line:**
```bash
python fetch_from_openwebui.py
```

### **What Happens:**
1. ✅ Fetches all chats from OpenWebUI
2. ✅ Fetches user information (names/emails)
3. ✅ Creates `data/user_names.json` automatically
4. ✅ Saves export file in `data/`
5. ✅ Runs analysis
6. ✅ Opens dashboard

---

## 📅 Step 4: Automate with Task Scheduler (Optional)

### **Daily Automated Reports:**

1. **Create Scheduled Task**
   - Open Task Scheduler
   - Create Basic Task

2. **Configure Schedule**
   - Name: "Mission Analysis Daily Report"
   - Trigger: Daily at 8:00 AM
   - Action: Start a program

3. **Set Program**
   - Program: `C:\Path\To\scripts\RUN_WITH_API_FETCH.bat`
   - Start in: `C:\Path\To\ParseChat`

4. **Save Task**
   - Enter admin credentials if prompted

**Result:** Dashboard auto-updates daily at 8 AM!

---

## 🔧 API Endpoints Reference

### **OpenWebUI API Structure:**

```
Base URL: https://amichat.prod.amivero-solutions.com

Endpoints:
- GET /api/v1/chats          - Get all chats
- GET /api/v1/chats/{id}     - Get specific chat
- GET /api/v1/users          - Get all users (admin only)
- GET /api/v1/models         - Get available models
```

### **Authentication:**

```python
headers = {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
}
```

---

## 🛠️ Troubleshooting

### **Issue: "API key invalid"**

**Solutions:**
1. Regenerate API key in OpenWebUI
2. Check for extra spaces in key
3. Verify admin permissions
4. Check URL is correct

### **Issue: "Connection refused"**

**Solutions:**
1. Verify OpenWebUI URL
2. Check network connectivity
3. Try from browser first
4. Check firewall settings

### **Issue: "No user data returned"**

**Solutions:**
1. Verify you have admin permissions
2. Some endpoints require higher privileges
3. Check OpenWebUI version (may need update)

### **Issue: "requests module not found"**

**Solution:**
```bash
pip install requests
```

---

## 📊 Comparison: Manual vs API

| Feature | Manual Export | API Integration |
|---------|---------------|-----------------|
| **Setup Time** | None | 5 minutes |
| **Update Process** | Manual | Automatic |
| **User Names** | Manual mapping | Automatic |
| **Schedule** | Manual | Can automate |
| **Real-time** | No | Yes |
| **Admin Effort** | High | Low |

---

## 🔐 Security Best Practices

1. **Store API Keys Securely**
   - Use environment variables
   - Don't commit to git
   - Use config files in .gitignore

2. **Limit Access**
   - Only admins should have API keys
   - Rotate keys periodically
   - Revoke unused keys

3. **Monitor Usage**
   - Check API logs in OpenWebUI
   - Set up alerts for unusual activity
   - Track who has access

---

## 🎯 Recommended Workflow

### **For Admins:**

**One-Time Setup:**
1. Get API key from OpenWebUI
2. Set environment variable
3. Test with `scripts/RUN_WITH_API_FETCH.bat`

**Daily Use:**
1. Double-click `scripts/RUN_WITH_API_FETCH.bat`
2. Wait 10-20 seconds
3. Dashboard opens with latest data

**Or Automated:**
1. Set up Task Scheduler
2. Forget about it!
3. Dashboard updates automatically

---

## 📝 Advanced: Custom Fetch Script

### **Fetch Only Recent Chats:**

```python
def fetch_recent_chats(self, days=7):
    """Fetch chats from last N days"""
    from datetime import datetime, timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    all_chats = self.fetch_all_chats()
    
    recent = [
        chat for chat in all_chats 
        if chat.get('created_at', 0) > cutoff.timestamp()
    ]
    
    return recent
```

### **Fetch Specific Model Chats:**

```python
def fetch_mission_chats(self):
    """Fetch only mission-related chats"""
    all_chats = self.fetch_all_chats()
    
    mission_chats = [
        chat for chat in all_chats
        if 'maip' in str(chat.get('chat', {}).get('models', [])).lower()
    ]
    
    return mission_chats
```

---

## 🚀 Next Level: Real-Time Dashboard

### **Option: Web Dashboard with Auto-Refresh**

If you want a continuously updating dashboard:

1. **Install Streamlit:**
   ```bash
   pip install streamlit
   ```

2. **Create Streamlit App:**
   ```python
   # streamlit_dashboard.py
   import streamlit as st
   from fetch_from_openwebui import OpenWebUIFetcher
   
   st.title("Mission Analysis - Live Dashboard")
   
   if st.button("Refresh Data"):
       # Fetch and display
       pass
   ```

3. **Run:**
   ```bash
   streamlit run streamlit_dashboard.py
   ```

4. **Access:**
   - Open: http://localhost:8501
   - Auto-refreshes every 60 seconds

---

## ✅ Setup Checklist

**API Integration Setup:**

- [ ] Have admin access to OpenWebUI
- [ ] Generated API key
- [ ] Installed requests library (`pip install requests`)
- [ ] Configured API key (environment variable or script)
- [ ] Tested `scripts/RUN_WITH_API_FETCH.bat`
- [ ] Verified data/user_names.json created
- [ ] Dashboard opens with real names
- [ ] (Optional) Set up Task Scheduler for automation

**Total Setup Time: 10-15 minutes**

---

## 🎉 You're Ready!

Once configured, admins can:
- ✅ Run one script to get everything
- ✅ No manual export needed
- ✅ Get user names automatically
- ✅ Schedule automatic updates
- ✅ Always have latest data

**Choose your update method:**
- **On-Demand:** Double-click `scripts/RUN_WITH_API_FETCH.bat`
- **Automated:** Set up Task Scheduler for daily reports

---

## 📞 Support

**For API issues:**
1. Check OpenWebUI documentation
2. Verify API key is valid
3. Check admin permissions
4. Contact OpenWebUI support

**For script issues:**
1. Check `docs/API_SETUP_GUIDE.md` (this file)
2. Review error messages
3. Verify Python and requests are installed

---

**Happy automating! 🚀**
