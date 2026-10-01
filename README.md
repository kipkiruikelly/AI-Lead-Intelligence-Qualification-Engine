# AI-Powered Lead Intelligence & Qualification Engine

Prototype for the **AI Engineering & Automation Technical Assessment**.

A Python pipeline that discovers, researches, qualifies, prioritizes, and prepares cybersecurity prospects for personalized outreach.

## Pipeline

```text
Config → Discovery → Deduplication → Research → Evidence
      → Deterministic Scoring → LLM Analysis → Validation
      → SQLite / CSV / JSON / Dashboard
```

**Key design principle:** deterministic rules handle qualification; the LLM handles interpretation and language generation.

## Verified Status

* **30 leads** discovered, researched, scored, validated, and persisted.
* **12/12 tests passing.**
* Live research with source URLs and retrieval timestamps.
* Evidence classified as `Verified`, `Inferred`, or `Unknown`.
* SQLite run persistence and structured outputs.
* SSRF, prompt-injection, hallucination, and validation controls.
* Configurable industries, geography, company size, keywords, and thresholds.

**LLM:** Real LLM execution was not verified in the final acceptance environment because Gemini quota was exhausted. The system records `pipeline_status: llm_unavailable` rather than fabricating AI output.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run without LLM
python main.py --skip-llm

# Full pipeline with LLM
export GEMINI_API_KEY="your-key"
python main.py

# Tests
pytest -q
```

For Windows:

```powershell
.venv\Scripts\activate
```

## Configuration

Edit `config.yaml` to change:

* Target industries
* Geography
* Employee range
* Discovery keywords
* Lead limit
* Score thresholds
* LLM configuration

No core-code changes are required for normal retargeting.

## Scoring

Qualification is deterministic and uses six factors:

| Factor                 |     Max |
| ---------------------- | ------: |
| Size                   |      20 |
| Sector                 |      25 |
| Digital Exposure       |      25 |
| Operational Complexity |      10 |
| Regulatory Sensitivity |      10 |
| Bonus                  |      10 |
| **Total**              | **100** |

This keeps qualification reproducible and auditable.

## Data Quality

The system:

* preserves source evidence and retrieval timestamps
* distinguishes verified information from inference and unknowns
* never invents unverified decision-maker names
* validates structured AI output with Pydantic
* routes invalid data for review
* treats external website content as untrusted input

## Security

Implemented controls include:

* SSRF protection
* Prompt-injection isolation
* Unsupported-claim/hallucination controls
* API failure handling
* Input and schema validation

## Outputs

Generated results include:

```text
output/
├── dashboard.html
├── leads_output.csv
├── leads_output.json
├── leads_repository.db
└── runs/
```

## Tests

```bash
pytest -q
```

Final verified result: **12/12 passed**.

## Demo

Recommended flow:

1. Show `config.yaml`.
2. Run discovery.
3. Inspect a researched lead and its evidence.
4. Explain deterministic scoring.
5. Explain the LLM's role.
6. Demonstrate validation and security controls.
7. Show SQLite, JSON, CSV, and dashboard outputs.
8. Discuss limitations and production scaling.

## Known Limitations

* Public HTML search can be rate-limited; a controlled fallback discovery provider is included.
* Real LLM execution requires internet connectivity and available provider quota.
* Decision-maker enrichment is limited to publicly available evidence; the system does not fabricate names.

## Production Direction

At larger scale, the architecture could move to:

* PostgreSQL
* Redis caching
* Queue-based workers
* Dedicated search/enrichment APIs
* Structured observability
* Human approval before outbound messaging

## Project Documentation

See:

* `DESIGN_DECISIONS.md`
* `architecture.md`
* `REPOSITORY_INVENTORY.md`
* `FINAL_REPOSITORY_CLEANUP_REPORT.md`

## Assessment Status

**READY WITH DOCUMENTED LIMITATIONS**

The project prioritizes a reliable, repeatable, structured, and adaptable automation workflow rather than production-scale infrastructure.
