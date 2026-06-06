from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class CritiqueAgent:
    def critique(self, run_dir: Path) -> dict:
        ranked = pd.read_csv(run_dir / "ranked_interventions.csv")
        params = json.loads((run_dir / "parameter_fingerprints.json").read_text(encoding="utf-8"))
        top = ranked.iloc[0]["intervention_name"]
        low_conf = [p["intervention_name"] for p in params if p.get("confidence_score", 0) < 0.45]
        report = {
            "biological_interpretation": f"{top} is prioritized by this in silico run because it balances tumor reduction, CAR-T persistence, exhaustion control, and TME suppression in the configured low-antigen setting.",
            "confidence_level": "moderate" if not low_conf else "low-to-moderate",
            "limitations": [
                "Predictions are hypotheses for prioritization, not evidence of efficacy.",
                "Mock-mode dynamics are simplified and should be replaced with compiled PhysiCell/BioFVM execution for scientific runs.",
                "Literature-derived qualitative effects may be indirect, model-specific, or conflicting.",
                "No detailed wet-lab protocol is generated.",
            ],
            "low_confidence_parameters": low_conf,
            "plausibility_checks": [
                "Interventions predicted to work only through high inflammatory signals should be treated cautiously.",
                "Cytokine payloads with increased PD-L1/TME signals may need combination or safety evaluation.",
                "Robustness across replicates and sweeps should be expanded before wet-lab prioritization.",
            ],
            "recommended_validation_experiments_high_level": [
                "Compare prioritized and control CAR-T designs under low antigen density in controlled in vitro cytotoxicity and persistence assays.",
                "Measure exhaustion, cytotoxicity, memory, IFN-gamma, and checkpoint/TME markers.",
                "Use in vivo or organoid models only after safety and cytokine exposure risks are reviewed.",
            ],
        }
        (run_dir / "critique_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
