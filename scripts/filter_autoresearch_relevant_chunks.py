from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CYTOKINES = ["IL-2", "IL-7", "IL-12", "IL-15", "IL-18"]

CYTOKINE_PATTERNS = {
    "IL-2": [r"\bIL[- ]?2\b", r"interleukin[- ]?2\b"],
    "IL-7": [r"\bIL[- ]?7\b", r"interleukin[- ]?7\b"],
    "IL-12": [r"\bIL[- ]?12\b", r"interleukin[- ]?12\b"],
    "IL-15": [r"\bIL[- ]?15\b", r"interleukin[- ]?15\b"],
    "IL-18": [r"\bIL[- ]?18\b", r"interleukin[- ]?18\b"],
}

CAR_T_PATTERNS = [
    r"CAR[- ]?T",
    r"chimeric antigen receptor",
    r"engineered T",
    r"transgenic",
    r"armou?red",
    r"self[- ]?secret",
    r"secret(?:e|ing|ion)",
]

T_CELL_MECHANISM_PATTERNS = [
    r"proliferation",
    r"persistence",
    r"exhaustion",
    r"cytotoxicity",
    r"IFN[- ]?(?:g|gamma|γ)",
    r"AICD",
    r"activation-induced cell death",
    r"granzyme",
    r"perforin",
    r"memory",
]

TUMOR_PATTERNS = [
    r"GPC3|glypican[- ]?3",
    r"hepatocellular|HCC|liver cancer",
    r"antigen density|antigen expression|low antigen|heterogeneous antigen|antigen loss",
    r"PD[- ]?L1|hypoxia|necrosis|proliferation|oxygen",
    r"tumou?r cell|cancer cell",
]

NOISE_PATTERNS = [
    r"SARS[- ]?CoV[- ]?2",
    r"COVID[- ]?19",
    r"acute respiratory distress syndrome",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter CAR-T cytokine and tumor chunks before AutoResearch LLM review.")
    parser.add_argument("--cytokine-chunks", required=True)
    parser.add_argument("--tumor-chunks", required=True)
    parser.add_argument("--output", default="outputs/autoresearch_relevance_filtered_chunks")
    parser.add_argument("--max-per-cytokine", type=int, default=40)
    parser.add_argument("--max-tumor", type=int, default=40)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output}. Use --force to overwrite.")
    output.mkdir(parents=True, exist_ok=True)

    cytokine_rows = read_jsonl(Path(args.cytokine_chunks))
    tumor_rows = read_jsonl(Path(args.tumor_chunks))

    selected_by_cytokine: dict[str, list[dict[str, Any]]] = {}
    report: dict[str, Any] = {
        "cytokine_input_chunks": len(cytokine_rows),
        "tumor_input_chunks": len(tumor_rows),
        "max_per_cytokine": args.max_per_cytokine,
        "max_tumor": args.max_tumor,
        "cytokines": {},
        "notes": [
            "Chunk filtering is heuristic and only narrows context for LLM review.",
            "Filtering does not establish scientific relevance; LLM and human review still inspect provenance.",
            "No citations, LLM outputs, PhysiCell outputs, or wet-lab values are fabricated.",
        ],
    }

    all_selected = []
    seen_ids = set()
    for cytokine in CYTOKINES:
        scored = []
        for row in cytokine_rows:
            score, reasons = score_cytokine_chunk(row, cytokine)
            if score > 0:
                scored.append((score, int(row.get("word_count") or 0), reasons, row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = []
        for score, _words, reasons, row in scored[: args.max_per_cytokine]:
            enriched = dict(row, autoresearch_topic="cytokine", target_cytokine=cytokine, relevance_score=score, relevance_reasons=reasons)
            selected.append(enriched)
            chunk_id = str(row.get("chunk_id"))
            if chunk_id not in seen_ids:
                all_selected.append(enriched)
                seen_ids.add(chunk_id)
        selected_by_cytokine[cytokine] = selected
        write_jsonl(output / f"{cytokine.lower().replace('-', '')}_chunks.jsonl", selected)
        report["cytokines"][cytokine] = {
            "candidate_chunks": len(scored),
            "selected_chunks": len(selected),
            "top_chunk_ids": [row.get("chunk_id") for row in selected[:10]],
        }

    tumor_scored = []
    for row in tumor_rows:
        score, reasons = score_tumor_chunk(row)
        if score > 0:
            tumor_scored.append((score, int(row.get("word_count") or 0), reasons, row))
    tumor_scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected_tumor = [
        dict(row, autoresearch_topic="tumor", relevance_score=score, relevance_reasons=reasons)
        for score, _words, reasons, row in tumor_scored[: args.max_tumor]
    ]

    write_jsonl(output / "selected_cytokine_chunks.jsonl", all_selected)
    write_jsonl(output / "selected_tumor_chunks.jsonl", selected_tumor)
    report["cytokine_selected_unique_chunks"] = len(all_selected)
    report["tumor_candidate_chunks"] = len(tumor_scored)
    report["tumor_selected_chunks"] = len(selected_tumor)
    (output / "relevance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def score_cytokine_chunk(row: dict[str, Any], cytokine: str) -> tuple[int, list[str]]:
    title = str(row.get("title") or "")
    section = str(row.get("section") or "")
    text = str(row.get("text") or "")
    combined = " ".join([title, section, text])
    score = 0
    reasons = []
    cytokine_hits = count_patterns(CYTOKINE_PATTERNS[cytokine], combined)
    if not cytokine_hits:
        return 0, []
    score += 4 * cytokine_hits
    reasons.append(f"{cytokine} mention")
    car_t_hits = count_patterns(CAR_T_PATTERNS, combined)
    mechanism_hits = count_patterns(T_CELL_MECHANISM_PATTERNS, combined)
    body_car_t_hits = count_patterns(CAR_T_PATTERNS, text)
    if car_t_hits:
        score += 3 * car_t_hits
        reasons.append("CAR-T/engineered/self-secreting context")
    if mechanism_hits:
        score += mechanism_hits
        reasons.append("T-cell functional mechanism")
    if body_car_t_hits:
        score += 3
        reasons.append("CAR-T evidence in chunk body")
    noise_hits = count_patterns(NOISE_PATTERNS, text)
    if noise_hits and not body_car_t_hits:
        score -= 8 * noise_hits
        reasons.append("penalized likely off-topic immune/infection chunk")
    return (score if score >= 6 and (car_t_hits or mechanism_hits) else 0), reasons


def score_tumor_chunk(row: dict[str, Any]) -> tuple[int, list[str]]:
    combined = " ".join(str(row.get(key) or "") for key in ["title", "section", "text"])
    score = count_patterns(TUMOR_PATTERNS, combined)
    reasons = ["tumor/antigen context"] if score else []
    return score, reasons


def count_patterns(patterns: list[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, re.I))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
