from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .orchestrator import AutolabOrchestrator
from .analysis.ablation import run_ablation
from .autoresearch import AutoResearchWorkflow
from .prompts import AGENT_PROMPTS, export_agent_prompts, get_agent_prompt, list_agent_prompts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cart-autolab")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--template", default="cytokine_gpc3_liver")
    prompts = sub.add_parser("prompts")
    prompts.add_argument("--agent", default=None)
    prompts.add_argument("--export", default=None)
    for name in ["search", "download-papers", "chunk-papers", "build-parameters", "export-physicell", "simulate", "run-all"]:
        p = sub.add_parser(name)
        p.add_argument("--config", default="configs/experiment_cytokine_gpc3_liver.yaml")
        if name == "export-physicell":
            p.add_argument("--base-config", default=None)
        if name == "simulate":
            p.add_argument("--simulator", default="physicell")
    for name in ["analyze", "report"]:
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.add_argument("--config", default="configs/experiment_cytokine_gpc3_liver.yaml")
    ablation = sub.add_parser("ablation")
    ablation.add_argument("--config", default="configs/experiment_cytokine_gpc3_liver_ablation.yaml")
    autoresearch = sub.add_parser("autoresearch-run")
    autoresearch.add_argument("--config", default="configs/experiment_cytokine_gpc3_liver_autoresearch.yaml")
    autoresearch.add_argument("--skip-base-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "init":
        src = Path(__file__).resolve().parents[2] / "configs" / "experiment_cytokine_gpc3_liver.yaml"
        dst = Path("configs") / "experiment_cytokine_gpc3_liver.yaml"
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(src, dst)
        print(f"Initialized {dst}")
        return
    if args.command == "ablation":
        print(json.dumps(run_ablation(args.config), indent=2))
        return
    if args.command == "autoresearch-run":
        print(json.dumps(AutoResearchWorkflow(args.config).run(skip_base_run=args.skip_base_run), indent=2))
        return
    if args.command == "prompts":
        if args.export:
            path = export_agent_prompts(args.export)
            print(json.dumps({"exported": str(path), "agents": list_agent_prompts()}, indent=2))
        elif args.agent:
            print(json.dumps(get_agent_prompt(args.agent), indent=2))
        else:
            print(json.dumps({"agents": list_agent_prompts(), "count": len(AGENT_PROMPTS)}, indent=2))
        return
    orch = AutolabOrchestrator(args.config)
    if args.command == "search":
        print(json.dumps(orch.search(), indent=2)[:4000])
    elif args.command == "download-papers":
        print(json.dumps(orch.download_papers(), indent=2))
    elif args.command == "chunk-papers":
        print(json.dumps(orch.chunk_papers(), indent=2))
    elif args.command == "build-parameters":
        print(json.dumps(orch.build_parameters(), indent=2))
    elif args.command == "export-physicell":
        print(json.dumps(orch.export_physicell_parameters(base_config=args.base_config), indent=2))
    elif args.command == "simulate":
        print(json.dumps(orch.simulate(simulator=args.simulator), indent=2))
    elif args.command == "analyze":
        orch.set_run_dir(args.run)
        print(json.dumps(orch.analyze(), indent=2))
    elif args.command == "report":
        orch.set_run_dir(args.run)
        print(json.dumps(orch.report(), indent=2))
    elif args.command == "run-all":
        print(json.dumps(orch.run_all(), indent=2))


if __name__ == "__main__":
    main()
