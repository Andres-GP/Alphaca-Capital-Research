#!/usr/bin/env python3
"""Collect matrix artifacts and prepare report links and PR summary."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


FAMILIES = ["momentum_trend", "mean_reversion", "calendar_seasonality", "overnight_gaps", "carry_relative_value"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--summary-json", required=True, type=Path)
    parser.add_argument("--copy-artifacts", action="store_true")
    args = parser.parse_args()

    report_root = args.repo_root / "research_development" / "01_initial_research" / "reportes"
    results = []
    for family in FAMILIES:
        artifact = args.artifact_dir / f"research-{family}"
        destination = report_root / f"{args.date}_{family}"
        source_yaml = artifact / "report.yaml"
        has_artifact = source_yaml.is_file()
        if args.copy_artifacts and has_artifact:
            destination.mkdir(parents=True, exist_ok=True)
            for entry in artifact.iterdir():
                target = destination / entry.name
                if entry.is_dir():
                    shutil.copytree(entry, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry, target)

        yaml_path = destination / "report.yaml" if args.copy_artifacts and has_artifact else source_yaml
        if has_artifact and yaml_path.is_file():
            metadata = json.loads(yaml_path.read_text(encoding="utf-8"))
            role_outputs = yaml_path.parent / "agentes"
            failures = []
            for output in sorted(role_outputs.glob("*.md")):
                if output.read_text(encoding="utf-8").startswith("FALLO:"):
                    failures.append(output.stem)
            results.append({
                "family": family,
                "status": metadata.get("status", "unknown"),
                "engines": metadata.get("engines", {}),
                "hypotheses": metadata.get("hypotheses", []),
                "failures": failures,
                "report_path": f"research_development/01_initial_research/reportes/{args.date}_{family}/report.md",
            })
        else:
            results.append({"family": family, "status": "missing_artifact", "engines": {}, "hypotheses": [], "failures": ["no se recibió artefacto"], "report_path": ""})

    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps({"date": args.date, "families": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in results:
        print(f"{item['family']}: {item['status']}")


if __name__ == "__main__":
    main()
