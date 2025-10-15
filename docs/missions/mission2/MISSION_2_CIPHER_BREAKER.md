# 🔐 Mission #2: Cipher Breaker

## Mission Details

- **Name:** Cipher Breaker
- **Points:** 20 pts
- **Difficulty:** Medium
- **Week:** 1 (or 2, depending on your schedule)
- **Challenge Number:** 2

---

## 📋 Mission Brief

**Scenario:** HQ intercepted a scrambled AI-generated transmission.

**Objective:** Use AmiChat or Open WebUI's text-analysis tools to decrypt it and reveal the original phrase.

**Proof:** Submit decrypted text via SharePoint.

**Skill Focus:** Text pattern recognition, translation, reasoning chains.

---

## 🛠️ OpenWebUI Model Configuration

### **Model Name:**
```
maip---week-1---challenge-2
```

### **Display Name:**
```
Mission 2: Cipher Breaker
```

### **Description:**
```
Decrypt the intercepted transmission to complete the mission. (20 pts - Medium)
```

---

## 📝 Complete Modelfile

```modelfile
FROM gpt-4

# Mission 2: Cipher Breaker
# Difficulty: Medium (20 points)
# Decrypt an intercepted AI transmission

SYSTEM """
You are Mission Control for the Cipher Breaker challenge.

**Mission Brief:**
HQ has intercepted a scrambled AI-generated transmission. Your mission is to decrypt it and reveal the original phrase.

**Your Role:**
- Present the encrypted message when users ask about the mission
- Guide them if they're stuck (but don't give away the answer)
- Confirm when they've successfully decrypted it
- Award points upon successful completion

**The Encrypted Message:**

"Mrrszexmsr xlvsykl gsppefsvexmsr gviexiw pewxmrk mqtegx"

**The Decryption Key (Hidden - Don't Tell Users!):**
- Cipher Type: Caesar Cipher
- Shift: 4 positions backward in alphabet
- Original Phrase: "Innovation through collaboration creates lasting impact"

**How Users Should Solve It:**
1. They ask you for the encrypted message
2. They analyze the pattern (letter frequency, repeated words)
3. They try different decryption methods (Caesar, substitution, etc.)
4. They figure out it's a Caesar cipher with shift of 4
5. They decrypt and submit the answer

**Hints You Can Give (Progressive):**
- Level 1 (if stuck): "Look at the letter patterns. Common short words might give you clues."
- Level 2 (still stuck): "Have you tried shifting letters in the alphabet?"
- Level 3 (really stuck): "Think about Caesar's cipher..."
- Level 4 (final hint): "Try shifting each letter by the same amount."

**When They Submit the Correct Answer:**

If they say something like:
- "Innovation through collaboration creates lasting impact"
- "The decrypted message is: Innovation through collaboration creates lasting impact"
- Or submit the correct phrase

You respond with:

"🎉 **MISSION ACCOMPLISHED!** 🎉

Outstanding work, Agent! You've successfully decrypted the intercepted transmission!

**Decrypted Message:** 
Innovation through collaboration creates lasting impact

**Cipher Used:** Caesar Cipher (shift of 4)

**Mission Points Earned:** 20 pts

**Next Steps:**
Submit your completion at the Mission: AI Possible SharePoint Site:
👉 https://amivero.sharepoint.com/sites/MissionAIPossibleI

**What You've Learned:**
✓ Pattern recognition and cryptanalysis
✓ Text analysis techniques
✓ Caesar cipher fundamentals
✓ Problem-solving with AI assistance
✓ How AI can help decrypt and analyze text

Excellent work on Mission #2! Ready for the next challenge? 🚀"

**Important Notes:**
- Be encouraging but don't give away the answer too easily
- Users should work through the problem
- Provide hints progressively only if they're truly stuck
- Confirm the exact decrypted phrase before declaring success
- Watch for variations in capitalization/punctuation (be flexible)
"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9

TEMPLATE """{{ if .System }}System: {{ .System }}{{ end }}
{{ if .Prompt }}User: {{ .Prompt }}{{ end }}
"""
```

---

## 🚀 Setup Instructions

### **Step 1: Create Model in OpenWebUI**

#### **Via Admin Panel UI:**

1. **Navigate to:**
   - https://amichat.dev.amivero-solutions.com (or prod)
   - Admin Panel → Workspace → Models (or Modelfiles)

2. **Click "Create New Model"** or "+" button

3. **Fill in Details:**
   - **Name:** `maip---week-1---challenge-2`
   - **Display Name:** `Mission 2: Cipher Breaker`
   - **Description:** `Decrypt the intercepted transmission (20 pts - Medium)`
   - **Base Model:** Select your preferred model (GPT-4, Claude, etc.)

4. **Paste System Prompt:**
   - Copy the SYSTEM section from above
   - Paste into the system prompt field

5. **Set Parameters:**
   - Temperature: 0.7
   - Top P: 0.9

6. **Save**

#### **Via Modelfile Format:**

If using Modelfile syntax directly:

1. Create new modelfile
2. Paste the complete modelfile from above
3. Save as: `maip---week-1---challenge-2`

---

### **Step 2: Test the Mission**

1. **Visit Mission URL:**
   ```
   https://amichat.dev.amivero-solutions.com/?model=maip---week-1---challenge-2
   ```

2. **Test Conversation:**
   ```
   User: "What's the mission?"
   AI: Should present the encrypted message
   
   User: "Innovation through collaboration creates lasting impact"
   AI: Should show success message
   ```

3. **Verify:**
   - Encrypted message displays correctly
   - Success keywords trigger ("Mission Accomplished")
   - SharePoint link is correct
   - Points are mentioned (20 pts)

---

### **Step 3: Export and Save Preset**

1. **Export the Model:**
   - In OpenWebUI admin, export the modelfile
   - Save as JSON/Modelfile format

2. **Add to Git Repository:**
   ```bash
   cd openwebui-localdev/presets
   # Save the exported file
   git add maip---week-1---challenge-2.json
   git commit -m "Add Mission 2: Cipher Breaker"
   git push
   ```

3. **Document in Presets README:**
   - Add mission details to `presets/README.md`
   - Include instructions for importing

---

### **Step 4: Deploy to Prod**

When ready for production:

1. **Export from Dev:**
   - Export the tested modelfile

2. **Import to Prod:**
   - Go to: https://amichat.prod.amivero-solutions.com
   - Admin Panel → Models → Import
   - Upload the modelfile

3. **Test in Prod:**
   - Visit prod URL with model parameter
   - Verify everything works

4. **Share with Employees:**
   ```
   https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-2
   ```

---

## 🎯 Mission Components Breakdown

### **Encrypted Message:**
```
Mrrszexmsr xlvsykl gsppefsvexmsr gviexiw pewxmrk mqtegx
```

### **Decryption (Caesar Cipher, Shift 4):**
```
Innovation through collaboration creates lasting impact
```

### **How It Works:**
```
M → I (shift back 4)
r → n (shift back 4)
r → n (shift back 4)
s → o (shift back 4)
z → v (shift back 4)
etc.
```

### **Success Criteria:**
User must submit the exact (or very close) phrase:
- "Innovation through collaboration creates lasting impact"
- Case-insensitive matching recommended
- Ignore minor punctuation differences

---

## 📊 Difficulty Tuning

### **Current: Medium (20 pts)**
- Caesar cipher with shift of 4
- Pattern is recognizable
- Common cipher that AI can help with

### **To Make Easier (15 pts):**
- Use shift of 1-3 (more obvious)
- Add more hints in system prompt
- Shorter encrypted phrase

### **To Make Harder (25 pts):**
- Use different cipher (Vigenère, substitution)
- Longer phrase
- Multiple encryption layers
- Fewer hints

---

## 🎨 Customization Options

### **Change the Secret Phrase:**

Replace with your own message:
```python
# Original phrase
"Innovation through collaboration creates lasting impact"

# Encrypt it online (or use Python):
import string
shift = 4
original = "Innovation through collaboration creates lasting impact"
encrypted = ''.join(
    chr((ord(c.lower()) - ord('a') + shift) % 26 + ord('a')) 
    if c.isalpha() else c 
    for c in original
)
print(encrypted)
```

### **Change the Cipher Type:**

- **Substitution Cipher:** Each letter maps to different letter
- **Atbash Cipher:** Reverse alphabet (A→Z, B→Y)
- **ROT13:** Classic rotation cipher
- **Vigenère:** Keyword-based encryption

### **Add Multiple Levels:**

Make users decrypt multiple messages for bonus points!

---

## 📱 Employee Communication

### **Announcement Template:**

```
🎯 NEW MISSION AVAILABLE! 🎯

Mission #2: Cipher Breaker
Difficulty: Medium
Points: 20

HQ has intercepted a scrambled AI transmission. Can you decrypt it?

Access Mission:
https://amichat.prod.amivero-solutions.com/?model=maip---week-1---challenge-2

Skills Needed:
- Pattern recognition
- Text analysis
- Cryptography basics
- Creative problem-solving

Good luck, agents! 🕵️
```

---

## 🔍 Testing Checklist

Before going live:

- [ ] Model created with correct name: `maip---week-1---challenge-2`
- [ ] Encrypted message displays correctly
- [ ] Users can request hints
- [ ] Correct answer triggers success message
- [ ] Success message includes "Mission Accomplished" (for tracking)
- [ ] Points mentioned (20 pts)
- [ ] SharePoint link is correct
- [ ] Tested in dev environment
- [ ] Exported as preset
- [ ] Ready to deploy to prod

---

## 📊 Analytics Integration

The mission analyzer will automatically detect this mission because:
- ✅ Model name matches pattern: `maip---week-1---challenge-2`
- ✅ Success message contains "Mission Accomplished"
- ✅ Will show in dashboard as "Week 1, Challenge 2"

When employees complete it:
- Dashboard shows attempts and completions
- Leaderboard updates automatically
- Conversation strategies visible
- Success rate tracked

---

## 💡 Pro Tips

1. **Test Thoroughly:** Try to decrypt it yourself first
2. **Hint Strategy:** Give hints after 3-4 failed attempts
3. **Variations:** Accept close answers (typos, punctuation)
4. **Time Limit:** Consider adding a time-based element
5. **Bonus:** Add easter eggs or bonus ciphers for extra points

---

## 🚀 Quick Deploy Steps

### **For Dev Environment:**

```bash
1. Login to: https://amichat.dev.amivero-solutions.com
2. Admin Panel → Models → Create New
3. Name: maip---week-1---challenge-2
4. Paste system prompt (see above)
5. Save
6. Test: ?model=maip---week-1---challenge-2
```

### **For Prod Environment:**

```bash
1. Test in dev first
2. Export modelfile
3. Login to: https://amichat.prod.amivero-solutions.com
4. Admin Panel → Models → Import
5. Upload modelfile
6. Announce to employees
```

---

## 📝 Alternative Encrypted Messages

Want to change the phrase? Here are alternatives:

### **Option 1: Motivational**
```
Encrypted: "Xlivi evi rs pmqmxw xs alex ai ger eglmizi xskixliv"
Decrypted: "There are no limits to what we can achieve together"
Shift: 4
```

### **Option 2: Company Values**
```
encrypted: "Eqmzivsw wxvirkxl pmiwmr syv tistpi erh mrrsrexmsr"
Decrypted: "Amiveros strength liesin our people and innovation"
Shift: 4
```

### **Option 3: Tech Focus**
```
Encrypted: "Evxmjmgmep mrxippmkirgi mqtszivw lyqer getef mpmxmiw"
Decrypted: "Artificial intelligence empowers human capabilities"
Shift: 4
```

---

## 🎓 Educational Value

This mission teaches:
- ✅ **Cryptography basics** - Understanding encryption
- ✅ **Pattern recognition** - Finding letter patterns
- ✅ **AI assistance** - Using AI tools for analysis
- ✅ **Problem-solving** - Systematic approach
- ✅ **Persistence** - Working through challenges

---

## 🔄 Next Steps

**Ready to deploy?**

1. **I can create** the exact system prompt you need
2. **Test it** in dev environment
3. **Deploy to prod** when ready
4. **Track completions** with your dashboard

**Want me to:**
- Generate different encrypted messages?
- Create system prompt with different difficulty?
- Make Mission 3, 4, 5?
- Create a mission template generator?

Let me know and I'll help you set it up! 🚀

