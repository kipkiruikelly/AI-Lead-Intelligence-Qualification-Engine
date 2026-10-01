# Design Decisions

This document outlines the core architectural and implementation decisions made during the development of the **AI-Powered Lead Intelligence & Qualification Engine**.

---

## 1. Why Python?
Python was chosen for its rich ecosystem in data processing (`pandas`), schema validation (`pydantic`), HTTP scraping (`requests`, `beautifulsoup4`), and LLM API integrations (`google-genai`, `openai`). It allows rapid iteration while keeping the pipeline clean, readable, and easy to run locally without build tools or complex compilation.

---

## 2. Why SQLite for Storage?
For an assessment prototype processing 25–30 leads per run, an embedded SQLite database (`output/leads_repository.db`) offers zero-configuration local persistence, full relational querying, and ACID guarantees without needing external database services like PostgreSQL or Docker containers.

---

## 3. Why Deterministic Scoring Instead of LLM Scoring?
Scoring is calculated using a 100% rule-based engine (`pipeline/scorer.py`) evaluating 6 objective factors (Size, Sector Risk, Digital Exposure, Operational Complexity, Regulatory Sensitivity, and Bonus Signals).

**Rationale**:
- **Reproducibility**: The same evidence always yields the exact same opportunity score (0–100) and priority level.
- **Auditability**: Sales teams can inspect the exact point breakdown (`size_score`, `sector_score`, `exposure_score`, etc.).
- **Cost Efficiency**: Eliminates LLM API calls for pure numerical evaluation.

---

## 4. Why Separate Discovery and Enrichment?
Discovery (`pipeline/discoverer.py`) focuses on finding candidate company URLs, whereas Enrichment (`pipeline/enricher.py`) fetches, scrapes, and parses individual websites for evidence. 

**Rationale**:
Separating candidate discovery from web scraping allows swapping discovery mechanisms (e.g., live DuckDuckGo query parsing vs. static seed file vs. Apollo.io API) without altering web research or evidence parsing logic.

---

## 5. Why Evidence and Provenance Controls?
Every extracted signal is tagged with a source URL, retrieval timestamp (ISO 8601 UTC), and reliability label (`Verified`, `Inferred`, or `Unknown`).

**Rationale**:
Cybersecurity outreach requires high trust. Explicit provenance allows sales reps to verify where claims originated before sending messages to executive prospects.

---

## 6. Why Pydantic v2 for Validation?
Pydantic (`schemas/lead_schema.py`) acts as a strict validation gate (`pipeline/validator.py`) before outputs are persisted or written to CSV/HTML.

**Rationale**:
LLM outputs can occasionally leak unparsed JSON formatting, missing fields, or invalid data types. Pydantic guarantees that only fully schema-compliant records pass to storage, routing invalid outputs to `output/review_queue.json` rather than failing silently.

---

## 7. Why Not Fabricate Decision-Maker Names?
If an individual executive's name is not explicitly confirmed in scraped web evidence, the system sets `name: "Not verified"` and provides a `recommended_role` (e.g., `CIO / IT Director / Information Security Lead`).

**Rationale**:
Inventing fake contact names severely damages outbound sales credibility. A verified target role is vastly superior to a hallucinated executive name.

---

## 8. Why Use an LLM at All?
While scoring and validation are deterministic, the LLM (`pipeline/llm_client.py`) is used strictly for tasks where natural language synthesis excels:
- Synthesizing unstructured web text into concise **business observations**.
- Generating clear **qualification explanations**.
- Writing tailored, non-generic **personalized outreach messages** based on legitimate company evidence.

---

## 9. Why Have Fallback Providers?
Search engines and external websites frequently rate-limit, block, or time out when queried repeatedly from residential IP addresses.

**Rationale**:
The system includes resourced fallback pools (e.g. 30 Kenyan target companies across 7 industries) and `llm_unavailable` state handling so that network blocks or API quota limits do not crash the pipeline or force fake data generation.

---

## 10. What Would Change in Production?
If deploying this system into a full production SaaS environment, the following upgrades would be made:
- **Dedicated Discovery API**: Replace web query parsing with Apollo.io, Hunter.io, or SerpAPI for structured lead finding.
- **Asynchronous Task Queue**: Use Celery / Redis or Temporal to process leads concurrently rather than sequentially.
- **Production Database**: Migrate SQLite to PostgreSQL or Supabase for multi-tenant concurrent access.
- **Paid Infrastructure**: Use paid Gemini/OpenAI API tiers and dedicated proxy pools for scraping.

---

## 11. What Was Deliberately Left Out?
To stay focused on the core engineering of an automated AI qualification engine within the 6–8 hour technical assessment scope, the following were intentionally excluded:
- User authentication / JWT tokens.
- Full React/Next.js web application frontend.
- Microservice container orchestration (Kubernetes/Docker Compose).
- Third-party CRM synchronization (HubSpot/Salesforce API integrations).

---

## 12. Main Operational Limitation
- **LLM API Quota**: Real LLM structured analysis relies on outbound internet connectivity and available daily quota on `GEMINI_API_KEY`. When unconfigured or depleted, the system safely operates in deterministic mode (`pipeline_status: llm_unavailable`).
