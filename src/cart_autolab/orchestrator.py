from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import yaml

from .analysis.metrics import compute_metrics
from .analysis.plotting import generate_figures
from .analysis.ranking import rank_interventions
from .agents.chunk_evidence_extraction import ChunkEvidenceExtractionAgent
from .agents.critique import ExecutableCritiqueAgent
from .agents.hypothesis_generation import HypothesisGenerationAgent
from .critique.critique_agent import CritiqueAgent
from .evidence.extractor import EvidenceExtractor
from .literature.paper_downloader import PaperDownloader
from .literature.paper_chunker import PaperChunker
from .literature.search_agent import LiteratureSearchAgent
from .memory.memory_store import MemoryStore
from .parameters.fingerprint_builder import FingerprintBuilder
from .parameters.evidence_loader import EvidenceLoader
from .parameters.physicell_exporter import PhysiCellParameterExporter
from .prompts import export_agent_prompts
from .reporting.report_generator import ReportGenerator
from .simulation.experiment_designer import SimulationExperimentDesigner
from .simulation.physicell_adapter import PhysiCellAdapter


class AutolabOrchestrator:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.run_dir = Path(self.config["output_dir"])
        if not self.run_dir.is_absolute():
            self.run_dir = self.config_path.parent.parent / self.run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.memory = MemoryStore(self.run_dir, self.config["experiment_id"])

    def set_run_dir(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.memory = MemoryStore(self.run_dir, self.config["experiment_id"])

    def run_all(self) -> dict:
        self.save_reproducibility_header()
        search = self.search()
        if self.config.get("literature", {}).get("download_papers", False):
            self.download_papers(search["included_papers"])
            self.chunk_papers()
        evidence = self.extract_evidence(search["included_papers"])
        built = self.build_parameters(evidence)
        self.simulate(built["parameters"])
        self.analyze()
        critique = self.critique()
        report = self.report()
        return {"run_dir": str(self.run_dir), "critique": critique, "report": report}

    def save_reproducibility_header(self) -> None:
        shutil.copy2(self.config_path, self.run_dir / "experiment_config.yaml")
        version = {"python": sys.version, "package": "cart-autolab 0.1.0"}
        (self.run_dir / "software_version.json").write_text(json.dumps(version, indent=2), encoding="utf-8")
        export_agent_prompts(self.run_dir / "agent_prompts.json")
        self.memory.add("init", self.run_dir / "experiment_config.yaml", "Original experiment configuration saved.")
        self.memory.add("prompts", self.run_dir / "agent_prompts.json", "Agent prompt registry saved for reproducibility.")

    def search(self) -> dict:
        agent = LiteratureSearchAgent(mode=self.config.get("literature", {}).get("mode", "mock"))
        result = agent.search(self.config, self.run_dir)
        self.memory.add("literature_search", self.run_dir / "included_papers.json", "Literature search and screening completed.")
        return result

    def download_papers(self, papers: list[dict] | None = None) -> dict:
        if papers is None:
            included_path = self.run_dir / "included_papers.json"
            if not included_path.exists():
                self.search()
            papers = json.loads(included_path.read_text(encoding="utf-8"))
        literature_cfg = self.config.get("literature", {})
        downloader = PaperDownloader(
            email=literature_cfg.get("email"),
            max_papers=int(literature_cfg.get("max_downloads", 20)),
            timeout=int(literature_cfg.get("download_timeout_seconds", 30)),
        )
        result = downloader.download(papers, self.run_dir)
        self.memory.add("paper_download", self.run_dir / "downloaded_papers_manifest.json", "Open-access paper artifacts downloaded or attempted with provenance.")
        return result

    def chunk_papers(self) -> dict:
        literature_cfg = self.config.get("literature", {})
        chunker = PaperChunker(
            chunk_chars=int(literature_cfg.get("chunk_chars", 3500)),
            overlap_chars=int(literature_cfg.get("chunk_overlap_chars", 350)),
        )
        result = chunker.chunk_downloaded_papers(self.run_dir)
        self.memory.add("paper_chunking", self.run_dir / "paper_chunks" / "paper_chunks.jsonl", "Downloaded papers extracted and chunked for LLM consumption.")
        return result

    def extract_evidence(self, papers: list[dict] | None = None) -> list[dict]:
        if papers is None:
            included_path = self.run_dir / "included_papers.json"
            if not included_path.exists():
                self.search()
            papers = json.loads(included_path.read_text(encoding="utf-8"))
        source = self.config.get("workflow", {}).get("evidence_source", "deterministic")
        if source not in {"deterministic", "llm", "hybrid"}:
            raise ValueError("workflow.evidence_source must be deterministic, llm, or hybrid.")
        deterministic = EvidenceExtractor().extract(papers, self.config, self.run_dir)
        (self.run_dir / "extracted_evidence_deterministic.json").write_text(json.dumps(deterministic, indent=2), encoding="utf-8")
        if source == "deterministic":
            evidence = deterministic
        else:
            llm_evidence = ChunkEvidenceExtractionAgent().extract(papers, self.config, self.run_dir, source="llm")
            if source == "llm":
                evidence = llm_evidence
            else:
                evidence = deterministic + llm_evidence
                (self.run_dir / "extracted_evidence_hybrid.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            (self.run_dir / "extracted_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            HypothesisGenerationAgent().generate(evidence, self.config, self.run_dir, source="llm")
        self.memory.add("evidence_extraction", self.run_dir / "extracted_evidence.json", "Structured biological evidence extracted from retrieved records.")
        return evidence

    def build_parameters(self, evidence: list[dict] | None = None) -> dict:
        if evidence is None:
            source = self.config.get("workflow", {}).get("evidence_source", "deterministic")
            evidence_path = self.run_dir / ("extracted_evidence.json" if source == "deterministic" else f"extracted_evidence_{source}.json")
            if not evidence_path.exists():
                self.extract_evidence()
            evidence = EvidenceLoader().load(self.run_dir, self.config)
        built = FingerprintBuilder().build(evidence, self.config, self.run_dir)
        self.memory.add("parameter_building", self.run_dir / "parameter_fingerprints.json", "Simulation-ready intervention parameters built.")
        return built

    def simulate(self, parameters: list[dict] | None = None, simulator: str = "physicell") -> dict:
        if simulator != "physicell":
            raise ValueError(f"Unsupported simulator '{simulator}'. Available adapter: physicell.")
        if parameters is None:
            parameter_path = self.run_dir / "parameter_fingerprints.json"
            if not parameter_path.exists():
                self.build_parameters()
            parameters = json.loads(parameter_path.read_text(encoding="utf-8"))
        plan = SimulationExperimentDesigner().design(self.config, parameters, self.run_dir)
        sim_cfg = self._load_simulator_config()
        mode = "external" if os.getenv("PHYSICELL_EXECUTABLE") else sim_cfg.get("mode", "mock")
        executable = os.getenv("PHYSICELL_EXECUTABLE") or sim_cfg.get("physicell_executable")
        adapter = PhysiCellAdapter(executable=executable, mode=mode)
        adapter.prepare_inputs(plan, parameters, self.run_dir)
        adapter.write_config(self.run_dir)
        adapter.run(self.run_dir)
        summary = adapter.summarize_results(self.run_dir)
        artifact = self.run_dir / "simulation" / "timeseries.csv"
        if not artifact.exists():
            artifact = self.run_dir / "simulation" / "simulation_summary.json"
        self.memory.add("simulation", artifact, "Simulation inputs, seeds, and outputs saved.")
        return summary

    def export_physicell_parameters(self, base_config: str | Path | None = None) -> dict:
        parameter_path = self.run_dir / "parameter_fingerprints.json"
        if not parameter_path.exists():
            self.build_parameters()
        parameters = json.loads(parameter_path.read_text(encoding="utf-8"))
        sim_cfg = self._load_simulator_config()
        configured_base = base_config or sim_cfg.get("base_config_template")
        exported = PhysiCellParameterExporter().export(parameters, self.config, self.run_dir, configured_base)
        self.memory.add("physicell_parameter_export", self.run_dir / "physicell_ready_parameters.json", "PhysiCell-ready XML user_parameters generated from intervention fingerprints.")
        return exported

    def _load_simulator_config(self) -> dict:
        path = self.config_path.parent / "simulator_physicell.yaml"
        config = {}
        if path.exists():
            config.update(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        config.update(self.config.get("simulator", {}) or {})
        return config or {"mode": "mock", "physicell_executable": None}

    def analyze(self) -> dict:
        compute_metrics(self.run_dir)
        ranked = rank_interventions(self.run_dir)
        figures = generate_figures(self.run_dir)
        self.memory.add("analysis", self.run_dir / "ranked_interventions.csv", "Metrics, rankings, uncertainty summaries, and figures generated.")
        return {"top": ranked.iloc[0].to_dict(), "figures": figures}

    def critique(self) -> dict:
        source = self.config.get("workflow", {}).get("critique_source", "deterministic")
        if source not in {"deterministic", "llm", "hybrid"}:
            raise ValueError("workflow.critique_source must be deterministic, llm, or hybrid.")
        if source == "deterministic":
            critique = CritiqueAgent().critique(self.run_dir)
        else:
            critique = ExecutableCritiqueAgent().critique(self.config, self.run_dir, source=source)
        self.memory.add("critique", self.run_dir / "critique_report.json", "Biological plausibility critique generated.")
        return critique

    def report(self) -> dict:
        report = ReportGenerator().generate(self.run_dir, self.config)
        self.memory.add("report", Path(report["markdown"]), "Final Markdown and HTML reports generated.")
        return report
