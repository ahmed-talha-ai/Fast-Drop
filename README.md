<div align="center">

# 🚚 FastDrop — AI-Powered Delivery Management System

### `فاست دروب — نظام توصيل ذكي`

<br/>

[![Status](https://img.shields.io/badge/Status-Active_Development-brightgreen?style=for-the-badge)](https://github.com/ahmed-talha-ai/Fast-Drop)
[![Version](https://img.shields.io/badge/API_Version-4.0.0-blue?style=for-the-badge)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![.NET](https://img.shields.io/badge/.NET_Core-10.0-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)](#)
[![Next.js](https://img.shields.io/badge/Next.js-SSR-000000?style=for-the-badge&logo=next.js&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](#)

**An enterprise-grade, bilingual (🇪🇬 Egyptian Arabic + English), AI-augmented logistics platform engineered for Egypt's delivery supply chain.**

[📖 API Documentation](#api-endpoints) • [⚙️ Setup Guide](#-how-to-run-locally) • [🤖 AI Features](#-ai--nlp-features)

</div>

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Core Features](#-core-features)
3. [Directory Structure](#-directory-structure)
4. [Database Schema](#-database-schema)
5. [API Endpoints](#-api-endpoints)
6. [AI &amp; NLP Features](#-ai--nlp-features)
7. [Technology Stack](#-technology-stack)
8. [How to Run Locally](#-how-to-run-locally)
9. [API Keys Guide](#-api-keys-guide)
10. [Database Setup](#-database-setup)
11. [Environment Variables](#-environment-variables-reference)
12. [Team](#-meet-the-team)

---

## 🎯 Project Overview

**FastDrop** is an enterprise-grade, AI-augmented delivery and logistics management platform purpose-built for Egypt's fast-growing urban delivery market. Version **4.0.0**.

The system is architected as a **three-tier platform**:

| Tier | Technology | Role |
|------|-----------|------|
| **AI Microservices** | Python 3.10+ / FastAPI (Async) | NLP Chatbot, Text-to-SQL, Multi-LLM Routing, RAG Pipeline |
| **Transactional Core** | C# 13 / .NET Core 10 Web API / EF Core | Orders, Auth, Drivers, RBAC, State Machine |
| **SSR Frontend** | Next.js (App Router) / Zustand / Shadcn UI | Role-based Dashboards — Dispatcher & Customer views |

### 🌍 Who Is It For?
FastDrop is built for **Egyptian last-mile delivery companies** that need to:
- Dispatch drivers intelligently across **25 geo-fenced Cairo zones** (GeoJSON boundary polygons)
- Let **customers track orders** and interact with support in **Egyptian Arabic dialect, Arabizi (Franco-Arabic), or English**
- Give **dispatchers & managers** instant operational analytics without writing any SQL
- Verify every delivery with **cryptographic OTP codes + photographic evidence**, eliminating disputes

### 📊 System Highlights
- **API Version:** `4.0.0` running on Uvicorn (ASGI, fully async)
- **Supported Languages:** Arabic (`ar`) — primary, English (`en`) — secondary
- **Input dialects recognized:** Egyptian Arabic dialect, Modern Standard Arabic, Franco-Arabic (Arabizi), English, and mixed language
- **Daily AI request capacity:** ~2,750 free requests/day across all LLM providers combined
- **Database tables:** 11 strongly-typed SQLAlchemy ORM models
- **Geographic coverage:** 25 Cairo delivery zones with individual pricing, capacity limits, and working hours
- **Fault Tolerance:** 4-tier LLM fallback chain ensuring near-100% chatbot availability

---

## ✨ Core Features

### 🚦 10-State Order State Machine

Every order progresses through a strictly validated lifecycle. Illegal state transitions are rejected at the API level — no order can skip steps or go backwards without explicit rules:

```
┌─────────────────────────────────────────────────────────────────┐
│  CREATED → PROCESSING → ASSIGNED → PICKED_UP → OUT_FOR_DELIVERY │
│      ↘                                                  ↙       │
│    RETURNED  ←─────────── FAILED ──────────────────────         │
│                               ↘                                 │
│                           RESCHEDULED → PROCESSING              │
│                                                  ↘              │
│                                               DELIVERED (final) │
└─────────────────────────────────────────────────────────────────┘
```

**Valid transition map (from `models.py`):**

| Current State | Allowed Next States |
|--------------|--------------------|
| `CREATED` | `PROCESSING`, `RETURNED` |
| `PROCESSING` | `ASSIGNED`, `RETURNED` |
| `ASSIGNED` | `PICKED_UP`, `RETURNED` |
| `PICKED_UP` | `OUT_FOR_DELIVERY`, `RETURNED` |
| `OUT_FOR_DELIVERY` | `DELIVERED`, `FAILED` |
| `FAILED` | `RESCHEDULED`, `RETURNED` |
| `RESCHEDULED` | `PROCESSING` |
| `DELIVERED` | *(terminal — no further transitions)* |
| `RETURNED` | *(terminal — no further transitions)* |

### 🧠 AI & NLP Integration

#### Bilingual Intent Classification
The chatbot first classifies user intent using an LLM prompt that understands **6 customer intent types** across all Egyptian Arabic forms:

| Intent | Arabic Triggers | English Triggers |
|--------|----------------|------------------|
| `track_order` | فين، وصل، تتبع، الشحنة | "where is my order", "track", "status" |
| `change_address` | عنوان، غير، بدل، تعديل | "change address", "new location" |
| `reschedule` | موعد، تأجيل، بكرة | "reschedule", "deliver tomorrow" |
| `cancel_order` | الغي، إلغاء، كنسل | "cancel", "don't want it" |
| `complaint` | اتكسر، شكوى، وحش، متأخر | "broken", "stolen", "complaint" |
| `policy_query` | بكام، رسوم، مناطق | "fees", "price", "zones", "do you deliver to" |

#### Multi-LLM Fallback Router
A rate-limit-aware routing engine automatically selects the best available provider:
```
[Request] → Groq (Llama 4 Maverick, ~500 req/day)
               ↓ rate limited?
           Gemini 2.5 Flash (~250 req/day)
               ↓ rate limited?
           HuggingFace Qwen 2.5-72B (~1000 req/day)
               ↓ rate limited?
           OpenRouter free models (emergency fallback)
```
Usage counts are tracked per-provider-per-day in the `rate_limit_counters` database table.

#### RAG Pipeline Architecture
```
[User Query (Arabic/English/Arabizi)]
        ↓
[Language Detection → langdetect]
        ↓
[Redis Semantic Cache] — cache hit? → return cached answer
        ↓ cache miss
[LlamaIndex QueryFusionRetriever]
  ├── Dense:  HuggingFace multilingual embeddings (paraphrase-multilingual-MiniLM)
  └── Sparse: BM25 lexical retrieval over knowledge base
        ↓
[Ranked context chunks from rag/knowledge_base/]
        ↓
[LLM Generation with policy context injected]
        ↓
[Bilingual Response ar/en + LangSmith trace logged]
```

#### Text-to-SQL Analytics Agent
Dispatchers describe what they need in plain language:
```
Input:  "What is the delay rate in Nasr City this week?"
SQL:    SELECT zone, COUNT(*) FILTER (WHERE status='failed') / COUNT(*) ...
Output: { "delay_rate": "23%", "zone": "Nasr City", "insight": "High congestion detected" }
```
SQL queries pass through a **schema protection layer** — only `SELECT` statements are allowed, preventing any destructive operations.

#### Driver Scoring Engine
After each delivery day, a weighted performance score is calculated per driver:
- `on_time_rate` × 0.4
- `avg_rating` × 0.3
- `(1 - complaint_rate)` × 0.2
- `delivery_success_rate` × 0.1

### 🛡️ Proof of Delivery (POD)

Every delivery closure requires **dual verification** via the `delivery_attempts` table:

1. **Photo upload** — driver takes a real-time photo at the delivery GPS location
2. **6-digit OTP** — generated server-side, sent to customer, verified at handoff
3. All fields GPS-stamped including `lat`, `lng`, `attempted_at`, and `otp_verified = True`

Failed deliveries record a `failure_reason` in Arabic for driver accountability.

### 🗺️ 25 Cairo Delivery Zones

Each `Zone` record includes:
- **Dual-language names** (`name_ar`, `name_en`) — e.g., "مدينة نصر" / "Nasr City"
- **GeoJSON polygon boundary** for precise geofencing
- **GPS center coordinates** (`center_lat`, `center_lng`)
- **Base delivery fee** (EGP), max orders/day, working hours (`09:00` – `22:00` default)
- Auto-assignment: orders geocoded to zone using polygon intersection logic

### 🤖 Telegram Bot Integration

The Telegram bot starts alongside the FastAPI server via `python-telegram-bot 21.6+`:
- Customers can send messages in **any Arabic dialect** or English
- The same RAG chatbot handles all Telegram messages
- RAG vector index is shared between the REST API and the Telegram bot via `bot_data`

---

## 📁 Directory Structure

```
Fast-Drop/
│
├── main.py                    # FastAPI application entry point (v4.0.0)
├── models.py                  # All SQLAlchemy ORM models (11 tables)
├── database.py                # Async SQLAlchemy engine + session factory
├── requirements.txt           # Python dependencies
├── seed_data.py               # Database seeder for development
├── .env                       # Environment variables (not committed)
│
├── api/                       # REST API route handlers (FastAPI routers)
│   ├── orders.py              # Order CRUD + state machine transitions
│   ├── drivers.py             # Driver management + GPS tracking
│   ├── analytics.py           # Analytics dashboard endpoints
│   ├── chat.py                # AI chatbot endpoint (RAG)
│   └── ai_endpoints.py        # Advanced AI features endpoints
│
├── ai/                        # AI logic & NLP modules
│   ├── nlp_chatbot.py         # Bilingual RAG chatbot engine
│   ├── analytics_agent.py     # Text-to-SQL NLP agent
│   ├── fallback_manager.py    # Multi-LLM rate-limited router
│   ├── smart_features.py      # AI feature orchestration
│   ├── driver_scoring.py      # Driver performance KPI engine
│   ├── clustering.py          # Zone-based order clustering (scikit-learn)
│   └── event_handler.py       # Async event processing
│
├── rag/                       # Retrieval-Augmented Generation pipeline
│   ├── build_index.py         # LlamaIndex vector + BM25 builder
│   ├── rag_cache.py           # Redis semantic cache for RAG
│   ├── knowledge_base/        # Policy documents (PDF/TXT)
│   └── index_data/            # Persisted vector index files
│
├── auth/                      # JWT Authentication
│   └── jwt.py                 # JWT login/register router + RBAC guards
│
├── core/                      # Shared utilities
│   └── zone_manager.py        # Cairo zone lookup + GeoJSON helpers
│
├── tg_bot/                    # Telegram Bot interface
│   └── bot.py                 # Telegram polling bot (python-telegram-bot)
│
└── docs/                      # Architecture diagrams
    ├── FastDrop ERD Diagram.drawio
    └── FastDrop_Class Diagram.drawio
```

---

## 🗄️ Database Schema

The system uses **11 database tables** managed via SQLAlchemy (async) ORM:

| Table                   | Description                                                         |
| ----------------------- | ------------------------------------------------------------------- |
| `users`               | Authentication accounts (`admin`, `driver`, `customer` roles) |
| `customers`           | Customer profiles with Telegram chat ID & language preference       |
| `drivers`             | Driver details, vehicle type, zone assignment, performance score    |
| `zones`               | 25 Cairo zones with GeoJSON boundaries, fees, and capacity          |
| `orders`              | Core order entity with addresses, COD amount, status, ETA           |
| `shipments`           | Batched order runs per driver with optimized route sequence         |
| `route_stops`         | Individual stops within a shipment with arrival timestamps          |
| `location_pings`      | GPS audit trail (lat/lng per driver per timestamp)                  |
| `delivery_attempts`   | POD records (OTP code, photo URL, GPS stamp, success/failure)       |
| `performance_scores`  | Daily driver KPI scores (on-time rate, rating, complaint count)     |
| `rate_limit_counters` | LLM API daily request tracking (Groq / Gemini / OpenRouter)         |

---

## 🔌 API Endpoints

> **Base URL:** `http://localhost:8000`
> **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)
> **Alternative Docs:** `http://localhost:8000/redoc`

### 🔐 Authentication (`/api/auth`)

| Method   | Path                   | Description                |
| -------- | ---------------------- | -------------------------- |
| `POST` | `/api/auth/register` | Create new user account    |
| `POST` | `/api/auth/login`    | Login → returns JWT token |
| `GET`  | `/api/auth/me`       | Get current user profile   |

### 📦 Orders (`/api/orders`)

| Method    | Path                        | Description                    |
| --------- | --------------------------- | ------------------------------ |
| `POST`  | `/api/orders`             | Create new order               |
| `GET`   | `/api/orders`             | List all orders (with filters) |
| `GET`   | `/api/orders/{id}`        | Get order details              |
| `PATCH` | `/api/orders/{id}/status` | Advance order state machine    |
| `POST`  | `/api/orders/{id}/pod`    | Submit Proof of Delivery       |

### 🚗 Drivers (`/api/drivers`)

| Method    | Path                           | Description                  |
| --------- | ------------------------------ | ---------------------------- |
| `GET`   | `/api/drivers`               | List all drivers             |
| `POST`  | `/api/drivers`               | Register new driver          |
| `PATCH` | `/api/drivers/{id}/location` | Update driver GPS location   |
| `GET`   | `/api/drivers/{id}/score`    | Get driver performance score |

### 📊 Analytics (`/api/analytics`)

| Method   | Path                       | Description                                      |
| -------- | -------------------------- | ------------------------------------------------ |
| `GET`  | `/api/analytics/summary` | Dashboard summary stats                          |
| `GET`  | `/api/analytics/zones`   | Per-zone performance metrics                     |
| `POST` | `/api/analytics/query`   | **NLP Text-to-SQL** natural language query |

### 🤖 AI Chat (`/api/chat`)

| Method   | Path          | Description                           |
| -------- | ------------- | ------------------------------------- |
| `POST` | `/api/chat` | Send message to bilingual RAG chatbot |

### 🗺️ Zones (`/api/zones`)

| Method  | Path           | Description                      |
| ------- | -------------- | -------------------------------- |
| `GET` | `/api/zones` | List all 25 Cairo delivery zones |

### 🏥 Health (`/health`)

| Method  | Path        | Description                        |
| ------- | ----------- | ---------------------------------- |
| `GET` | `/health` | Check status of DB, Redis, and RAG |

---

## 🤖 AI & NLP Features

### Multi-LLM Fallback Router

The system routes requests through multiple LLM providers based on availability and daily rate limits:

```
[User Request]
      ↓
[Groq - Llama 4 Maverick] ─── (limit: ~500 req/day)
      ↓ (if rate limited)
[Gemini 2.5 Flash] ─────────── (limit: 250 req/day)
      ↓ (if rate limited)
[HuggingFace - Qwen 2.5-72B] ─ (limit: ~1000 req/day)
      ↓ (if rate limited)
[OpenRouter - Free Models] ───── (emergency fallback)
```

### RAG Chatbot Architecture

```
[Arabic/English Query]
      ↓
[Language Detection (langdetect)]
      ↓
[LlamaIndex QueryFusionRetriever]
   ├── Dense: HuggingFace Embeddings (paraphrase-multilingual)
   └── BM25: Lexical sparse retrieval
      ↓
[Redis Semantic Cache] ←── (saves ~40% API calls)
      ↓
[LLM Generation with policy context]
      ↓
[Bilingual Response ar/en]
```

### Text-to-SQL Agent

Dispatchers query operational data in natural language:

```
Input:  "What is the delay rate in Nasr City this week?"
Output: { "sql": "SELECT ...", "result": [...], "insight": "23% delay rate..." }
```

---

## 🛠️ Technology Stack

| Layer                        | Technologies                                                                 |
| ---------------------------- | ---------------------------------------------------------------------------- |
| **AI Backend**         | Python 3.10+, FastAPI (Async), Uvicorn                                       |
| **RAG Pipeline**       | LlamaIndex 0.11+, llama-index-retrievers-bm25, HuggingFace Embeddings        |
| **LLM Providers**      | Groq, Gemini (google-generativeai), OpenAI SDK (OpenRouter), HuggingFace Hub |
| **NLP**                | langdetect, arabic-reshaper, python-bidi                                     |
| **Route Optimization** | Google OR-Tools, scikit-learn, geopy                                         |
| **Database**           | PostgreSQL (asyncpg) / SQLite (fallback), SQLAlchemy async                   |
| **Caching**            | Redis 5.0+ (semantic cache + rate limiting)                                  |
| **Auth**               | python-jose JWT, passlib/bcrypt, RBAC                                        |
| **Telegram**           | python-telegram-bot 21.6+                                                    |
| **Observability**      | LangSmith (LLM tracing)                                                      |
| **Geocoding**          | Google Maps API, OpenCage API                                                |
| **.NET Backend**       | C# 13, .NET Core 10 Web API, EF Core                                         |
| **Frontend**           | Next.js SSR (App Router), Zustand, Shadcn UI                                 |

---

## 🚀 How to Run Locally

> **Prerequisites:** Python 3.10+, Git, Redis, PostgreSQL (or use SQLite fallback)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/ahmed-talha-ai/Fast-Drop.git
cd Fast-Drop
```

### Step 2 — Create & Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and fill in your keys (see API Keys Guide below)
```

### Step 5 — Start Redis

```bash
# Option A: If Redis is installed locally
redis-server

# Option B: Using Docker (recommended)
docker run -d -p 6379:6379 --name fastdrop-redis redis
```

### Step 6 — Initialize the Database & Seed Data

```bash
# The database tables are auto-created on first startup.
# To seed with development data (zones, sample drivers):
python seed_data.py
```

### Step 7 — Start the FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 8 — (Optional) Run the Telegram Bot

```bash
# The bot starts automatically with the server.
# To run it standalone:
python -m tg_bot.bot
```

### ✅ Verify Everything is Running

Once started, check these URLs:

- **Health Check:** http://localhost:8000/health
- **Swagger UI (API Docs):** http://localhost:8000/docs
- **ReDoc UI:** http://localhost:8000/redoc
- **Zones List:** http://localhost:8000/api/zones

A successful `/health` response looks like:

```json
{
  "status": "healthy",
  "checks": {
    "api": "ok",
    "database": "ok",
    "redis": "ok",
    "rag": "ok (LlamaIndex loaded)"
  }
}
```

---

## 🔑 API Keys Guide

All keys go into your `.env` file. All providers below offer **free tiers** (except Google Maps).

### 1. Groq API Key (Primary LLM — Llama 4)

- 🌐 Go to: **[console.groq.com](https://console.groq.com)**
- Sign in with Google → Click **"API Keys"** in the sidebar → **"Create API Key"**
- Free tier: ~500 requests/day for `llama-4-maverick`
- No credit card required ✅

### 2. Gemini API Key (Analytics & Text-to-SQL)

- 🌐 Go to: **[aistudio.google.com](https://aistudio.google.com)**
- Sign in → Click **"Get API Key"** → **"Create API key"**
- Free tier: 250 requests/day for `gemini-2.5-flash`
- No credit card required ✅

### 3. HuggingFace Token (Embeddings + Fallback LLMs)

- 🌐 Go to: **[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)**
- Click **"New token"** → set role to **"Read"** → Generate
- Free tier: ~1,000 inference requests/day
- No credit card required ✅

### 4. OpenRouter API Key (Emergency Fallback)

- 🌐 Go to: **[openrouter.ai/keys](https://openrouter.ai/keys)**
- Sign up → Click **"Create Key"**
- Free models available (e.g., `gemini-2.0-flash-exp:free`)
- No credit card required ✅

### 5. Telegram Bot Token (Chat Integration)

- 📱 Open **Telegram** → search for **`@BotFather`**
- Send `/newbot` → Follow the prompts → Copy the **API token**
- Completely free, unlimited messages ✅

### 6. Google Maps API Key (Traffic & Geocoding)

- 🌐 Go to: **[console.cloud.google.com](https://console.cloud.google.com)**
- Create a project → Enable **"Maps JavaScript API"** + **"Directions API"**
- ⚠️ Requires billing enabled (10,000 requests/month free)
- **Free alternative:** Use [openrouteservice.org](https://openrouteservice.org) — 2,500 req/day, no card ✅

### 7. OpenCage API Key (Geocoding Fallback)

- 🌐 Go to: **[opencagedata.com](https://opencagedata.com)**
- Sign up free → Copy your API key from dashboard
- Free tier: 2,500 requests/day ✅

### 8. LangSmith API Key (LLM Observability/Tracing)

- 🌐 Go to: **[smith.langchain.com](https://smith.langchain.com)**
- Sign up → Go to **Settings** → **API Keys** → Create key
- Free tier available ✅

---

## 💾 Database Setup

### Option A: SQLite (Zero Config — for development)

If you **don't set** `DATABASE_URL` in your `.env`, the app automatically uses SQLite:

```bash
# No setup needed! A file `fastdrop.db` will be created automatically.
# Just start the server and the tables are auto-created.
uvicorn main:app --reload
```

### Option B: PostgreSQL (Recommended for production)

**1. Install PostgreSQL** from [postgresql.org](https://www.postgresql.org/download/)

**2. Create the database:**

```sql
-- In psql or pgAdmin:
CREATE DATABASE fastdrop;
CREATE USER fastdrop_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE fastdrop TO fastdrop_user;
```

**3. Update your `.env`:**

```env
DATABASE_URL=postgresql+asyncpg://fastdrop_user:your_password@localhost:5432/fastdrop
```

**4. Let the app auto-create tables** on first startup — no Alembic migration needed for dev:

```bash
uvicorn main:app --reload
```

**5. Seed development data:**

```bash
python seed_data.py
```

---

## 🔧 Environment Variables Reference

> **💡 Quick Start:** Copy the example file and fill in your keys:
> ```bash
> cp .env.example .env
> # Then fill in your actual API key values
> ```

The `.env.example` file in the root directory contains:
- ✅ **Placeholder values** for every variable (no real keys committed)
- 📝 **Inline comments** on each section explaining where to get the key, the free tier limits, and whether a credit card is required
- 🗄️ **Database note:** Leave `DATABASE_URL` empty to automatically use SQLite with zero configuration

> **🔒 Security:** The `.gitignore` prevents your real `.env` file from ever being pushed to GitHub.

Create your `.env` from the example above, then populate with your actual keys:


```env
# ── LLM Providers ──────────────────────────────────────
GROQ_API_KEY=gsk_...            # Primary LLM (Llama 4 Arabic)
GEMINI_API_KEY=AIza...          # Analytics + Text-to-SQL
HUGGINGFACE_API_TOKEN=hf_...    # Embeddings + fallback models
OPENROUTER_API_KEY=sk-or-v1-... # Emergency LLM fallback

# ── Telegram Bot ────────────────────────────────────────
TELEGRAM_BOT_TOKEN=1234...      # From @BotFather

# ── External APIs ───────────────────────────────────────
GOOGLE_MAPS_KEY=AIza...         # Traffic routing (optional)
OPENCAGE_API_KEY=...            # Geocoding fallback

# ── Database ────────────────────────────────────────────
# Leave blank to use SQLite (auto-created for dev)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/fastdrop

# ── Redis ───────────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ── App Config ──────────────────────────────────────────
SECRET_KEY=your-long-random-secret-key-here
DEBUG=False
DEFAULT_LANGUAGE=ar             # ar | en
SUPPORTED_LANGUAGES=ar,en
DOMAIN=localhost

# ── LangSmith (LLM Observability) ───────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=FastDrop_Production
```

---

## 👥 Meet the Team

This platform was architected and built by a specialized 4-engineer team as part of the **DEPI Round 04** Graduation Project:

| Name                                                             | Role                                                                  |
| ---------------------------------------------------------------- | --------------------------------------------------------------------- |
| **Ahmed Mohamed Abd EL Latief Talha** ⭐ *(Team Leader)* | AI Architecture, RAG Pipelines, Multi-LLM Routing, Python/FastAPI     |
| **Ahmed Mohammed Ibrahim**                                 | UI/Frontend (Next.js SSR, Zustand), Auth & Access Control             |
| **Ali Mohamed Ahmed**                                      | .NET Backend APIs, CRUD implementations, UI-Backend Integration       |
| **Khalid Mahmoud Hussein Mahmoud**                         | Database schema design, SQL optimization, Geospatial mapping, EF Core |

---

## 📜 Project Milestones

| Phase             | Timeline     | Description                                                             |
| ----------------- | ------------ | ----------------------------------------------------------------------- |
| **Phase 1** | Weeks 1–3   | ERD Design, 10-State Architecture Blueprinting, 25-Zone GeoJSON mapping |
| **Phase 2** | Weeks 4–6   | .NET Core 10 Backend, JWT/RBAC Auth, EF Core schema implementation      |
| **Phase 3** | Weeks 7–9   | Python AI microservices — RAG, Text-to-SQL, Multi-LLM routing          |
| **Phase 4** | Weeks 10–12 | Next.js SSR frontend, Zustand state management, API wiring              |
| **Phase 5** | June 2026    | End-to-End QA, SQL optimization, load testing, final presentation       |

---

<div align="center">

**Made with ❤️ in Egypt 🇪🇬 | DEPI Round 04 Graduation Project**

</div>
