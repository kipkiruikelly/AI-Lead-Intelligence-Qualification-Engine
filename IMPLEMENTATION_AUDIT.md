# IMPLEMENTATION AUDIT REPORT

## A. What Changed
1. **Provider-Based Lead Discovery**: Replaced static seed file reading in `pipeline/discoverer.py` with an extensible `DiscoveryProvider` interface (`WebSearchProvider`, `SeedFileProvider`). Discovery queries are dynamically generated from `config.yaml` target parameters.
2. **Canonical Deduplication**: Added `pipeline/deduplicator.py` to prevent duplicate domain/company processing across URLs (stripping protocols, `www.`, ports, and entity suffixes).
3. **Live Web Scraping & Evidence Model**: Upgraded `pipeline/enricher.py` to perform HTTP web page fetching (extracting title, meta description, and page text), scanning for exposure and regulatory signals, and attributing ISO 8601 UTC timestamps (`retrieved_at`).
4. **No Silent Fallback Fabrication**: Updated `pipeline/llm_client.py` so that normal live execution marks `pipeline_status: llm_unavailable` when LLM keys/APIs fail instead of silently fabricating fake stubs. Demo mode stubs are locked behind explicit `--demo-mode`.
5. **Run Versioning & Persistence**: Added unique `run_id` generation (e.g. `run_20260930_125633_ce93`), folder versioning under `output/runs/<run_id>/` and `output/latest/`, plus SQLite database repository persistence in `output/leads_repository.db`.
6. **Automated Unit Testing**: Created a `pytest` test suite in `tests/` covering deterministic scoring, canonical deduplication, and schema validation.

## B. Live Providers Implemented
* `WebSearchProvider`: Live web search query execution via DuckDuckGo HTML parser.
* `SeedFileProvider`: Historical seed file provider activated **only** when `--demo-mode` flag is explicitly passed.
* `Gemini 2.0 Flash` / `GPT-4o-mini`: Live LLM structured analysis APIs (when `GEMINI_API_KEY` or `OPENAI_API_KEY` environment variables are present).

## C. What is Now Genuinely Dynamic
* Search query formulation from YAML config.
* External web discovery and candidate URL retrieval.
* Canonical domain deduplication.
* Homepage web page scraping, title/meta extraction, and signal detection.
* ISO UTC retrieval timestamping.
* Unique `run_id` allocation and versioned file/database output generation.

## D. What Remains Static
* Default decision-maker role recommendation table when leadership details cannot be verified on the scraped page.

## E. Remaining Limitations
* Live search discovery relies on DuckDuckGo HTML parsing; heavily rate-limited connections may return fewer candidates unless paid APIs (e.g. SerpAPI) are configured.
* Scraped web text is limited to homepage title and meta descriptions to avoid aggressive scraping.

## F. Files Changed
* `pipeline/discoverer.py`
* `pipeline/enricher.py`
* `pipeline/llm_client.py`
* `pipeline/validator.py`
* `pipeline/output_writer.py`
* `schemas/lead_schema.py`
* `config.yaml`
* `main.py`
* `pipeline/deduplicator.py` (New)
* `pipeline/repository.py` (New)
* `pipeline/providers/base.py` (New)
* `pipeline/providers/web_search.py` (New)
* `pipeline/providers/seed_file.py` (New)
* `tests/test_scorer.py` (New)
* `tests/test_deduplication.py` (New)
* `tests/test_validator.py` (New)

## G. Environment Variables Required
* `GEMINI_API_KEY` (Optional: Enables Gemini LLM synthesis)
* `OPENAI_API_KEY` (Optional: Fallback LLM synthesis)

## H. How to Run Live Mode
```bash
python3 main.py
```
*(Runs live web search discovery, live web scraping, deterministic scoring, Pydantic validation, SQLite persistence, and exports output to `output/runs/<run_id>/` and `output/latest/`)*

## I. How to Run Demo Mode
```bash
python3 main.py --demo-mode
```
*(Runs against historical static seed file `data/seed_companies.json` for deterministic testing)*

## J. Test Results
```text
============================== 6 passed in 0.18s ===============================
```
All unit tests in `tests/` passed cleanly.

## K. Live Discovery Proof
Documented in `LIVE_DISCOVERY_PROOF.md`. Discovered 18 external candidates (e.g., `Fsdkenya`, `Pesamarket`) completely absent from the pre-existing seed dataset.

## L. Cost Considerations
* Web Search & Scraping: $0.00
* LLM Analysis: ~$0.001 per lead via Gemini 2.0 Flash / GPT-4o-mini.

## M. Security Considerations
* API keys are loaded exclusively from environment variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`).
* No secrets or credentials in repository files.

## N. Final Authenticity Verdict

```text
REAL WORKING PROTOTYPE
```

**Reasoning**:
The system successfully executed a end-to-end run in Live Mode, queried live external search engines, discovered companies absent from the codebase, scraped web content in real-time, extracted signals with ISO timestamps, calculated deterministic scores, validated output schemas, and persisted records to SQLite and versioned files.
