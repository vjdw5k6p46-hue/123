# Reproducibility Commands

## Real Default Workflow

```bash
export OPENAI_API_KEY=your_key
export PHYSICELL_EXECUTABLE=/path/to/local/PhysiCell/project_executable
cart-autolab autoresearch-run --config configs/experiment_cytokine_gpc3_liver_autoresearch.yaml
```

## Deterministic Safe Demo

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_safe_demo.yaml
```

## LLM Mock Demo

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_llm_mock.yaml
```

## Replay Demo

```bash
```

## Ablation Demo

```bash
cart-autolab ablation --config configs/experiment_cytokine_gpc3_liver_ablation.yaml
```

## External PhysiCell Mode

```bash
export PHYSICELL_EXECUTABLE=/path/to/local/PhysiCell/project_executable
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

The safe demo, LLM mock, and ablation commands use software fixtures by default and require no API key. The real default workflow requires provider credentials, online literature access, and a local external PhysiCell executable. Missing external dependencies should be reported clearly rather than replaced with fabricated scientific outputs.
