# External PhysiCell Mode

PhysiCell is an external third-party simulator. This repository does not vendor the full PhysiCell source tree, compiled executables, object files, or large simulation outputs.

The project contribution is the LLM-guided, schema-constrained CAR-T in silico workflow that maps evidence into bounded parameter fingerprints and simulator adapter inputs. External PhysiCell execution is optional and requires a local PhysiCell build.

## Modes

- Mock mode: used for CI, offline software tests, and demonstrations. Mock outputs are software fixtures only and are not mechanistic simulation evidence.
- External mode: writes adapter inputs and calls a user-supplied PhysiCell executable.

## Configure an External Executable

Set the executable path:

```bash
export PHYSICELL_EXECUTABLE=/path/to/PhysiCell/project_executable
```

On Windows PowerShell:

```powershell
$env:PHYSICELL_EXECUTABLE="C:\path\to\PhysiCell\project_executable.exe"
```

Then run with a config that enables external mode:

```bash
cart-autolab simulate --config configs/experiment_cytokine_gpc3_liver_physicell.yaml
```

If `PHYSICELL_EXECUTABLE` is missing or points to a non-executable path, external mode fails with an actionable error. It does not silently fall back to mock mode.

## Output Conversion

External PhysiCell outputs vary by project. The converter looks for common summary tables and only writes `simulation/timeseries.csv` when available data include the required common schema fields:

- `condition_id`
- `intervention_name`
- `replicate`
- `time`
- `tumor_burden`
- `car_t_cells`
- `exhaustion_fraction`
- `cytotoxicity`
- `IFN_gamma`
- `hypoxia`
- `PD_L1_signal`
- `tme_suppression`

If data are insufficient, the converter writes `simulation/conversion_report.json` explaining what was found and what could not be converted. Missing time series are never fabricated.
