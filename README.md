<div align="center">

<!-- LOGO -->
<p align="center">
  <img src="docs/images/logo.png" alt="VSF Merchant AI Logo" width="110" style="border-radius: 24px; box-shadow: 0 8px 32px rgba(16, 185, 129, 0.25);" />
</p>

# 🍽️ Merchant Management AI
### *Multi-Agent Copilot Platform for F&B Merchants*

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.12%2B-blue?logo=python&logoColor=white" alt="Python" /></a>
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI" /></a>
  <a href="https://reactjs.org/"><img src="https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black" alt="React" /></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-18%20%2B%20pgvector-336791?logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="https://crewai.com"><img src="https://img.shields.io/badge/Multi--Agent-CrewAI-FF4B4B?logo=ai&logoColor=white" alt="CrewAI" /></a>
  <a href="https://langfuse.com"><img src="https://img.shields.io/badge/Observability-Langfuse-orange?logo=apachespark&logoColor=white" alt="Langfuse" /></a>
  <a href="https://mem0.ai"><img src="https://img.shields.io/badge/Memory-Mem0%20(pgvector)-8A2BE2" alt="Mem0" /></a>
  <a href="https://h3geo.org"><img src="https://img.shields.io/badge/H3-Geo" alt="Mem0" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" /></a>

</p>

<p align="center">
  <a href="#-key-features"><b>Key Features</b></a> •
  <a href="#-architecture"><b>Architecture</b></a> •
  <a href="#-video-demo--preview"><b>Demo Preview</b></a> •
  <a href="#-memory--hybrid-rag-engine"><b>Memory & RAG</b></a> •
  <a href="#-observability--evaluation"><b>Observability</b></a> •
  <a href="#-quick-start"><b>Quick Start</b></a> •
  <a href="#-tech-stack"><b>Tech Stack</b></a>
</p>

---

</div>

## About

**Merchant Management AI** is an enterprise-grade agentic assistant tailored for restaurant & F&B owners on the platform. 

Instead of navigating fragmented dashboards and lengthy policy documents, merchants can query operational metrics, competitor market dynamics, menu optimization suggestions, customer reviews, and official platform policies using natural language with **Multi Agentic AI** and **Personalized Memory**.

---

## Preview

<!-- DEMO VIDEO / GIF PLACEHOLDER
<div align="center">
  <table>
    <tr>
      <td align="center">
        <a href="#-video-demo--preview">
          <br />
          <em>🎥 Click here or embed demo video: <code>docs/demo_preview.mp4</code></em>
        </a>
      </td>
    </tr>
  </table>
</div> -->


<div align="center">
  <table style="border: none; border-collapse: collapse;">
    <tr>
      <td width="500px" style="border: none; padding: 0;">
        <img src="docs/images/chatbot.png" alt="Interactive Copilot" />
        <p align="center"><b>🤖 Real-time Streaming Copilot & Grounded Cards</b></p>
      </td>
      <td width="500px" style="border: none; padding: 0;">
        <img src="docs/images/reviews.png" alt="Customer Sentiment" />
        <p align="center"><b>📊 Review & Sentiment Analytics</b></p>
      </td>
      <td width="500px" style="border: none; padding: 0;">
        <img src="docs/images/documents.png" alt="Policy RAG" />
        <p align="center"><b>📜 Policy RAG with Source Citations</b></p>
      </td>
      <td width="500px" style="border: none; padding: 0;">
        <img src="docs/images/menu.png" alt="Menu Intelligence" />
        <p align="center"><b>🍲 Menu Catalog & Competitor Pricing</b></p>
      </td>
    </tr>
  </table>
</div>

---

## Key Features

| Capability | What It Solves | Value Delivered |
| :--- | :--- | :--- |
| **🔍 Market & Competitor Discovery** | *"Which sushi stores compete with me in a 3km radius?"* | Spatial Haversine search, pricing tier comparison & customer segment mapping. |
| **📈 Owner Diagnosis & Metrics** | *"Evaluate my store's operational performance this week."* | Pre-computed scoring, cancel rate analysis, prep time audits, and actionable growth tips. |
| **💬 Review & Sentiment Analysis** | *"What are the most frequent complaints from customers recently?"* | Aspect-based sentiment analysis, negative topic clustering & driver feedback integration. |
| **📑 Hybrid Policy RAG** | *"What are the qualification terms for merchant promotions?"* | BM25 + Dense Vector + Reciprocal Rank Fusion (RRF) on official XanhSM policy guidelines. |
| **⚡ Native Async Streaming** | Eliminates 40–90s blocking orchestration latency. | Direct SSE token emission with **Time-To-First-Token < 1.5s**. |
| **🧠 Personalized Long-Term Memory** | Remembers store preferences, tone, and past discussions. | Entity graph-driven memory powered by self-hosted **Mem0** on pgvector. |

---

## Agentic Architecture

The system implements a **Planner-Specialist-Synthesis** multi-agent design with run-scoped tool isolation and asynchronous Server-Sent Events (SSE).

<p align="center">
  <img src="docs/images/Agentic_Architecture.png" alt="Agentic Architecture" width="600px" />
</p>

### Agent Roles & Workflows

1. **Planner (`PlannerRespond` vs `PlannerDelegate`)**: Evaluates query complexity in $<1.5\text{s}$. If conversational, streams directly; if analytical, constructs a targeted delegation plan.
2. **Run-Scoped Tool Gateway (`RunScopedMerchantToolGateway`)**: Enforces strict privilege boundaries per specialist. Prevents tool misuse, scrubs sensitive IDs, and outputs **Compact Projections** to reduce LLM input tokens by $>70\%$.
3. **Synthesis Engine**: Formats grounded observations into clean, structured Markdown while syncing interactive Merchant Cards to the frontend.

---

## Memory & Hybrid RAG Engine

### 1. Semantic Long-term Memory (Mem0 + pgvector)
Instead of feeding full conversation transcripts into LLM context, the platform utilizes **Mem0** backed by PostgreSQL `pgvector`:
- Extracts persistent merchant preferences, tone customizations, and key operational entities.
- Automatically queries the top **3–5 semantic memories** in the background ($<100\text{ms}$).
- Submits conversation memories asynchronously without delaying user response.

<div align="center">
  <img src="docs/images/Memory_Context_View.png" alt="Mem0 Memory View" width="800px" />
</div>

---

### 2. Hybrid Policy RAG (BM25 + Dense Vectors + RRF)

To guarantee 100% compliance with platform regulations:
- **Structural Chunking**: 1,024-token chunks with 64-token overlap, preserving hierarchical headings.
- **Dense Embedding**: `BAAI/bge-small-en-v1.5` (384 dimensions) indexed in pgvector.
- **Hybrid Fusion**: Merges Top-20 BM25 lexical results and Top-20 Dense Vector cosine scores via **Reciprocal Rank Fusion (RRF)**.
- **Evidence Hydration**: Top 5 ranked chunks are hydrated with source URLs, section titles, and effective dates.

<div align="center">
  <img src="docs/images/Retrieval_Pipeline.png" alt="Retrieval Pipeline" width="800px" />
</div>

---

## Observability & Evaluation

Integrated with **Langfuse** for enterprise observability and continuous automated evaluation:

<div align="center">
  <img src="docs/images/Trace_View.png" alt="Langfuse Tracing" width="600px" />
</div>

* **Full Trace Lifecycle**: Tracks TTFT (Time-To-First-Token), total latency, tool calls, token usage, and prompt versioning.
* **LLM-as-Judge & Automated Evaluation**:
  * **Multi-Agent Routing Accuracy**: **88.9%** passed across 25 gold standard testcases.
  * **Policy RAG Grounding**: **100%** accuracy across 20 compliance cases.
  * **Memory Preference Recall**: **83%** relevance.
  * **Jailbreak / Prompt Injection Defense**: **75%** pass rate.

<div align="center">
  <img src="docs/images/Eval_View.png" alt="Evaluation Dashboard" width="600px" />
</div>

---

## Tech Stack

| Category | Technologies |
| :--- | :--- |
| **Backend & API** | [Python 3.12+](https://python.org), [FastAPI](https://fastapi.tiangolo.com), [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [Uvicorn](https://www.uvicorn.org/) |
| **Database & Vector** | [PostgreSQL 18](https://www.postgresql.org/), [pgvector](https://github.com/pgvector/pgvector), Native Haversine Spatial PL/pgSQL |
| **Agentic & LLM** | [CrewAI](https://crewai.com), [Instructor](https://github.com/jxnl/instructor), [OpenAI / vLLM](https://vllm.ai), [LlamaIndex](https://www.llamaindex.ai/) |
| **Memory & Observability** | [Mem0](https://mem0.ai), [Langfuse OTel Tracing](https://langfuse.com) |
| **Frontend & UI** | [React 18](https://reactjs.org), [Vite](https://vitejs.dev), [TypeScript](https://www.typescriptlang.org/), [TailwindCSS](https://tailwindcss.com) |
| **DevOps & Testing** | [Docker Compose](https://docs.docker.com/compose/), [Pytest](https://pytest.org) (148 tests), [Vitest](https://vitest.dev) |

---

## 📁 Repository Structure

```text
├── backend/                       # FastAPI Core & Multi-Agent Architecture
│   ├── agents/merchant/           # Planner, Capability Specialists & Synthesis
│   ├── core/                      # LLM Tracing, Settings & Global Configurations
│   ├── database/                  # PostgreSQL Connection & SQLAlchemy Models
│   ├── flows/                     # MerchantFlowDispatcher & Native Async Streaming
│   ├── migrations/                # Alembic Database Migrations
│   ├── routes/                    # API Endpoints (Chat, Stream, Metrics, Health)
│   ├── services/                  # Mem0, Policy RAG, ChatSession & Prompts
│   ├── tools/merchant/            # RunScoped Tool Gateway & Specialized Tools
│   └── tests/                     # Comprehensive Unit & Integration Test Suites
├── frontend/                      # Modern React + Vite Web Client
│   ├── src/merchant/components/   # Chat Interface, Thinking Accordion, Merchant Cards
│   └── src/merchant/hooks/        # useMerchantChat (Native SSE Stream Processor)
├── docs/                          # Architecture Diagrams, Benchmarks & Sprint Specs
├── docker-compose.yml             # Containerized PostgreSQL 18 + pgvector
├── Makefile                       # One-Click Development & Testing Commands
└── README.md                      # Project Documentation
```

---

## 🚀 Quick Start

### 1. Prerequisites
- [Docker & Docker Compose](https://www.docker.com/)
- [Python 3.12+](https://python.org)
- [Node.js 18+](https://nodejs.org)

### 2. Clone & Environment Setup
```bash
# Clone the repository
git clone https://github.com/minhnvm2307/Merchant_Agentic_Assistant.git
cd Merchant_Agentic_Assistant

# Copy environment template
cp .env.example .env
```

Configure the following variables in `.env`:
```env
# Database & Vector
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=merchant_platform
DB_HOST=localhost
DB_PORT=5432

# LLM & Agent Configuration
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o-mini

# Langfuse Observability
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Launch Services

```bash
# Step 1: Start PostgreSQL + pgvector container
docker compose up -d

# Step 2: Run Database Migrations
cd backend
python -m alembic upgrade head
cd ..

# Step 3: Start Backend & Frontend Dev Servers (Concurrent)
make dev
# Or run individually:
# make dev-backend   -> http://localhost:8000
# make dev-frontend  -> http://localhost:5173
```

### 4. Running Test Suites
```bash
# Run all backend unit tests (148 tests)
pytest backend/tests/unit/

# Run frontend tests
cd frontend && npm test
```

---

## Roadmap

- [x] **Sprint 1**: Database schema design, Spatial Haversine search & core CRUD APIs.
- [x] **Sprint 2**: Multi-Agent orchestration with CrewAI, Tool Gateway & Langfuse integration.
- [x] **Sprint 3**: Mem0 Long-term Memory, Hybrid Policy RAG (RRF), Native Async Token Streaming ($<1.5\text{s}$ TTFT).