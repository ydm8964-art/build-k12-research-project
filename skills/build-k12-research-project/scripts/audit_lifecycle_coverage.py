#!/usr/bin/env python3
"""Audit whether a manifest covers the material-role groups promised by its package scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

READY_STATUSES = {"ready", "submitted", "archived"}
GROUPS = {
    "attention-file": {"attention-items"},
    "application": {"application"},
    "anonymous-form": {"anonymous-form"},
    "opening": {"opening"},
    "ethics-consent": {"consent-form"},
    "research-instrument": {"blank-instrument", "interview-guide", "observation-form", "assessment-tool"},
    "coding-plan": {"codebook", "data-workbook"},
    "data-workbook": {"data-workbook"},
    "raw-evidence": {"raw-data", "completed-record", "transcription"},
    "diagnostic-analysis": {"analysis-report"},
    "intervention": {"intervention-plan"},
    "practice-carrier": {"lesson-plan", "task-sheet", "case", "casebook"},
    "evaluation-tool": {"rubric", "assessment-tool"},
    "process-management": {"fidelity-log", "meeting-record", "progress-report"},
    "photo-register": {"photo-register"},
    "evidence-book": {"evidence-book"},
    "final-report": {"final-report"},
    "closing-application": {"closing-application"},
    "achievement-catalog": {"achievement-catalog"},
    "proof-or-appraisal": {"proof", "expert-appraisal"},
    "delivery-index": {"index"},
}
SCOPE_GROUPS = {
    "application-kit": ("attention-file", "application"),
    "implementation-kit": (
        "attention-file", "opening", "ethics-consent", "research-instrument", "coding-plan", "data-workbook",
        "intervention", "practice-carrier", "evaluation-tool", "process-management", "photo-register",
    ),
    "full-lifecycle-kit": (
        "attention-file", "application", "opening", "ethics-consent", "research-instrument", "coding-plan",
        "data-workbook", "raw-evidence", "diagnostic-analysis", "intervention",
        "practice-carrier", "evaluation-tool",
        "process-management", "photo-register", "evidence-book", "final-report",
        "closing-application", "achievement-catalog", "proof-or-appraisal", "delivery-index",
    ),
    "closing-kit": (
        "attention-file", "raw-evidence", "diagnostic-analysis", "final-report", "closing-application", "achievement-catalog",
        "photo-register", "evidence-book", "proof-or-appraisal", "delivery-index",
    ),
    "custom": ("attention-file",),
}


def audit(data: dict, final: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    generation = data.get("generation_contract", {})
    if not isinstance(generation, dict):
        return ["缺少generation_contract"], warnings
    scope = generation.get("package_scope")
    required_groups = list(SCOPE_GROUPS.get(scope, ()))
    requirements = data.get("submission_requirements", {})
    if isinstance(requirements, dict) and requirements.get("anonymous_required") is True:
        required_groups.append("anonymous-form")

    exemptions = generation.get("coverage_exemptions", [])
    exemption_groups = {
        str(item.get("group"))
        for item in exemptions
        if isinstance(item, dict) and item.get("group") and str(item.get("reason", "")).strip()
    }
    unknown_exemptions = exemption_groups - set(GROUPS)
    if unknown_exemptions:
        errors.append(f"coverage_exemptions含未知组：{sorted(unknown_exemptions)}")

    materials = [item for item in data.get("materials", []) if isinstance(item, dict)]
    delivery_state = generation.get("delivery_state")
    require_ready = {
        "application-ready": {"attention-file", "application", "anonymous-form"},
        "implementation-ready": set(SCOPE_GROUPS["implementation-kit"]),
        "closing-ready": set(SCOPE_GROUPS["closing-kit"]),
    }.get(delivery_state, set())

    for group in required_groups:
        if group in exemption_groups:
            warnings.append(f"生命周期组{group}已豁免；交付时保留书面理由")
            continue
        matching = [item for item in materials if item.get("material_role") in GROUPS[group]]
        if not matching:
            (errors if final else warnings).append(
                f"{scope}缺少生命周期组{group}，应包含角色{sorted(GROUPS[group])}之一或登记豁免"
            )
            continue
        if group in require_ready and not any(item.get("status") in READY_STATUSES for item in matching):
            (errors if final else warnings).append(f"交付状态{delivery_state}要求生命周期组{group}至少一份材料ready")
        elif group == "attention-file" and not any(item.get("status") in READY_STATUSES for item in matching):
            (errors if final else warnings).append("材料包注意事项文件尚未实际生成并标记ready")

    if delivery_state == "closing-ready":
        pending = [
            str(item.get("id", "未编号"))
            for item in materials
            if item.get("status") in {"pending-data", "pending-photo", "pending-signature"}
            and item.get("stage") in {"final", "closing"}
        ]
        if pending:
            errors.append(f"closing-ready仍含待数据/照片/签章的结题材料：{pending}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors, warnings = audit(data, args.final)
    for item in warnings:
        print(f"警告：{item}")
    for item in errors:
        print(f"错误：{item}")
    if errors:
        print(f"生命周期覆盖审计未通过：{len(errors)}个错误，{len(warnings)}个警告")
        return 1
    print(f"生命周期覆盖审计通过：0个错误，{len(warnings)}个警告")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
