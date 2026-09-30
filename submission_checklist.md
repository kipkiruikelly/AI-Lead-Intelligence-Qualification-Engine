# Demonstration Checklist

Use this guide during the 30-45 minute demo session.

## Setup (before the call)
- [ ] `source .venv/bin/activate` (or ensure Python 3.9+ in PATH)
- [ ] Run `python main.py --skip-llm --skip-website-check` once to pre-generate outputs
- [ ] Open `output/dashboard.html` in browser
- [ ] Have `config.yaml`, `pipeline/scorer.py`, `schemas/lead_schema.py` open in editor

---

## Demo Flow

### 1. Run the pipeline live (2 min)
```bash
python main.py --skip-llm --skip-website-check
```
Show the progress bar, scoring summary, validation pass count.

### 2. Show configurable targeting (2 min)
Edit `config.yaml` — change industries or geography. Rerun with `--dry-run`:
```bash
python main.py --dry-run --skip-llm
```
Show how the matched company count changes immediately.

### 3. Show the deterministic scorer (5 min)
Open `pipeline/scorer.py`. Walk through:
- The `SIZE_SCORES`, `SECTOR_SCORES` constants
- The `_score_exposure()` signal matching loop
- Show `output/leads_output.json` → pick any lead → show `score_breakdown` object
- Emphasise: **LLM cannot change these numbers**

### 4. Show structured output (3 min)
Open `output/dashboard.html`:
- Search for "banking" → filtered results
- Click score column header → sorts by score
- Expand "View explanation" for a High Priority lead
- Expand "View message" for the outreach
- Point out Verified / Inferred / Unknown evidence tags

### 5. Show data reliability controls (5 min)
Open `output/leads_output.json`, find any lead:
- `source_evidence` array — every claim has a URL and evidence_status
- `decision_maker.name` = "Not verified" — never invented
- `decision_maker.recommended_role` = correct role for the industry
- `pipeline_status` = "ok"

### 6. Show hallucination controls (5 min)
Open `prompts/system_prompt.txt`:
- Walk through the 10 explicit prohibition rules
- Explain evidence-only prompt (no web browsing)
- Show `prompts/analysis_prompt_template.txt` — `{{EVIDENCE_BLOCK}}` injection
- Explain Pydantic validation → retry → fallback chain

### 7. Show Pydantic validation (3 min)
Open `schemas/lead_schema.py`:
- Show `LeadRecord` model fields
- Show `@field_validator("opportunity_score")` — score must match breakdown total
- Show `@field_validator("outreach_message")` — rejects generic phrases
- Run `python main.py --validate-only` → 30 passed, 0 failed

### 8. Show error handling (3 min)
Explain what happens when:
- Website unreachable → `website_reachable: false`, pipeline continues
- LLM API fails → tenacity retry (2s, 5s, 10s) → deterministic stub
- LLM returns bad JSON → `_extract_json()` tries multiple parse strategies
- Pydantic fails → coercion attempt → if still fails → `review_queue.json`

### 9. LLM path (if API key available) (5 min)
```bash
export GEMINI_API_KEY="your-key"
python main.py --skip-website-check
```
Compare LLM outreach vs deterministic stub for same lead.
Show `llm_used: true` in JSON.

### 10. Cost & scale discussion (5 min)
- Per-lead cost: ~$0.01-0.06 (seed+enrichment+LLM)
- 1k leads: ~$1-5 LLM + ~$50-100 enrichment APIs
- 100k leads: queue-based fan-out, PostgreSQL, Redis cache, model routing

---

## Anticipated questions

| Question | Answer |
|----------|--------|
| Why doesn't the LLM set the score? | LLM scores are inconsistent and opaque; deterministic formula is auditable, reproducible, and testable |
| What if a company isn't in the seed file? | Production would call Apollo/SerpAPI; seed file simulates that step without paid credentials |
| How do you prevent the LLM making up executive names? | System prompt prohibits it; `Not verified` is always valid; Pydantic rejects confabulated contact data |
| What happens if the LLM is down? | tenacity retries 3x, then deterministic stub is used; lead is still scored and output correctly |
| How would you adapt this to a different vertical? | Change 5 lines in config.yaml; everything else adapts automatically |
| How do you handle conflicting information? | enricher preserves conflicts in evidence; LLM is instructed to flag rather than resolve them |
