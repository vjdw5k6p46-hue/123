from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DEFAULT_CONTROL_CONFIG = Path(os.environ.get("PHYSICELL_CONTROL_CONFIG", "physicell_project/config/PhysiCell_settings.template.xml"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run multi-replicate PhysiCell validation for AutoResearch cytokine XML configs.")
    parser.add_argument("--configs-dir", required=True)
    parser.add_argument("--output", default="outputs/physicell_autoresearch_replicates")
    parser.add_argument("--executable", default=os.environ.get("PHYSICELL_EXECUTABLE"))
    parser.add_argument("--control-config", default=str(DEFAULT_CONTROL_CONFIG))
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--max-time", type=float, default=1440)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--omp-threads", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    configs_dir = Path(args.configs_dir)
    if not args.executable:
        raise SystemExit("PhysiCell executable not configured. Set PHYSICELL_EXECUTABLE or pass --executable.")
    executable = Path(args.executable)
    control_config = Path(args.control_config)
    output = Path(args.output)
    if output.exists() and args.force:
        shutil.rmtree(output)
    if output.exists():
        raise SystemExit(f"Output already exists: {output}. Use --force to overwrite.")
    if not executable.exists():
        raise SystemExit(f"PhysiCell executable not found: {executable}")
    if not configs_dir.exists():
        raise SystemExit(f"Config directory not found: {configs_dir}")
    output.mkdir(parents=True)

    conditions = [("control", control_config)]
    for path in sorted(configs_dir.glob("*.xml")):
        name = path.stem
        name = name.replace("PhysiCell_settings_reasoned_", "").replace("PhysiCell_settings_", "")
        conditions.append((name, path))

    jobs = [(condition, config, rep) for condition, config in conditions for rep in range(1, args.replicates + 1)]
    print(f"running {len(jobs)} jobs: {len(conditions)} conditions x {args.replicates} replicates", flush=True)
    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(run_job, condition, config, rep, executable, output, args.max_time, args.omp_threads): (condition, rep)
            for condition, config, rep in jobs
        }
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            row = result.get("selected_metrics") or {}
            print(
                f"[{completed}/{len(jobs)}] {result['condition']} rep={result['replicate']} "
                f"rc={result['returncode']} tumor={row.get('live_tumor_count')} cart={row.get('live_cart_count')} "
                f"time={row.get('time_min')}",
                flush=True,
            )

    write_replicate_csv(output / "replicate_metrics.csv", results)
    summary_rows = summarize_results(results)
    write_summary_csv(output / "replicate_summary.csv", summary_rows)
    ranking = rank_summary(summary_rows)
    write_summary_csv(output / "replicate_ranking.csv", ranking)
    manifest = {
        "configs_dir": str(configs_dir),
        "executable": str(executable),
        "control_config": str(control_config),
        "replicates": args.replicates,
        "max_time": args.max_time,
        "workers": args.workers,
        "total_jobs": len(jobs),
        "successful_returncodes": sum(1 for row in results if row["returncode"] == 0),
        "metrics_outputs": sum(1 for row in results if row.get("metrics_csv")),
        "elapsed_seconds": round(time.time() - start, 2),
        "replicate_metrics_csv": str(output / "replicate_metrics.csv"),
        "replicate_summary_csv": str(output / "replicate_summary.csv"),
        "replicate_ranking_csv": str(output / "replicate_ranking.csv"),
        "note": "Multi-replicate in silico PhysiCell run. Results are not wet-lab validation.",
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    return 0


def run_job(
    condition: str,
    config: Path,
    replicate: int,
    executable: Path,
    output_root: Path,
    max_time: float,
    omp_threads: int,
) -> dict[str, Any]:
    condition_dir = output_root / condition / f"replicate_{replicate:02d}"
    condition_dir.mkdir(parents=True, exist_ok=True)
    run_config = prepare_config(config, condition_dir, max_time, omp_threads)
    command = (
        f"cd '{to_wsl(executable.parent)}' && "
        f"./{executable.name} '{to_wsl(run_config)}' OUTPUT_DIR='{to_wsl(condition_dir)}'"
    )
    start = time.time()
    proc = subprocess.run(["wsl", "-e", "bash", "-lc", command], text=True, capture_output=True)
    stdout_path = condition_dir / "physicell_stdout.log"
    stderr_path = condition_dir / "physicell_stderr.log"
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")
    metrics_csv = condition_dir / "metrics.csv"
    selected = selected_metrics(metrics_csv)
    if selected is not None:
        persist_avg_life_min = strict_persist_avg_life_min(condition_dir / "time_series.csv")
        if persist_avg_life_min is not None:
            selected["persist_avg_life_min"] = f"{persist_avg_life_min:.10e}"
    seed = extract_seed(proc.stdout or "")
    return {
        "condition": condition,
        "replicate": replicate,
        "returncode": proc.returncode,
        "elapsed_seconds": round(time.time() - start, 2),
        "reported_seed": seed,
        "metrics_csv": str(metrics_csv) if metrics_csv.exists() else None,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "selected_metrics": selected,
    }


def prepare_config(config: Path, condition_dir: Path, max_time: float, omp_threads: int) -> Path:
    tree = ET.parse(config)
    root = tree.getroot()
    set_text(root, "./overall/max_time", f"{max_time:g}")
    set_text(root, "./parallel/omp_num_threads", str(omp_threads))
    set_text(root, "./save/full_data/enable", "false")
    set_text(root, "./save/SVG/enable", "false")
    set_text(root, "./save/folder", to_wsl(condition_dir))
    out = condition_dir / "run_config.xml"
    tree.write(out, encoding="utf-8", xml_declaration=True)
    return out


def set_text(root: ET.Element, path: str, value: str) -> None:
    elem = root.find(path)
    if elem is not None:
        elem.text = value


def selected_metrics(metrics_csv: Path) -> dict[str, str] | None:
    if not metrics_csv.exists():
        return None
    rows = list(csv.DictReader(metrics_csv.open(newline="", encoding="utf-8")))
    if not rows:
        return None
    selected = rows[-1]
    for row in rows:
        try:
            if float(row.get("live_tumor_count", "nan")) <= 0:
                selected = row
                break
        except ValueError:
            pass
    return selected


def extract_seed(stdout: str) -> str | None:
    match = re.search(r"seed\s+(\d+)", stdout, re.I)
    return match.group(1) if match else None


def write_replicate_csv(path: Path, results: list[dict[str, Any]]) -> None:
    fields = [
        "condition",
        "replicate",
        "returncode",
        "reported_seed",
        "time_min",
        "live_tumor_count",
        "live_cart_count",
        "persist_avg_life_min",
        "mean_cart_activation",
        "mean_cart_exhaustion",
        "mean_aux_cytokine",
        "mean_IFNg",
        "mean_tumor_PDL1",
        "tumor_remaining_fraction",
        "metrics_csv",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in sorted(results, key=lambda row: (row["condition"], row["replicate"])):
            metrics = result.get("selected_metrics") or {}
            writer.writerow({field: result.get(field, metrics.get(field, "")) for field in fields})


def summarize_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        if result["returncode"] != 0 or not result.get("selected_metrics"):
            continue
        by_condition.setdefault(result["condition"], []).append(result["selected_metrics"])
    rows = []
    for condition, metrics_rows in sorted(by_condition.items()):
        row: dict[str, Any] = {"condition": condition, "n": len(metrics_rows)}
        for field in [
            "live_tumor_count",
            "live_cart_count",
            "persist_avg_life_min",
            "mean_cart_exhaustion",
            "mean_aux_cytokine",
            "mean_IFNg",
            "mean_tumor_PDL1",
            "tumor_remaining_fraction",
        ]:
            values = [float(item[field]) for item in metrics_rows if item.get(field) not in (None, "")]
            row[f"{field}_mean"] = round(statistics.fmean(values), 6) if values else ""
            row[f"{field}_sd"] = round(statistics.stdev(values), 6) if len(values) > 1 else 0 if values else ""
        rows.append(row)
    return rows


def strict_persist_avg_life_min(time_series_csv: Path) -> float | None:
    """Compute CAR-T persistence as RMST from the observed live CAR-T trajectory.

    This is the strict metric available from current PhysiCell outputs:
    integral(CAR_T_count(t) dt) / CAR_T_count(t=0), in minutes.
    It uses the full time series and does not substitute final live cell count.
    Exact per-cell lineage lifespan would require the C++ model to emit CAR-T
    birth/death records, which the current output files do not contain.
    """
    if not time_series_csv.exists():
        return None
    points: list[tuple[float, float]] = []
    with time_series_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            time_value = row.get("time_min")
            count_value = row.get("CAR_T_count") or row.get("live_cart_count")
            if time_value in (None, "") or count_value in (None, ""):
                continue
            try:
                points.append((float(time_value), float(count_value)))
            except ValueError:
                continue
    points = sorted(points)
    if len(points) < 2:
        return None
    initial_count = points[0][1]
    if initial_count <= 0:
        return None
    auc = 0.0
    for (t0, n0), (t1, n1) in zip(points, points[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        auc += dt * (max(n0, 0.0) + max(n1, 0.0)) / 2.0
    return auc / initial_count


def rank_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for row in rows:
        score_components = cytokine_priority_score_from_summary(row)
        scored.append({**row, **score_components})
    ranked = sorted(scored, key=lambda row: -float(row.get("ranked_intervention_score") or -1))
    out = []
    for index, row in enumerate(ranked, start=1):
        out.append({"rank": index, **row})
    return out


def clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def cytokine_priority_score_from_summary(row: dict[str, Any]) -> dict[str, float | str]:
    required = ["tumor_remaining_fraction_mean", "persist_avg_life_min_mean", "mean_cart_exhaustion_mean", "mean_tumor_PDL1_mean"]
    if any(row.get(field) in (None, "") for field in required):
        return {
            "K_score": "",
            "P_score": "",
            "E_score": "",
            "R_score": "",
            "ranked_intervention_score": "",
        }
    tumor_remaining_fraction = float(row["tumor_remaining_fraction_mean"])
    persist_avg_life_min = float(row["persist_avg_life_min_mean"])
    mean_cart_exhaustion = float(row["mean_cart_exhaustion_mean"])
    mean_tumor_pdl1 = float(row["mean_tumor_PDL1_mean"])
    k_score = 1.0 - clamp01((tumor_remaining_fraction - 0.30) / (1.00 - 0.30))
    p_score = clamp01((persist_avg_life_min - 600.0) / (1200.0 - 600.0))
    e_score = 1.0 - clamp01((mean_cart_exhaustion - 0.15) / (0.35 - 0.15))
    r_score = 1.0 - clamp01((mean_tumor_pdl1 - 0.03) / (0.18 - 0.03))
    score = 100.0 * clamp01(0.40 * k_score + 0.30 * p_score + 0.20 * e_score + 0.10 * r_score)
    return {
        "K_score": round(k_score, 6),
        "P_score": round(p_score, 6),
        "E_score": round(e_score, 6),
        "R_score": round(r_score, 6),
        "ranked_intervention_score": round(score, 6),
    }


def write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def to_wsl(path: Path) -> str:
    text = str(path.resolve()).replace("\\", "/")
    if len(text) > 2 and text[1] == ":":
        return f"/mnt/{text[0].lower()}{text[2:]}"
    return text


if __name__ == "__main__":
    raise SystemExit(main())
