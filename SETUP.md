# 🚀 AI Social Media Manager — Setup Guide

## What You Need (Free accounts, takes 10 minutes)

| Service | Why | Free? |
|---|---|---|
| [Supabase](https://supabase.com) | Database + Storage | ✅ Yes |
| [Groq](https://console.groq.com) | AI text generation | ✅ Yes |
| [Gemini](https://aistudio.google.com) | AI image generation | ✅ Yes |
| LinkedIn Developer App | Publishing to LinkedIn | Requires approval |
| Instagram Graph API | Publishing to Instagram | Requires Business account |

---

## Step 1: Supabase Setup (3 minutes)

1. Go to [supabase.com](https://supabase.com) → **Sign Up** (free)
2. Click **"New Project"**
   - Name: `ai-social-manager`
   - Database password: Save this somewhere safe!
   - Region: Choose closest to you
3. Wait ~60 seconds for project to be ready
4. Go to **Settings → API**
5. Copy:
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **anon public** key
   - **service_role** key (click to reveal)
6. Go to **SQL Editor** → Paste the entire contents of `backend/schema.sql` → Click **Run**
7. You should see `Schema created successfully! ✅`

---

## Step 2: Get AI API Keys

### Groq (text generation)
1. Go to [console.groq.com](https://console.groq.com) → Create account
2. Click **API Keys** → **Create API Key**
3. Copy the key (starts with `gsk_`)

### Gemini (image generation)
1. Go to [aistudio.google.com](https://aistudio.google.com) → Sign in with Google
2. Click **Get API Key** → **Create API Key**
3. Copy the key (starts with `AIza`)

---

## Step 3: Configure Environment Variables

### Backend
```bash
cp backend/.env.example backend/.env
```
Open `backend/.env` and fill in:
```
DATABASE_URL=postgresql+asyncpg://postgres:[YOUR-DB-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
SECRET_KEY=run-python3-secrets-token-hex-32-to-generate-this
ENCRYPTION_KEY=run-python3-secrets-token-urlsafe-32-to-generate-this

SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
SUPABASE_SERVICE_KEY=[your-service-role-key]
```

### Frontend
```bash
cp frontend/.env.example frontend/.env
```
Open `frontend/.env`:
```
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://[YOUR-PROJECT-REF].supabase.co
VITE_SUPABASE_ANON_KEY=[your-anon-key]
```

---

## Step 4: Generate Secrets

Run these commands to generate secure secrets:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))" # ENCRYPTION_KEY
```

---

## Step 5: Install and Run Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend will be running at: **http://localhost:8000**
API Docs: **http://localhost:8000/api/docs**

---

## Step 6: Install and Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be running at: **http://localhost:5173**

---

## Step 7: First Time Setup in the App

1. Open http://localhost:5173
2. Click **"Create one free"** → Register your account
3. Go to **Brand Profile** → Fill in your company info
4. Go to **API Keys** → Add your Groq and Gemini keys
5. Go to **Content Planner** → Add some topics
6. Go to **AI Generator** → Generate your first post!
7. (Optional) Go to **Scheduler** → Enable automation

---

## Generating ENCRYPTION_KEY correctly

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())  # Use this as ENCRYPTION_KEY
```

---

## LinkedIn & Instagram (Optional for now)

These require approved developer apps. For initial testing, you can:
1. Generate posts without connecting social accounts
2. Manually copy the caption and post it yourself
3. Add LinkedIn/Instagram credentials when ready

For LinkedIn: [developers.linkedin.com](https://developer.linkedin.com)
For Instagram: [developers.facebook.com](https://developers.facebook.com)

---

## Project Structure

```
ai sheduler/
├── frontend/         # React + TypeScript + Tailwind
│   └── src/
│       ├── pages/    # All 10 pages
│       ├── components/
│       ├── providers/
│       └── lib/
└── backend/          # Python + FastAPI
    ├── app/
    │   ├── api/      # All route files
    │   ├── models/   # Database models
    │   ├── services/ # AI + Social + Key Rotation
    │   └── scheduler/# APScheduler
    └── schema.sql    # Paste into Supabase
```

---

## Need Help?

- Backend API docs: http://localhost:8000/api/docs
- Check terminal for error messages
- Make sure your API keys are correct (use "Test All" in API Keys page)
