# Reproducibility Commands

## Deterministic Demo

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver.yaml
```

## LLM Mock Demo

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_llm_mock.yaml
```

## Replay Demo

```bash
cart-autolab run-all --config configs/experiment_cytokine_gpc3_liver_replay.yaml
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

The LLM mock, replay, and ablation commands use software fixtures by default and require no API key. External PhysiCell mode requires a local executable and should not be used as a CI requirement.
