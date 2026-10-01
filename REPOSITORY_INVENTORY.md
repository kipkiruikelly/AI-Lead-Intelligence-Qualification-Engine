# REPOSITORY INVENTORY

| Path | Purpose | Used By | Runtime Used? | Submission Required? | Action |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `main.py` | Pipeline CLI orchestrator & entry point | CLI | Yes | Yes | KEEP |
| `config.yaml` | External targeting & threshold configuration | Pipeline modules | Yes | Yes | KEEP |
| `requirements.txt` | Python runtime dependency specifications | Environment | Yes | Yes | KEEP |
| `architecture.md` | Architecture documentation & diagrams | Developer / Assessor | No | Yes | KEEP — DOCUMENTATION |
| `README.md` | Primary setup & user guide | Developer / Assessor | No | Yes | KEEP — DOCUMENTATION |
| `llm_output_schema.json` | JSON Schema reference specification | Developer / Documentation | No | Yes | KEEP — DOCUMENTATION |
| `pipeline/__init__.py` | Pipeline package initializer | Python import | Yes | Yes | KEEP |
| `pipeline/deduplicator.py` | Canonical domain deduplication logic | `discoverer.py` | Yes | Yes | KEEP |
| `pipeline/discoverer.py` | Lead discovery & provider routing engine | `main.py` | Yes | Yes | KEEP |
| `pipeline/enricher.py` | Live HTTP web research & signal scraper | `main.py` | Yes | Yes | KEEP |
| `pipeline/llm_client.py` | Structured LLM analysis client (`google-genai`) | `main.py` | Yes | Yes | KEEP |
| `pipeline/output_writer.py` | Exporter for CSV, JSON, and HTML dashboard | `main.py` | Yes | Yes | KEEP |
| `pipeline/repository.py` | SQLite database persistence layer | `main.py` | Yes | Yes | KEEP |
| `pipeline/scorer.py` | Deterministic 6-factor qualification engine | `main.py` | Yes | Yes | KEEP |
| `pipeline/security.py` | SSRF protection & IP resolution safety check | `enricher.py` | Yes | Yes | KEEP |
| `pipeline/validator.py` | Pydantic schema gate & hallucination guard | `main.py` | Yes | Yes | KEEP |
| `pipeline/providers/__init__.py` | Providers package initializer | Python import | Yes | Yes | KEEP |
| `pipeline/providers/base.py` | Abstract Base Class for discovery providers | `discoverer.py` | Yes | Yes | KEEP |
| `pipeline/providers/seed_file.py` | Local seed file provider for offline/demo runs | `discoverer.py` | Demo Mode | Yes | KEEP — DEMO/TEST |
| `pipeline/providers/web_search.py` | Live web search provider with fallback pool | `discoverer.py` | Yes | Yes | KEEP |
| `schemas/__init__.py` | Schemas package initializer | Python import | Yes | Yes | KEEP |
| `schemas/lead_schema.py` | Pydantic v2 data models & validation schema | `validator.py`, `output_writer.py` | Yes | Yes | KEEP |
| `prompts/system_prompt.txt` | LLM system prompt (strict anti-fabrication rules) | `llm_client.py` | Yes | Yes | KEEP |
| `prompts/analysis_prompt_template.txt` | Per-lead evidence injection template | `llm_client.py` | Yes | Yes | KEEP |
| `data/seed_companies.json` | 30 pre-researched seed leads for offline demo mode | `seed_file.py` | Demo Mode | Yes | KEEP — DEMO/TEST |
| `tests/__init__.py` | Test suite initializer | `pytest` | Yes | Yes | KEEP |
| `tests/test_deduplication.py` | Tests for domain normalization & deduplication | `pytest` | Yes | Yes | KEEP |
| `tests/test_hallucination.py` | Tests for hallucinated contact rejection | `pytest` | Yes | Yes | KEEP |
| `tests/test_prompt_injection.py` | Tests for HTML script tag stripping | `pytest` | Yes | Yes | KEEP |
| `tests/test_reproducibility.py` | Tests for scoring calculation reproducibility | `pytest` | Yes | Yes | KEEP |
| `tests/test_scorer.py` | Tests for 6-factor deterministic scoring engine | `pytest` | Yes | Yes | KEEP |
| `tests/test_security.py` | Tests for SSRF IP resolution blocking | `pytest` | Yes | Yes | KEEP |
| `tests/test_validator.py` | Tests for Pydantic schema validation gate | `pytest` | Yes | Yes | KEEP |
| `output/leads_repository.db` | SQLite database holding persisted run history | `repository.py` | Yes | Yes | KEEP |
| `output/latest/dashboard.html` | Generated interactive HTML dashboard | Assessor Review | Yes | Yes | KEEP — GENERATED OUTPUT |
| `output/latest/leads_output.csv` | Generated CSV output dataset | Assessor Review | Yes | Yes | KEEP — GENERATED OUTPUT |
| `output/latest/leads_output.json` | Generated full JSON output dataset | Assessor Review | Yes | Yes | KEEP — GENERATED OUTPUT |
| `output/runs/` | Historical versioned run directory artifacts | Output Writer | Yes | Yes | KEEP — GENERATED OUTPUT |
| `llm_system_prompt.txt` | Duplicate root-level prompt file | None | No | No | REMOVE — DUPLICATE |
| `leads.csv` | Root-level legacy CSV export clutter | None | No | No | REMOVE — TEMPORARY |
| `FINAL_DEMO_DATA.md` | Internal development audit notes | None | No | No | REMOVE — OBSOLETE |
| `.pytest_cache/` | Local pytest cache directory | `pytest` | Temporary | No | REMOVE — TEMPORARY |
