# Enterprise RAG Agent: From Cloud Infrastructure to AI

This project demonstrates a complete, end-to-end AI pipeline. It doesn't just ask a Large Language Model a question; it automates the creation of a cloud database, securely stores private company knowledge, and gives an AI agent the tools to search that database while tracking its own performance.

## The Overall Flow

Here is exactly how the system works, step-by-step:

### 1. The Vault (Security First)
Before anything runs, all passwords, API keys, and access tokens are locked away in hidden files (`.env` and `terraform.tfvars`). This ensures no sensitive data is ever uploaded to GitHub.

### 2. Building the Cloud (Terraform)
Instead of manually clicking through a website to rent a database, this project uses **Terraform** (Infrastructure as Code). Terraform reads a blueprint file (`main.tf`), securely logs into Supabase, and automatically builds a live PostgreSQL database in seconds.

### 3. Creating the Brain (Knowledge Seeding)
AI models don't naturally know private company information. A Python script (`seed_db.py`) takes mock internal company documents, slices them into small, readable paragraphs, and saves them directly into the newly built cloud database.

### 4. The Smart Agent (LangGraph)
The main script (`agent.py`) acts as an autonomous worker. When asked a question, it uses a "Reason and Act" loop:
* **Reason:** It realizes it doesn't know the answer off the top of its head.
* **Act:** It uses a custom tool to connect to our Supabase database, search for keywords, and pull the exact documentation needed.
* **Answer:** It reads the pulled data and generates a highly accurate, company-specific response using Google's Gemini model.

### 5. The Stopwatch (Observability)
In the real world, you need to know if an app is slow because of the database or the AI. The agent is wrapped in **OpenTelemetry**. Every time it answers a question, it prints a raw JSON trace to the terminal showing exactly how many milliseconds the database took versus how long the AI took to think.

---

## How to Run This Project

**1. Secure Your Secrets**
* Create a `.env` file for Python to hold your `GOOGLE_API_KEY` and `SUPABASE_DB_URL`.
* Create a `terraform.tfvars` file for Terraform to hold your Supabase Access Token, Org ID, and Database Password.

**2. Deploy the Database**
```bash
terraform init
terraform apply
```

**3. Install Dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install langchain langchain-google-genai psycopg2-binary langgraph opentelemetry-api opentelemetry-sdk python-dotenv
```

**4. Seed the Data**
```bash
python seed_db.py
```

**5. Run the Traced AI Agent**
```bash
python agent.py
```


## Acknowledgements & References

* **Architecture:** Built to demonstrate modern, production-grade AI infrastructure, bridging the gap between cloud provisioning (Terraform) and autonomous AI (LangGraph).
* **AI Assistance:** Portions of the code and documentation in this repository were pair-programmed and refined using Google Gemini. AI was leveraged to accelerate development, troubleshoot cloud networking protocols, and structure the OpenTelemetry tracing framework.