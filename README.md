# AI-Powered Lead Intelligence & Qualification Engine

**Prototype submission for the AI Engineering & Automation Technical Assessment**

A fully runnable end-to-end Python pipeline that discovers, researches, scores, analyses, and generates personalised outreach for cybersecurity consulting prospects.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run (no API key needed — deterministic mode)
python main.py --skip-llm --skip-website-check

# 4. Run with LLM synthesis (set one of these first)
export GEMINI_API_KEY="your-key-here"
# or: export OPENAI_API_KEY="your-key-here"
python main.py

# 5. View outputs
open output/dashboard.html         # Interactive HTML dashboard
open output/leads_output.csv       # Flat CSV for spreadsheets
```

---

## Pipeline Architecture

```
config.yaml  ──────────────────────────────────────────────────────────────────
    │  (industries, geography, employee range, score thresholds, LLM provider)
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Step 1  LEAD DISCOVERY  (pipeline/discoverer.py)                           │
│  Loads data/seed_companies.json → applies config filters                    │
│  Production: SerpAPI / Apollo / Hunter API call                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ 25-30 matched companies
┌──────────────────────────────────▼──────────────────────────────────────────┐
│  Step 2  COMPANY RESEARCH & ENRICHMENT  (pipeline/enricher.py)              │
│  Website reachability check (HTTP HEAD)                                     │
│  Evidence normalisation: Verified / Inferred / Unknown                      │
│  Decision-maker defaults (never invented)                                   │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ enriched + tagged evidence
┌──────────────────────────────────▼──────────────────────────────────────────┐
│  Step 3  DETERMINISTIC SCORING  (pipeline/scorer.py)  ← NO LLM             │
│  size_score (0-20) + sector_score (0-25) + exposure_score (0-25)            │
│  + complexity_score (0-10) + regulatory_score (0-10) + bonus (0-10)        │
│  → opportunity_score (0-100) → High / Medium / Low Priority                 │
└────────────────────────┬────────────────────────────────────────────────────┘
                         │ scored company dict
          ┌──────────────▼──────────────┐
          │  LLM enabled?               │
          │  (env var check)            │
          └────┬────────────┬───────────┘
             YES            NO
┌────────────▼───────────┐  ┌──────────────────────────────┐
│  Step 4a  LLM ANALYSIS │  │  Step 4b  DETERMINISTIC STUB │
│  llm_client.py         │  │  llm_client._build_stub()    │
│  Gemini / OpenAI       │  │  No hallucination risk       │
│  Evidence-only prompt  │  │  No API cost                 │
│  tenacity retries (3x) │  └──────────────────────────────┘
│  JSON extraction       │              │
│  → explanation         │              │
│  → observations        │              │
│  → outreach message    │              │
└────────────┬───────────┘              │
             └──────────────┬───────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│  Step 5  VALIDATION GATE  (pipeline/validator.py)                           │
│  Pydantic v2 LeadRecord model                                               │
│  Coercion of trivial type mismatches                                        │
│  Failures → review_queue.json (not silently accepted or discarded)         │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ List[LeadRecord]
┌───────────────────────────▼─────────────────────────────────────────────────┐
│  Step 10  OUTPUT  (pipeline/output_writer.py)                               │
│  output/leads_output.csv    — flat CSV, all fields                          │
│  output/leads_output.json   — full JSON including evidence arrays           │
│  output/dashboard.html      — self-contained interactive HTML               │
│  output/review_queue.json   — validation failures for human review          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
AI_Lead_Intelligence_Assessment_Prototype/
├── main.py                         # CLI orchestrator — run this
├── config.yaml                     # All targeting & scoring configuration
├── requirements.txt
│
├── pipeline/
│   ├── discoverer.py               # Step 1: load seed data, apply filters
│   ├── enricher.py                 # Step 2: website check, evidence tagging
│   ├── scorer.py                   # Step 3: deterministic scoring formula
│   ├── llm_client.py               # Step 4: Gemini/OpenAI with retry + fallback
│   ├── validator.py                # Step 5: Pydantic validation gate
│   └── output_writer.py            # Step 10: CSV, JSON, HTML dashboard
│
├── schemas/
│   └── lead_schema.py              # Pydantic v2 models (shared contract)
│
├── data/
│   └── seed_companies.json         # 30 pre-researched Nairobi companies
│
├── prompts/
│   ├── system_prompt.txt           # Hardened LLM rules (no fabrication)
│   └── analysis_prompt_template.txt # Per-lead evidence injection template
│
├── output/                         # Generated on first run
│   ├── leads_output.csv
│   ├── leads_output.json
│   ├── dashboard.html
│   └── review_queue.json
│
└── llm_output_schema.json          # JSON schema reference (documentation)
```

---

## Scoring Model (Deterministic — No LLM)

All scoring is done in `pipeline/scorer.py` using objective rules. The LLM cannot change the score.

| Factor | Max | Rule |
|--------|-----|------|
| **Size band** | 20 | 51-200 employees → 15pts; 201-500 → 20pts |
| **Sector risk** | 25 | Banking/Finance/Health → 25; Tech/Telecom → 18-20; Logistics → 12; Hospitality → 10 |
| **Digital exposure** | 25 | +5pts per detected signal (payments, health data, PII, cloud, AI/ML, e-commerce, etc.) up to 25 |
| **Operational complexity** | 10 | Multi-site / regional / distributed ops → 10pts |
| **Regulatory sensitivity** | 10 | Evidence of CBK/IRA/MOH/PCI-DSS/AML regulation → 10pts |
| **Bonus signals** | 10 | Digital transformation mention, funding round, recent tech hire → +5pts each |

**Thresholds (configurable in config.yaml):**
- ≥ 70 → High Priority / Qualified
- ≥ 50 → Medium Priority / Qualified
- < 50 → Low Priority / Needs Review

---

## AI vs. Deterministic Logic

| Concern | Where handled |
|---------|---------------|
| Company filtering | **Deterministic** — config.yaml rules |
| Opportunity scoring | **Deterministic** — scorer.py formula |
| Qualification status | **Deterministic** — threshold comparison |
| Priority assignment | **Deterministic** — threshold comparison |
| Evidence labelling | **Deterministic** — enricher.py logic |
| Decision-maker role lookup | **Deterministic** — industry keyword table |
| Score explanation (narrative) | **LLM** — synthesis of pre-collected evidence |
| Business observations | **LLM** — qualitative analysis of evidence |
| Personalised outreach | **LLM** — evidence-grounded message generation |
| Schema validation | **Deterministic** — Pydantic v2 |
| Retry / fallback | **Deterministic** — tenacity + stub |

**The LLM cannot change scores or invent facts.** It receives only pre-collected evidence.

---

## Hallucination & Data Quality Controls

1. **Evidence-only prompting** — The LLM is given only the evidence the enricher collected. It cannot browse the web or use training-data recall about specific companies.
2. **Explicit prohibition rules** — The system prompt lists 10 categories of things the LLM must never fabricate (names, incident history, certifications, revenues, etc.).
3. **Field-level reliability labels** — Every piece of information carries `Verified | Inferred | Unknown`.
4. **"Not verified" is valid** — The system never invents a decision-maker name. `Not verified` + recommended role is always preferred.
5. **Pydantic validation** — LLM output is parsed and validated before use. Invalid responses trigger a retry.
6. **Retry → fallback** — After 3 failed attempts, a deterministic stub is used. The lead is marked `pipeline_status: llm_fallback`.
7. **Outreach template guard** — Unfilled placeholders (`{first_name}`) are stripped during coercion.
8. **Source evidence preserved** — Every claim links back to its source URL and evidence status.

**Where hallucinations could still occur:**
- LLM could over-interpret sparse evidence. Mitigated by instructing it to label inferences.
- LLM could produce subtly generic outreach. Mitigated by requiring specific evidence references.

**How conflicting information is handled:**
- Contradictory signals are preserved in `business_observations` with an explicit conflict note.
- The system does not silently resolve conflicts.

**When an API fails:**
- `tenacity` retries with exponential back-off (2s, 5s, 10s).
- After 3 failures, deterministic stub is used, `pipeline_status` set to `llm_fallback`.
- The lead is still scored, validated, and written to output — not silently dropped.

---

## Configuration — Retargeting

To retarget the pipeline for a different business or geography, edit **only** `config.yaml`:

```yaml
target:
  industries:
    - retail           # ← change to new target sectors
    - manufacturing
  geography:
    - South Africa     # ← change to new region
    - Johannesburg
  employee_min: 100
  employee_max: 1000

scoring:
  high_threshold: 65   # ← adjust if needed for new vertical
  medium_threshold: 45
```

No code changes required. The scoring formula, LLM prompts, and output formats all adapt automatically.

---

## CLI Reference

```bash
python main.py                           # full pipeline run
python main.py --skip-llm               # deterministic only (no API key needed)
python main.py --skip-website-check     # skip HTTP checks (faster)
python main.py --config custom.yaml     # use alternate config
python main.py --output-dir ./results   # custom output directory
python main.py --dry-run                # discovery only, lists matches
python main.py --validate-only          # re-validate existing output JSON
python main.py --verbose                # debug logging
python main.py --help                   # full help
```

**Environment variables:**
```bash
GEMINI_API_KEY=...    # enables Gemini LLM synthesis
OPENAI_API_KEY=...    # fallback if no Gemini key
```

---

## Demo Guide

For the 30-45 minute demonstration, walk through:

1. **Config change** — modify `config.yaml` geography or industry, rerun, show different results
2. **Dry run** — `python main.py --dry-run` shows discovery without output files
3. **Deterministic path** — `python main.py --skip-llm` shows full scoring without API key
4. **Score breakdown** — open `leads_output.json`, show `score_breakdown` object for any lead
5. **Evidence tagging** — point to `source_evidence` array, show Verified vs Inferred labels
6. **Decision-maker handling** — show `Not verified` + `recommended_role` (never invented name)
7. **LLM fallback** — explain what happens when API is unavailable (`pipeline_status: llm_fallback`)
8. **Validation gate** — explain Pydantic coercion and `review_queue.json`
9. **Dashboard** — open `output/dashboard.html`, demonstrate search/filter/sort
10. **Cost/scale** — explain per-lead cost estimate and 100k-lead architecture

---

## Technology Stack

| Component | Technology | Why |
|-----------|------------|-----|
| Language | Python 3.9+ | Ubiquitous, excellent LLM/data library ecosystem |
| Schema validation | Pydantic v2 | Fast, expressive, catches LLM output drift immediately |
| Config | YAML | Human-editable, supports comments, easily version-controlled |
| LLM (primary) | Google Gemini 2.0 Flash | Fast, cost-effective, multimodal, generous free tier |
| LLM (fallback) | OpenAI GPT-4o-mini | Industry standard, high JSON reliability |
| HTTP enrichment | requests + urllib3 | Lightweight, no external runtime dependency |
| Retries | tenacity | Battle-tested exponential backoff library |
| Output | CSV + JSON + HTML | Zero external dependencies for viewing; works offline |

**Production additions I would recommend:**
- **PostgreSQL** — replace CSV for lead/evidence storage with queryable DB
- **Redis** — cache enrichment results (company data doesn't change daily)
- **SQS/RabbitMQ** — queue-based fan-out for parallel enrichment at scale
- **Apollo.io / Hunter.io** — replace seed JSON with live company discovery API
- **Celery + workers** — concurrent pipeline execution
- **Structured logging / OpenTelemetry** — observability
- **Airflow or Prefect** — pipeline scheduling and DAG management
- **Human approval step** — before any outbound sending

---

## Cost & Scale

### Cost per lead (prototype)
- Discovery: ~\$0 (seed file) → ~\$0.002 (SerpAPI search) in production
- Enrichment: ~\$0 (website check) → ~\$0.01-0.05 (Clearbit/Apollo) in production  
- LLM analysis: ~\$0.001-0.005 (Gemini Flash ~\$0.075/1M input tokens)
- **Estimated total: \$0.01-0.06 per lead** depending on providers

### 1,000 leads
- LLM cost: ~\$1-5 (Gemini Flash) or ~\$5-15 (GPT-4o-mini)
- Enrichment API: ~\$50-100 (if using paid company data APIs)
- **Batch processing, caching, and smaller models reduce this materially**

### 100,000 leads — architectural changes required
1. **Queue-based architecture** — SQS/RabbitMQ for parallel enrichment fan-out
2. **Database** — PostgreSQL with lead/evidence tables, idempotency keys
3. **Caching** — Redis for company data (TTL ~7 days; company info is stable)
4. **Model routing** — cheap model (Flash) for extraction/classification; stronger model only for ambiguous cases
5. **Rate-limit awareness** — per-provider concurrency limits respected in worker pool
6. **Cost optimisation** — cache LLM responses for identical evidence blocks; deduplicate companies before scoring
7. **Dead-letter queue** — failed leads after all retries go to DLQ for manual review, not silently lost
8. **Observability** — structured logs, per-stage metrics, alert on error rate spikes

---

## Limitations of This Prototype

- **Discovery is seeded** — 30 pre-researched companies; production would call a live API
- **No real-time web scraping** — enrichment uses pre-collected signals; production would scrape websites
- **Decision-maker names not found** — no LinkedIn API or Hunter.io integration in prototype
- **Single-threaded** — processes one company at a time; production would parallelise
- **No database** — all state is in-memory per run; production would persist to PostgreSQL
- **No deduplication across runs** — rerunning creates new output; production would upsert by company ID
- **LLM outreach quality** — without a real key, deterministic stub outreach is functional but less personalised
- **Website check is HEAD-only** — does not scrape page content; production enricher would extract metadata

---

## Important Note

The opportunity signals identified for each company are **prospecting hypotheses** — not findings that a company has a security vulnerability or weakness. All data is sourced from publicly available profiles and websites. Public-source data is a snapshot and may change.
