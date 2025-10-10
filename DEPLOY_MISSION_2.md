# 🚀 Deploy Mission #2: Cipher Breaker

## Quick Deployment Checklist

---

## ✅ What You Have

I've created everything you need for Mission #2:

- ✅ **Mission design document:** `MISSION_2_CIPHER_BREAKER.md`
- ✅ **Ready-to-paste system prompt:** `mission-2-system-prompt.txt`
- ✅ **Encrypted message:** `Mrrszexmsr xlvsykl gsppefsvexmsr gviexiw pewxmrk mqtegx`
- ✅ **Answer:** `Innovation through collaboration creates lasting impact`
- ✅ **Analytics ready:** Dashboard will auto-detect completions

---

## 🎯 Deployment Steps (5 Minutes)

### **Step 1: Open System Prompt File**

Open: `mission-2-system-prompt.txt`

This contains the complete system prompt, ready to copy/paste.

---

### **Step 2: Create Model in OpenWebUI**

#### **Go to Dev Environment:**
1. Visit: https://amichat.dev.amivero-solutions.com
2. Login as admin
3. Click profile → **Admin Panel**

#### **Create New Model:**
1. Navigate to: **Workspace** → **Models** (or **Modelfiles**)
2. Click: **"+ Create New Model"** or **"Add Model"**

#### **Fill in Model Details:**

| Field | Value |
|-------|-------|
| **Name** | `maip---week-1---challenge-2` |
| **Display Name** | `Mission 2: Cipher Breaker` |
| **Description** | `Decrypt the intercepted transmission (20 pts - Medium)` |
| **Base Model** | `gpt-4` or `claude-3-5-sonnet` (your choice) |
| **System Prompt** | *Paste from `mission-2-system-prompt.txt`* |

#### **Set Parameters:**
- **Temperature:** `0.7`
- **Top P:** `0.9`
- **Max Tokens:** `2000`

#### **Save Model**

---

### **Step 3: Test in Dev**

1. **Visit Mission URL:**
   ```
   https://amichat.dev.amivero-solutions.com/?model=maip---week-1---challenge-2
   ```

2. **Test Conversation:**

   **You:** "What's the mission?"
   
   **AI:** Should present the encrypted message and brief
   
   **You:** "Can I have a hint?"
   
   **AI:** Should provide Level 1 hint
   
   **You:** "Innovation through collaboration creates lasting impact"
   
   **AI:** Should show "MISSION ACCOMPLISHED!" message

3. **Verify Success Message Contains:**
   - ✅ "Mission Accomplished" or "MISSION ACCOMPLISHED"
   - ✅ "20 pts" mentioned
   - ✅ SharePoint link
   - ✅ Decrypted phrase displayed

---

### **Step 4: Export as Preset (Optional but Recommended)**

1. **In OpenWebUI Admin:**
   - Find your model: `maip---week-1---challenge-2`
   - Click **Export** or **Download**
   - Save file as: `maip---week-1---challenge-2.json`

2. **Add to Git Repository:**
   ```bash
   # If you have the openwebui-localdev repo cloned
   cp maip---week-1---challenge-2.json /path/to/openwebui-localdev/presets/
   cd /path/to/openwebui-localdev
   git add presets/maip---week-1---challenge-2.json
   git commit -m "Add Mission 2: Cipher Breaker (20 pts - Medium)"
   git push
   ```

This backs up your mission configuration!

---

### **Step 5: Deploy to Production**

When ready for employees:

1. **Export from Dev:**
   - Export the tested modelfile

2. **Import to Prod:**
   - Go to: https://amichat.prod.amivero-solutions.com
   - Admin Panel → Models → Import
   - Upload the modelfile

3. **Test in Prod:**
   ```
   https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-2
   ```

4. **Verify Everything Works**

---

### **Step 6: Announce to Employees**

**Email Template:**

```
Subject: 🎯 New Mission Available - Cipher Breaker (20 pts)

Team,

A new mission challenge is now live!

🔐 Mission #2: Cipher Breaker
Difficulty: Medium
Points: 20

HQ has intercepted a scrambled AI transmission. Can you crack the code?

🔗 Access Mission:
https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-2

Skills You'll Use:
- Text pattern analysis
- Cryptography basics
- Problem-solving
- AI-assisted reasoning

Good luck, agents! 🕵️

Submit completions at: 
https://amivero.sharepoint.com/sites/MissionAIPossibleI
```

---

## 📊 Your Dashboard Will Automatically Track:

Once deployed and employees start attempting:

- ✅ Total attempts on Mission 2
- ✅ Completion count
- ✅ Success rate
- ✅ Who completed it
- ✅ Conversation strategies used
- ✅ Leaderboard updated

**The analyzer already supports this - no code changes needed!**

---

## 🔍 Testing Scenarios

Before going live, test these:

### **Scenario 1: First-Time User**
```
User: "What's this mission about?"
Expected: AI presents the encrypted message and mission brief
```

### **Scenario 2: User Asks for Hints**
```
User: "Can I get a hint?"
Expected: AI provides Level 1 hint
```

### **Scenario 3: Wrong Answer**
```
User: "The answer is: something wrong"
Expected: AI encourages them to keep trying
```

### **Scenario 4: Correct Answer**
```
User: "Innovation through collaboration creates lasting impact"
Expected: AI shows "MISSION ACCOMPLISHED" with all details
```

### **Scenario 5: Partial Answer**
```
User: "Is it about innovation and collaboration?"
Expected: AI encourages they're on the right track
```

---

## 📁 Files Created for You

All ready in your ParseChat folder:

| File | Purpose |
|------|---------|
| `MISSION_2_CIPHER_BREAKER.md` | Complete mission documentation |
| `mission-2-system-prompt.txt` | **Copy this to OpenWebUI** |
| `DEPLOY_MISSION_2.md` | This deployment guide |

---

## ⚡ Quick Deploy (TL;DR)

```bash
1. Open: mission-2-system-prompt.txt
2. Copy all text
3. Go to: https://amichat.dev.amivero-solutions.com
4. Admin Panel → Models → Create New
5. Name: maip---week-1---challenge-2
6. Paste system prompt
7. Save
8. Test: ?model=maip---week-1---challenge-2
9. Deploy to prod when ready
```

---

## 🎯 About the GitHub Repo

**To answer your question:** The [openwebui-localdev repository](https://github.com/Amivero-LLC/openwebui-localdev.git) does **NOT** have automated mission generation code.

**What it has:**
- ✅ Docker setup for running OpenWebUI locally
- ✅ `presets/` folder for storing model configurations
- ✅ Scripts for managing the environment
- ❌ No mission generator code

**How missions work:**
1. Create manually in OpenWebUI UI (what I've given you)
2. Export as preset
3. Store in `presets/` folder
4. Commit to Git for version control
5. Import to other environments as needed

**The repo is for infrastructure, not mission creation.**

---

## 🔄 Next Steps

**Ready to deploy Mission #2?**

1. ✅ **Open:** `mission-2-system-prompt.txt`
2. ✅ **Copy:** All the text
3. ✅ **Go to:** https://amichat.dev.amivero-solutions.com/admin
4. ✅ **Create model:** Paste system prompt
5. ✅ **Test it**
6. ✅ **Deploy to prod**

**Want me to:**
- Create Mission 3, 4, 5?
- Make missions harder/easier?
- Generate different ciphers?
- Create mission templates?

Let me know! 🚀

