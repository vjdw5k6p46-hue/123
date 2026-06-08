# Reviewer Reproducibility Commands

Run the safe reproducibility demo:

```bash
bash scripts/run_reviewer_reproducibility_demo.sh
```

If `outputs/reviewer_demo/` already exists, the script refuses to overwrite it. To replace an existing demo output directory:

```bash
bash scripts/run_reviewer_reproducibility_demo.sh --force
```

The script runs only modes that require no API key, no internet access, and no compiled PhysiCell executable:

- deterministic demo
- LLM mock demo using software fixture responses
- ablation demo using mock software workflows

Outputs are written under:

```text
outputs/reviewer_demo/
```

Expected subdirectories:

- `deterministic/`
- `llm_mock/`
- `ablation/`

Each subdirectory contains a `README.txt` labeling the mode. Mock outputs are software fixtures only. They are not real scholarly citations, manuscript evidence, PhysiCell outputs, or wet-lab validation.

The final printed checklist reports:

- deterministic `final_report.md`
- LLM mock `llm_calls.jsonl`
- LLM mock `agent_outputs/`
- ablation `ablation_summary.csv`
- ablation `ranking_comparison.csv`
