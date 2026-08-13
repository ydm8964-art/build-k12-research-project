#!/usr/bin/env python3
"""Compare two manifest snapshots and list materials that must be regenerated or rechecked."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIELD_IMPACT = {
    "project": {"*"},
    "project_context": {"*"},
    "problem_context": {"*"},
    "governance": {"attention-items", "index", "analysis-report", "final-report", "closing-application"},
    "submission_requirements": {"application", "anonymous-form", "opening", "closing-application", "index", "attention-items"},
    "contributors": {"*"},
    "subject_coverage": {"blank-instrument", "observation-form", "assessment-tool", "intervention-plan", "lesson-plan", "task-sheet", "rubric", "case", "casebook", "analysis-report", "final-report", "attention-items"},
    "timeline": {"*"},
    "research_questions": {"*"},
    "logic_mappings": {"*"},
    "samples": {"data-workbook", "analysis-report", "final-report", "attention-items"},
    "instruments": {"blank-instrument", "interview-guide", "observation-form", "assessment-tool", "data-workbook", "analysis-report", "final-report", "attention-items"},
    "evidence": {"raw-data", "data-workbook", "analysis-report", "casebook", "evidence-book", "final-report", "proof", "index", "attention-items"},
    "interventions": {"intervention-plan", "lesson-plan", "task-sheet", "rubric", "casebook", "fidelity-log", "progress-report", "final-report", "attention-items"},
    "cases": {"lesson-plan", "task-sheet", "rubric", "case", "casebook", "evidence-book", "progress-report", "final-report", "attention-items"},
    "sources": {"application", "anonymous-form", "opening", "analysis-report", "lesson-plan", "casebook", "final-report", "closing-application", "attention-items"},
    "commitments": {"application", "progress-report", "final-report", "achievement-catalog", "proof", "index", "attention-items"},
    "claims": {"analysis-report", "casebook", "evidence-book", "final-report", "attention-items"},
    "evaluation_weights": {"assessment-tool", "rubric", "data-workbook", "analysis-report", "casebook", "final-report"},
}


def compare(old: dict, new: dict) -> dict:
    old_generation = old.get("generation_contract", {})
    new_generation = new.get("generation_contract", {})
    old_snapshot = str(old_generation.get("snapshot_id", ""))
    parent_snapshot = str(new_generation.get("parent_snapshot_id", ""))
    errors: list[str] = []
    if new_generation.get("batch_mode") != "incremental":
        errors.append("新主清单generation_contract.batch_mode必须是incremental")
    if old_snapshot and parent_snapshot != old_snapshot:
        errors.append(f"新主清单parent_snapshot_id应为旧快照{old_snapshot!r}")
    changed_fields = [field for field in FIELD_IMPACT if old.get(field) != new.get(field)]
    materials = [item for item in new.get("materials", []) if isinstance(item, dict)]
    affected: list[dict] = []
    for item in materials:
        role = str(item.get("material_role", ""))
        reasons = [field for field in changed_fields if "*" in FIELD_IMPACT[field] or role in FIELD_IMPACT[field]]
        if reasons:
            affected.append(
                {
                    "material_id": item.get("id"),
                    "name": item.get("name"),
                    "material_role": role,
                    "current_status": item.get("status"),
                    "reasons": reasons,
                    "required_action": "从新快照重新生成；重新执行内容、格式、渲染、隐私及适用的数据/照片QA",
                }
            )
    return {
        "schema_version": "1.3",
        "old_snapshot_id": old_snapshot or None,
        "new_snapshot_id": new_generation.get("snapshot_id"),
        "changed_fields": changed_fields,
        "affected_material_count": len(affected),
        "affected_materials": affected,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_manifest", type=Path)
    parser.add_argument("new_manifest", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        old = json.loads(args.old_manifest.read_text(encoding="utf-8"))
        new = json.loads(args.new_manifest.read_text(encoding="utf-8"))
        report = compare(old, new)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output + "\n", encoding="utf-8")
        print(args.out.resolve())
    else:
        print(output)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
