# PondySevAi Backend — Phase 2

**FastAPI backend for the PondySevAi civic volunteer platform.**
An Initiative by Decision Minds · For the Government of Puducherry.

---

## Setup

### 1. Clone and install

```bash
cd pondysevai-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in Supabase, Anthropic, Twilio keys
```

### 3. Set up Supabase database

1. Go to **supabase.com** → create a free project
2. Open the **SQL Editor** tab
3. Paste the entire contents of `supabase_schema.sql` and click **Run**
4. Copy your **Project URL** and **service_role key** into `.env`

### 4. Run locally

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for the interactive API explorer.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/otp/send` | Send OTP to volunteer phone |
| POST | `/auth/otp/verify` | Verify OTP, get JWT |
| POST | `/auth/staff/login` | Nodal officer login |
| POST | `/auth/admin/login` | Admin login |
| POST | `/volunteers/register` | Register new volunteer |
| GET | `/volunteers/me` | My profile (volunteer) |
| GET | `/volunteers/` | List all volunteers (officer/admin) |
| PATCH | `/volunteers/{id}` | Update volunteer (officer/admin) |
| GET | `/roles/` | List all roles |
| GET | `/roles/departments` | List departments |
| POST | `/deployments/` | Create deployment (officer) |
| GET | `/deployments/my` | My deployments (volunteer) |
| POST | `/deployments/checkin` | QR check-in/out |
| POST | `/deployments/feedback` | Submit feedback (officer) |
| GET | `/certificates/download/{id}` | Download PDF certificate |
| GET | `/certificates/verify/{cert_id}` | Verify certificate (public) |
| GET | `/nodal-officer/applicants` | All applicants with AI scores |
| POST | `/nodal-officer/assign/{id}` | Assign volunteer to role |
| POST | `/nodal-officer/reject/{id}` | Reject application |
| POST | `/nodal-officer/bulk-sms` | Send bulk SMS |
| GET | `/nodal-officer/export/csv` | Export volunteer CSV |
| GET | `/nodal-officer/stats` | Dashboard stats |

---

## Deploy to Railway

1. Go to **railway.app** → New Project → Deploy from GitHub
2. Select your `pondysevai-backend` repo
3. Add all environment variables from `.env.example` in Railway's Variables tab
4. Railway auto-detects `railway.toml` and deploys

---

## Connecting Frontend to Backend

In your Next.js frontend, add to `.env.local`:

```
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

Then update `lib/api.ts` to use `process.env.NEXT_PUBLIC_API_URL`.

---

## Phase 2 Deliverables

- [x] FastAPI backend with all REST endpoints
- [x] Supabase PostgreSQL schema (volunteers, roles, deployments, feedback, certificates)
- [x] OTP authentication (Supabase Auth + Twilio SMS fallback)
- [x] JWT session management (volunteer / nodal officer / admin roles)
- [x] AI matching service — MiniLM Layer 1 + Claude API Layer 2
- [x] Certificate generation — QR-verifiable PDF via reportlab
- [x] Notification service — SMS + WhatsApp (EN/TA/FR templates)
- [x] Nodal officer endpoints — assign, reject, bulk SMS, CSV export
- [x] Tier calculation engine (bronze/silver/gold/platinum)
- [x] QR check-in/check-out for deployments
- [x] Feedback system (top_performer / performer / regular)
- [x] Rate limiting (slowapi)
- [x] CORS configured for frontend
- [x] Railway deployment config (railway.toml, Procfile)
- [x] Full Supabase schema with RLS, indexes, triggers

Prepared by: Dharshini.N — Intern, Decision Minds AI Incubation Center
