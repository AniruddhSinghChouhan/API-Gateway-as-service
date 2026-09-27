AI Gateway-as-a-Service (LLM Router & Multi-Provider Proxy)
Enterprise-grade AI Gateway with intelligent multi-provider routing (Groq, OpenAI, Anthropic, Gemini), budget caps, token quotas, exact match (<5ms) & semantic caching, rate limiting, guardrails, and Next.js observability dashboard.

🚀 Instant Quickstart (Currently Running!)
The project is already running in background processes on your machine:

Dashboard UI: http://localhost:3000
API Gateway: http://localhost:8000
Swagger Interactive API Docs: http://localhost:8000/docs
Health Check: http://localhost:8000/health
🛠️ How to Run the Project Locally (Terminal / PowerShell)
If you ever restart your machine or want to run the services in separate terminal windows:

Terminal 1: Run the Backend Gateway (FastAPI)
Open PowerShell and navigate to the gateway folder:

cd "c:\Users\aniru\OneDrive\Desktop\project\API\ai-gateway\gateway"
(Optional if already installed) Install Python dependencies:

python -m pip install -r requirements.txt
Start the Gateway server:

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
The gateway will automatically initialize gateway.db with default organizations, master virtual keys, and sample telemetry.

Terminal 2: Run the Frontend Dashboard (Next.js)
Open a second PowerShell window and navigate to the dashboard folder:

cd "c:\Users\aniru\OneDrive\Desktop\project\API\ai-gateway\dashboard"
Start the Next.js development server:

npm.cmd run dev
(Or for production mode: npm.cmd run build followed by npm.cmd start)

Open your browser at:

http://localhost:3000
🐳 How to Run with Docker Compose
If you have Docker Desktop running:

cd "c:\Users\aniru\OneDrive\Desktop\project\API\ai-gateway"

# Start all 5 services (PostgreSQL + pgvector, Redis, ClickHouse, Gateway, Dashboard)
docker compose up -d

# View logs
docker compose logs -f
🔑 Pre-Configured Virtual Keys
Your gateway comes pre-seeded with ready-to-use virtual keys:

Key Name	Secret Key	Budget Cap	Rate Limit
Production Master Key	gw-live-master-enterprise-key-2026	$1,000.00 / 10M tokens	300 RPM
Sandbox Dev Key	gw-live-developer-sandbox-key-789	$25.00 / 500k tokens	60 RPM
🧪 Testing Chat Completions (OpenAI Compatible)
You can call the gateway using any OpenAI SDK or direct cURL:

cURL (PowerShell / Bash)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer gw-live-master-enterprise-key-2026" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "messages": [
      {"role": "user", "content": "Explain AI Gateways in 2 sentences."}
    ],
    "temperature": 0.7
  }'
Python OpenAI SDK
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="gw-live-master-enterprise-key-2026"
)

response = client.chat.completions.create(
    model="openai/gpt-oss-20b", # or "cost-optimized", "latency-optimized"
    messages=[{"role": "user", "content": "Hello AI Gateway!"}],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)
