# Hermes Model — Training Data Pipeline

## Purpose
Collect + format successful agent interactions as training data for fine-tuning
a small specialized model. True sovereignty — own the intelligence stack.

## How it works
1. `collector.py` scans Hermes logs + session files
2. Extracts tool call patterns and user→agent interactions
3. Formats as JSONL training examples
4. Outputs to `data/agent_interactions.jsonl`

## Running
```bash
python3 collector.py
```

## Validation
```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 collector.py
```

The unittest smoke test runs the collector against temporary sample logs/sessions so you can verify the pipeline without mutating the live corpus first.

## Nightly automation
Add to cron: run collector before vault autocommit so training data
compounds nightly alongside everything else.

## Roadmap
- [ ] v0.1: Log/interaction collector (DONE)
- [ ] v0.2: Quality filtering (only keep high-success interactions)
- [ ] v0.3: Format for specific fine-tuning APIs (OpenAI, Axolotl, Unsloth)
- [ ] v0.4: Training pipeline using Unsloth/QLoRA on collected data
- [ ] v1.0: Small specialized agent model trained on our own data
