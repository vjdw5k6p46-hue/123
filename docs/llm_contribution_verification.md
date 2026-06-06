# LLM Contribution Verification

The reproducibility demo writes:

```text
outputs/reviewer_demo/llm_contribution_summary.csv
```

The table compares deterministic, LLM mock, LLM replay, and hybrid software workflows.

Columns:

- `workflow_mode`
- `evidence_source`
- `number_of_evidence_records`
- `number_of_cytokines_covered`
- `endpoints_covered`
- `citation_traceability_fraction`
- `schema_valid_fraction`
- `low_confidence_fraction`
- `IL15_rank`
- `top_ranked_intervention`
- `notes`

Rows using mock or replay data are labeled as software-fixture demonstrations. They show that the LLM layer can alter the software path and parameter provenance, but they do not establish biological superiority and are not manuscript evidence.

Wet-lab concordance is not fabricated. If no user-supplied validation CSV is available, the notes state:

```text
experimental concordance not evaluated; user-supplied validation table required
```

Run:

```bash
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

Then inspect:

```bash
python - <<'PY'
from pathlib import Path
print(Path('outputs/reviewer_demo/llm_contribution_summary.csv').read_text())
PY
```
